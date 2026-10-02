"""
Execution Guard — chapter 03 C15 (n12) / REQ-EG-01.

Last guard before Broker/Exchange. Only an order that:
- passed Risk Engine (I1)
- was approved by user (veto OK or silence; I3)
- is NOT in HALTED state (I2)
- has a unique idempotency key (P-04)
passes through.

The guard enforces idempotency at the broker level too: a second submission
with the same key is rejected by the broker adapter.
"""
from __future__ import annotations

from typing import Optional

from trader.core.schemas import ExecutionOrder, RiskResult, VetoEvent, VetoResponse
from trader.services.kill_switch import KillSwitch


class ExecutionGuard:
    def __init__(self, kill_switch: KillSwitch, observability=None):
        self._ks = kill_switch
        self._obs = observability
        self._seen_idempotency: set[str] = set()

    def allow(self, order: ExecutionOrder, risk_result: RiskResult,
              veto: VetoEvent) -> tuple[bool, str]:
        # I2 — Kill switch / HALTED
        if self._ks.is_active:
            return False, "kill_switch active (HALTED)"
        # I1 — Risk passed
        if not risk_result.passed:
            return False, f"risk rejected: {risk_result.rejected_by()}"
        # I3 — User approved (OK or silence)
        if veto.response not in (VetoResponse.OK.value, VetoResponse.SILENCE.value):
            return False, f"user {veto.response}"
        # Idempotency (P-04)
        if order.idempotency_key in self._seen_idempotency:
            return False, "duplicate idempotency_key (guard)"
        self._seen_idempotency.add(order.idempotency_key)
        if self._obs:
            self._obs.info("execution_guard", trace_id=order.cycle_id,
                            data={"event": "allow", "order_id": order.order_id})
        return True, "ok"
