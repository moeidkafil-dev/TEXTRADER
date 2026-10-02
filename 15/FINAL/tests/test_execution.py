"""Execution + Guard + Final Tools tests — REQ-EG-01, REQ-BRK-01, REQ-FT-01."""
import pytest

from trader.adapters.broker.mock import MockBroker
from trader.adapters.broker.base import OrderRequest
from trader.core.schemas import (
    ExecutionOrder, RiskResult, RuleResult, VetoEvent, VetoResponse, Side,
    OrderStatus,
)
from trader.services.execution_guard import ExecutionGuard
from trader.services.kill_switch import KillSwitch
from trader.services.final_tools import FinalTools
from trader.services.observability import Observability


def _order(side="BUY", size=10, sl=99, tp=101):
    return ExecutionOrder(side=side, instrument="XIR/USDT", size=size,
                           sl=sl, tp=tp, cycle_id="c1")


def _risk_ok(order):
    return RiskResult(order_id=order.order_id, passed=True,
                       rules=(RuleResult(rule="all", passed=True, reason="ok"),))


def _risk_bad(order):
    return RiskResult(order_id=order.order_id, passed=False,
                       rules=(RuleResult(rule="position_size", passed=False,
                                          reason="too big"),))


def test_guard_allows_ok(orchestrator):
    """REQ-EG-01 — order with risk pass + OK veto + not halted ⇒ allow."""
    o = _order()
    r = _risk_ok(o)
    v = VetoEvent(order_id=o.order_id, notified_at=orchestrator.db.query("SELECT datetime('now')")[0]["datetime('now')"],
                  response=VetoResponse.OK.value)
    allowed, why = orchestrator.guard.allow(o, r, v)
    assert allowed
    assert why == "ok"


def test_guard_blocks_when_halted(orchestrator):
    """I2 — halted ⇒ no orders pass."""
    orchestrator.activate_kill_switch("test")
    o = _order()
    r = _risk_ok(o)
    v = VetoEvent(order_id=o.order_id, notified_at="2026-09-22T00:00:00+00:00",
                  response=VetoResponse.OK.value)
    allowed, _ = orchestrator.guard.allow(o, r, v)
    assert not allowed


def test_guard_blocks_when_risk_failed(orchestrator):
    """I1 — risk fail ⇒ no pass."""
    o = _order()
    r = _risk_bad(o)
    v = VetoEvent(order_id=o.order_id, notified_at="2026-09-22T00:00:00+00:00",
                  response=VetoResponse.OK.value)
    allowed, _ = orchestrator.guard.allow(o, r, v)
    assert not allowed


def test_guard_blocks_when_user_rejected(orchestrator):
    """I3 — user reject ⇒ no pass."""
    o = _order()
    r = _risk_ok(o)
    v = VetoEvent(order_id=o.order_id, notified_at="2026-09-22T00:00:00+00:00",
                  response=VetoResponse.REJECT.value)
    allowed, _ = orchestrator.guard.allow(o, r, v)
    assert not allowed


def test_guard_idempotency(orchestrator):
    """TST-SYS-09 — duplicate idempotency_key rejected."""
    o = _order()
    r = _risk_ok(o)
    v = VetoEvent(order_id=o.order_id, notified_at="2026-09-22T00:00:00+00:00",
                  response=VetoResponse.OK.value)
    allowed1, _ = orchestrator.guard.allow(o, r, v)
    assert allowed1
    # re-create a fresh guard with the same key (simulating restart)
    allowed2, why = orchestrator.guard.allow(o, r, v)
    assert not allowed2
    assert "duplicate" in why.lower()


def test_mock_broker_fill(orchestrator):
    """REQ-BRK-01 — Mock Broker fills valid order."""
    o = _order()
    res = orchestrator.final_tools.buy_system(o)
    assert res.status == OrderStatus.FILLED.value
    assert res.fill_price > 0


def test_mock_broker_idempotency():
    """REQ-BRK-01 / TST-SYS-09 — idempotent submit ignored."""
    broker = MockBroker()
    o = _order()
    req = OrderRequest(order_id=o.order_id, idempotency_key=o.idempotency_key,
                       side=o.side, instrument=o.instrument, size=o.size,
                       sl=o.sl, tp=o.tp)
    ack1 = broker.submit(req)
    ack2 = broker.submit(req)
    assert ack1.ok
    assert ack1.status == "filled"
    assert ack2.ok  # idempotent — no error, but no second fill
    assert "idempotent" in ack2.reason.lower()


def test_final_tools_skip():
    """REQ-FT-01 — skip tool exists and is no-op."""
    obs = Observability(db_getter=lambda: None, level="error")
    broker = MockBroker()
    ft = FinalTools(broker, observability=obs)
    res = ft.skip(_order())
    assert res.status == OrderStatus.CANCELLED.value


def test_final_tools_side_mismatch():
    """FinalTools refuses side mismatch."""
    broker = MockBroker()
    ft = FinalTools(broker, observability=None)
    o = _order(side="SELL")
    # call buy_system on a SELL order
    res = ft.buy_system(o)
    assert res.status == OrderStatus.REJECTED.value
    assert "side mismatch" in res.broker_ack
