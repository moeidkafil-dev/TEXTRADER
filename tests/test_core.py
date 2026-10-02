"""Core schema + state machine + invariant tests."""
import pytest

from trader.core.schemas import (
    Action, FailureCategory, Severity, InitialDecision, FailureReport,
    FailurePath, FinalDecision, ExecutionOrder, Side, is_valid_initial,
    is_valid_failure_report, is_valid_final, is_valid_order,
)
from trader.core.state_machine import State, StateMachine, Transition


def test_action_enum():
    assert Action.BUY.value == "BUY"
    assert Action.WAIT.value == "WAIT"
    assert Action.RE_EVALUATE.value == "RE-EVALUATE"
    assert "RE-EVALUATE" in Action.final_values()


def test_failure_categories_count():
    # All 9 categories from chapter 06 must exist
    assert len(FailureCategory.all()) == 9
    expected = {
        "wrong_prediction", "logical_inconsistency", "missing_data",
        "invalid_assumption", "risk_violation", "contradictory_evidence",
        "tool_failure", "model_uncertainty", "execution_impossibility",
    }
    assert {c.value for c in FailureCategory.all()} == expected


def test_is_valid_initial():
    d = InitialDecision(cycle_id="c", action="BUY", instrument="X", rationale="r")
    assert is_valid_initial(d)
    d2 = InitialDecision(cycle_id="c", action="INVALID", instrument="X", rationale="r")
    assert not is_valid_initial(d2)


def test_is_valid_failure_report_all_categories_required():
    # Missing category ⇒ invalid (per REQ-AG-03 acceptance)
    paths = tuple(FailurePath(category=c.value, description="x", severity="low")
                  for c in FailureCategory.all())
    r = FailureReport(cycle_id="c", paths=paths)
    assert is_valid_failure_report(r)
    # Missing one category ⇒ invalid
    partial = paths[:8]
    r2 = FailureReport(cycle_id="c", paths=partial)
    assert not is_valid_failure_report(r2)


def test_is_valid_final():
    d = FinalDecision(cycle_id="c", decision="WAIT", overrode_initial=False, reason="ok")
    assert is_valid_final(d)
    d2 = FinalDecision(cycle_id="c", decision="INVALID", overrode_initial=False, reason="ok")
    assert not is_valid_final(d2)


def test_is_valid_order():
    o = ExecutionOrder(side="BUY", instrument="X", size=10, sl=1, tp=2)
    assert is_valid_order(o)
    o2 = ExecutionOrder(side="BUY", instrument="X", size=0, sl=1, tp=2)
    assert not is_valid_order(o2)


def test_state_machine_basic_transitions():
    sm = StateMachine(state=State.IDLE)
    assert sm.can(Transition.START_CYCLE)
    sm.apply(Transition.START_CYCLE)
    assert sm.state == State.READING
    sm.apply(Transition.DATA_READ)
    sm.apply(Transition.CONTEXT_READY)
    sm.apply(Transition.A1_DONE)
    sm.apply(Transition.A2_DONE)
    sm.apply(Transition.A3_BUY_SELL)
    assert sm.state == State.AWAIT_VETO


def test_state_machine_illegal_transition():
    sm = StateMachine(state=State.IDLE)
    with pytest.raises(ValueError):
        sm.apply(Transition.VETO_OK)  # can't veto from IDLE


def test_state_machine_kill_switch_forces_halted():
    sm = StateMachine(state=State.A3)
    sm.force_halted()
    assert sm.state == State.HALTED


def test_state_machine_resume_from_halted():
    sm = StateMachine(state=State.HALTED)
    sm.apply(Transition.RESUME_FROM_HALTED)
    assert sm.state == State.IDLE
