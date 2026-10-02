import pytest

from xir_trader.core.schemas import (
    InitialDecision, FailureReport, FailurePath, SchemaError,
)
from xir_trader.services.execution import ExecutionGuard, GuardRejection
from xir_trader.adapters.broker.mock import MockBroker
from xir_trader.services.db_manager import DBManager
from xir_trader.services.observability import Observability
from xir_trader.core.schemas import ExecutionOrder
from xir_trader.core.schemas import RiskResult
from xir_trader.core.config import RiskConfig
from xir_trader.services.risk_engine import RiskEngine, PortfolioSnapshot
import datetime as dt
import time


RULES = ["01_position_size", "02_max_daily_loss", "03_max_drawdown", "04_exposure_limit",
         "05_leverage_limit", "06_stop_loss_validation", "07_take_profit_validation",
         "08_correlation_exposure", "09_portfolio_exposure", "10_trading_session_rules",
         "11_liquidity_feasibility", "12_emergency_kill_switch"]


def _risk(engine, order, failed=False):
    if failed:
        # Caller-authored rule lists are intentionally not valid authorizations.
        return RiskResult(order.order_id, [{"rule": name, "passed": False, "reason": "test"} for name in RULES])
    return engine.check(order, PortfolioSnapshot(10_000, 0, 0, {}, 0, 1, 0),
                        now=dt.datetime(2026, 9, 25, 12, tzinfo=dt.timezone.utc),
                        execution_facts={"bid": 99, "ask": 100, "bid_size": 10, "ask_size": 10})


def test_i5_invalid_initial_decision_action_raises():
    with pytest.raises(SchemaError):
        InitialDecision(cycle_id="c1", action="HOLD", instrument="EURUSD", rationale="x").validate()


def test_i5_failure_report_must_cover_all_9_categories():
    incomplete = FailureReport(cycle_id="c1", paths=[
        FailurePath(category="wrong_prediction", description="x", severity="low"),
    ])
    with pytest.raises(SchemaError):
        incomplete.validate()


def test_i1_guard_refuses_order_that_did_not_pass_risk(tmp_path):
    db = DBManager(str(tmp_path / "t.db"))
    obs = Observability(db, "test")
    engine = RiskEngine(RiskConfig())
    guard = ExecutionGuard(MockBroker(), db, obs, risk_engine=engine)
    order = ExecutionOrder(side="BUY", instrument="EURUSD", size=10, sl=1, tp=1, cycle_id="c1")
    db.set_system_state("EXECUTING")
    with pytest.raises(GuardRejection):
        guard.submit(order, risk_result=_risk(engine, order, failed=True), system_state="EXECUTING",
                     human_stop=False, trace_id="t1")
    db.close()


def test_i1_guard_blocks_duplicate_idempotency_key(tmp_path):
    db = DBManager(str(tmp_path / "t2.db"))
    obs = Observability(db, "test")
    engine = RiskEngine(RiskConfig())
    broker = MockBroker()
    guard = ExecutionGuard(broker, db, obs, risk_engine=engine)
    order = ExecutionOrder(side="BUY", instrument="EURUSD", size=10, sl=1, tp=1, cycle_id="c1")
    db.set_system_state("EXECUTING")
    db.save_veto_event(order.order_id, time.time(), "OK")
    guard.submit(order, risk_result=_risk(engine, order), system_state="EXECUTING", human_stop=False, trace_id="t1")
    order2 = ExecutionOrder(side="BUY", instrument="EURUSD", size=10, sl=1, tp=1, cycle_id="c1")
    # same cycle_id/side/instrument => same idempotency_key (P-04)
    with pytest.raises(GuardRejection):
        db.save_veto_event(order2.order_id, time.time(), "OK")
        guard.submit(order2, risk_result=_risk(engine, order2), system_state="EXECUTING",
                     human_stop=False, trace_id="t1")
    assert len(broker.filled_orders) == 1
    db.close()
