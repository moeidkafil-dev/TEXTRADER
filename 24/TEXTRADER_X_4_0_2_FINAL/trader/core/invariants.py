"""
Invariants I1–I5 — chapter 04 SYSTEM_MODEL.md.

I1: No order reaches Broker without passing R (Risk) and G (Guard).
I2: HALTED state ⇒ zero orders pass.
I3: User reject ⇒ no execution.
I4: Every decision is written to Audit Memory (append-only).
I5: Agent output violating schema ⇒ WAIT.

The orchestrator consults these checks before and after every cycle step.
A violation is a runtime assertion failure — the system logs the breach to
observability with level=error and refuses the unsafe action. Live deployment
must never see I1/I2 violated.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from trader.core.schemas import (
    FinalDecision, InitialDecision, FailureReport, ExecutionOrder, RiskResult,
    is_valid_initial, is_valid_failure_report, is_valid_final, is_valid_order,
)


class InvariantViolation(Exception):
    def __init__(self, code: str, detail: str):
        self.code = code
        self.detail = detail
        super().__init__(f"[{code}] {detail}")


# I1 — order must pass risk + guard before broker
def assert_i1_risk_guard_passed(order: ExecutionOrder, risk: RiskResult,
                                guard_passed: bool) -> None:
    if not risk.passed:
        raise InvariantViolation("I1", f"order {order.order_id} did not pass Risk Engine")
    if not guard_passed:
        raise InvariantViolation("I1", f"order {order.order_id} did not pass Guard")


# I2 — halted ⇒ zero orders
def assert_i2_not_halted(is_halted: bool, order: ExecutionOrder | None) -> None:
    if is_halted and order is not None:
        raise InvariantViolation("I2", f"order {order.order_id} reached Broker while HALTED")


# I3 — user reject ⇒ no execution
def assert_i3_user_approved(user_response: str) -> None:
    if user_response not in ("SILENCE", "OK"):
        raise InvariantViolation("I3", f"user response {user_response!r} did not approve execution")


# I5 — schema validation ⇒ WAIT on failure
def enforce_i5_initial(d: InitialDecision) -> bool:
    """Return True if valid; False ⇒ orchestrator downgrades to WAIT."""
    return is_valid_initial(d)


def enforce_i5_failure(r: FailureReport) -> bool:
    return is_valid_failure_report(r)


def enforce_i5_final(d: FinalDecision) -> bool:
    return is_valid_final(d)


def enforce_i5_order(o: ExecutionOrder) -> bool:
    return is_valid_order(o)


# I4 — append-only audit; enforced by storage layer (audit_log table).
