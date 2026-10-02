import pytest
from xir_trader.core.state_machine import StateMachine, State, IllegalTransition


def test_happy_path_transitions():
    sm = StateMachine()
    for s in [State.READING, State.CONTEXTING, State.A1, State.A2, State.A3,
              State.AWAIT_VETO, State.RISK_CHECK, State.GUARD, State.EXECUTING, State.IDLE]:
        sm.go(s)
    assert sm.state == State.IDLE


def test_illegal_transition_rejected():
    sm = StateMachine()
    with pytest.raises(IllegalTransition):
        sm.go(State.EXECUTING)  # can't jump straight from IDLE to EXECUTING


def test_kill_switch_from_any_state():
    for start in [State.READING, State.A1, State.A2, State.A3, State.AWAIT_VETO,
                  State.RISK_CHECK, State.GUARD, State.EXECUTING]:
        sm = StateMachine()
        # walk to `start` via legal path where possible, otherwise force for test purposes
        sm.state = start
        sm.kill_switch("test")
        assert sm.state == State.HALTED


def test_halted_only_leaves_via_explicit_recovery():
    sm = StateMachine()
    sm.kill_switch("test")
    with pytest.raises(IllegalTransition):
        sm.recover_from_halt(operator_confirmed=False)
    assert sm.state == State.HALTED
    sm.recover_from_halt(operator_confirmed=True)
    assert sm.state == State.IDLE


def test_reeval_loops_back_to_reading():
    sm = StateMachine()
    for s in [State.READING, State.CONTEXTING, State.A1, State.A2, State.A3, State.REEVAL]:
        sm.go(s)
    assert sm.state == State.REEVAL
    sm.go(State.READING)
    assert sm.state == State.READING
