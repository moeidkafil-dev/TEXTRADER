"""
State machine — verbatim transitions from
04_FORMAL_SYSTEM_SPECIFICATION/STATE_MACHINE.md:

IDLE->READING->CONTEXTING->A1->A2->A3
A3--BUY/SELL-->AWAIT_VETO--(silence|OK)-->RISK_CHECK--pass-->GUARD-->EXECUTING-->IDLE
AWAIT_VETO--(reject|stop)-->WAITING--(user command)-->IDLE
A3--WAIT-->WAITING/IDLE ; A3--RE-EVALUATE-->REEVAL->READING
RISK_CHECK--reject-->WAITING ; any state--KillSwitch-->HALTED--(explicit command)-->IDLE

Invariants (04_FORMAL_SYSTEM_SPECIFICATION/SYSTEM_MODEL.md), enforced here:
  I1: no order reaches X (broker) without passing R (risk) and G (guard).
  I2: HALTED => zero orders.
  I3: user rejection => no execution.
  I4: every decision is written to Audit Memory (append-only).
  I5: agent output outside schema => WAIT.
"""
from __future__ import annotations

from enum import Enum


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


# Adjacency of legal transitions. KillSwitch can fire from ANY state (handled specially).
_TRANSITIONS: dict[State, set[State]] = {
    State.IDLE: {State.READING},
    State.READING: {State.CONTEXTING},
    State.CONTEXTING: {State.A1},
    State.A1: {State.A2},
    State.A2: {State.A3},
    State.A3: {State.AWAIT_VETO, State.WAITING, State.IDLE, State.REEVAL},
    State.AWAIT_VETO: {State.RISK_CHECK, State.WAITING},
    State.RISK_CHECK: {State.GUARD, State.WAITING},
    State.GUARD: {State.EXECUTING, State.WAITING},
    State.EXECUTING: {State.IDLE},
    State.WAITING: {State.IDLE},
    State.REEVAL: {State.READING},
    State.HALTED: {State.IDLE},  # only via explicit operator command
}


class IllegalTransition(RuntimeError):
    pass


class StateMachine:
    def __init__(self, on_transition=None, initial_state: State = State.IDLE):
        if not isinstance(initial_state, State):
            raise IllegalTransition("unknown initial state; fail closed")
        self.state: State = initial_state
        self.history: list[tuple[State, State]] = []
        self._on_transition = on_transition  # callback(from_state, to_state) for Observability/Audit

    def can(self, to_state: State) -> bool:
        if self.state == State.HALTED:
            return to_state == State.IDLE  # only explicit recovery
        return to_state in _TRANSITIONS.get(self.state, set())

    def go(self, to_state: State) -> None:
        if not self.can(to_state):
            raise IllegalTransition(f"{self.state} -> {to_state} is not a legal transition")
        prev = self.state
        self.state = to_state
        self.history.append((prev, to_state))
        if self._on_transition:
            self._on_transition(prev, to_state)

    def kill_switch(self, reason: str) -> None:
        """Absolute priority: fires from ANY state (SUPER_PROMPT §8, P-05)."""
        prev = self.state
        self.state = State.HALTED
        self.history.append((prev, State.HALTED))
        if self._on_transition:
            self._on_transition(prev, State.HALTED, reason=reason)  # type: ignore[call-arg]

    def recover_from_halt(self, operator_confirmed: bool) -> None:
        if self.state != State.HALTED:
            raise IllegalTransition("recover_from_halt only valid from HALTED")
        if not operator_confirmed:
            raise IllegalTransition("HALTED -> IDLE requires an explicit operator command (I2)")
        self.go(State.IDLE)
