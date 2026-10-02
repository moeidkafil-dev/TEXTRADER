import pytest

from xir_trader.core.schemas import (
    InitialDecision, FailureReport, FailurePath, FinalDecision, SchemaError,
)
from xir_trader.services.execution import ExecutionGuard, GuardRejection
from xir_trader.adapters.broker.mock import MockBroker
from xir_trader.services.db_manager import DBManager
from xir_trader.services.observability import Observability
from xir_trader.core.schemas import ExecutionOrder


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
    guard = ExecutionGuard(MockBroker(), db, obs)
    order = ExecutionOrder(side="BUY", instrument="EURUSD", size=10, sl=1, tp=1, cycle_id="c1")
    with pytest.raises(GuardRejection):
        guard.submit(order, risk_passed=False, trace_id="t1")
    db.close()


def test_i1_guard_blocks_duplicate_idempotency_key(tmp_path):
    db = DBManager(str(tmp_path / "t2.db"))
    obs = Observability(db, "test")
    guard = ExecutionGuard(MockBroker(), db, obs)
    order = ExecutionOrder(side="BUY", instrument="EURUSD", size=10, sl=1, tp=1, cycle_id="c1")
    guard.submit(order, risk_passed=True, trace_id="t1")
    order2 = ExecutionOrder(side="BUY", instrument="EURUSD", size=10, sl=1, tp=1, cycle_id="c1")
    # same cycle_id/side/instrument => same idempotency_key (P-04)
    with pytest.raises(GuardRejection):
        guard.submit(order2, risk_passed=True, trace_id="t1")
    db.close()
