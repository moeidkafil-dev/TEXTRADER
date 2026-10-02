"""
State machine — chapter 04 STATE_MACHINE.md.

States: IDLE, READING, CONTEXTING, A1, A2, A3, AWAIT_VETO, RISK_CHECK,
        GUARD, EXECUTING, WAITING, REEVAL, HALTED

Transitions enforced by the orchestrator. The orchestrator never directly jumps
outside the allowed transition set; any illegal attempt is rejected and logged
to observability with level=error.

Kill Switch has absolute priority (REQ-P-05): from ANY state, a KillSwitch
event forces a transition to HALTED. Recovery from HALTED requires an explicit
resume command (no auto-recovery).
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class State(str, Enum):
    IDLE = "IDLE"
    READING = "READING"
    CONTEXTING = "CONTEXTING"
    A1 = "A1"
    A2 = "A2"
    A3 = "A3"
    AWAIT_VETO = "AWAIT_VETO"
    RISK_CHECK = "RISK_CHECK"
    GUARD = "GUARD"
    EXECUTING = "EXECUTING"
    WAITING = "WAITING"
    REEVAL = "REEVAL"
    HALTED = "HALTED"


# Transition labels
class Transition(str, Enum):
    START_CYCLE = "START_CYCLE"
    DATA_READ = "DATA_READ"
    CONTEXT_READY = "CONTEXT_READY"
    A1_DONE = "A1_DONE"
    A2_DONE = "A2_DONE"
    A3_BUY_SELL = "A3_BUY_SELL"
    A3_WAIT = "A3_WAIT"
    A3_REEVAL = "A3_REEVAL"
    VETO_SILENCE = "VETO_SILENCE"
    VETO_OK = "VETO_OK"
    VETO_REJECT = "VETO_REJECT"
    VETO_STOP = "VETO_STOP"
    RISK_PASS = "RISK_PASS"
    RISK_REJECT = "RISK_REJECT"
    GUARD_PASS = "GUARD_PASS"
    GUARD_REJECT = "GUARD_REJECT"
    EXEC_DONE = "EXEC_DONE"
    EXEC_FAIL = "EXEC_FAIL"
    USER_RESUME = "USER_RESUME"
    USER_NEW_COMMAND = "USER_NEW_COMMAND"
    KILL_SWITCH = "KILL_SWITCH"
    RESUME_FROM_HALTED = "RESUME_FROM_HALTED"


# Allowed transitions (from_state, transition) -> to_state
_ALLOWED: dict[tuple[State, Transition], State] = {
    (State.IDLE, Transition.START_CYCLE): State.READING,
    (State.READING, Transition.DATA_READ): State.CONTEXTING,
    (State.CONTEXTING, Transition.CONTEXT_READY): State.A1,
    (State.A1, Transition.A1_DONE): State.A2,
    (State.A2, Transition.A2_DONE): State.A3,
    (State.A3, Transition.A3_BUY_SELL): State.AWAIT_VETO,
    (State.A3, Transition.A3_WAIT): State.WAITING,
    (State.A3, Transition.A3_REEVAL): State.REEVAL,
    (State.REEVAL, Transition.START_CYCLE): State.READING,
    (State.AWAIT_VETO, Transition.VETO_SILENCE): State.RISK_CHECK,
    (State.AWAIT_VETO, Transition.VETO_OK): State.RISK_CHECK,
    (State.AWAIT_VETO, Transition.VETO_REJECT): State.WAITING,
    (State.AWAIT_VETO, Transition.VETO_STOP): State.WAITING,
    (State.RISK_CHECK, Transition.RISK_PASS): State.GUARD,
    (State.RISK_CHECK, Transition.RISK_REJECT): State.WAITING,
    (State.GUARD, Transition.GUARD_PASS): State.EXECUTING,
    (State.GUARD, Transition.GUARD_REJECT): State.WAITING,
    (State.EXECUTING, Transition.EXEC_DONE): State.IDLE,
    (State.EXECUTING, Transition.EXEC_FAIL): State.WAITING,
    (State.WAITING, Transition.USER_NEW_COMMAND): State.IDLE,
    (State.WAITING, Transition.START_CYCLE): State.READING,
    (State.HALTED, Transition.RESUME_FROM_HALTED): State.IDLE,
}


@dataclass
class StateMachine:
    """Pure state machine — no I/O, no side effects.

    The orchestrator holds an instance of this; every transition is logged to
    observability and audit. Illegal transitions raise (defensive) — but the
    orchestrator wraps them so that an illegal attempt ⇒ WAIT + log, never a crash.
    """
    state: State = State.IDLE

    def can(self, t: Transition) -> bool:
        return (self.state, t) in _ALLOWED

    def next_state(self, t: Transition) -> Optional[State]:
        # Kill switch is checked first by the orchestrator; this helper does not
        # special-case it so the rule table stays explicit.
        return _ALLOWED.get((self.state, t))

    def apply(self, t: Transition) -> State:
        nxt = _ALLOWED.get((self.state, t))
        if nxt is None:
            raise ValueError(f"Illegal transition {t.value} from state {self.state.value}")
        self.state = nxt
        return nxt

    def force_halted(self) -> None:
        self.state = State.HALTED

    def force_idle(self) -> None:
        self.state = State.IDLE


def allowed_transitions(s: State) -> list[Transition]:
    return [t for (src, t) in _ALLOWED if src == s]
