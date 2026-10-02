"""
Execution Guard + Final Tools — 08_EXECUTION_MODEL/EXECUTION_MODEL.md, REQ-EX-*.

Final Tools = execution tools, NOT decision makers (buy_system / sell_system / skip).
Execution Guard sits between the Risk-approved order and the Broker adapter and is
the single choke point that turns a RiskResult into an actual broker call —
invariant I1 ("no order reaches X without passing R and G") is enforced by the
orchestrator only calling ExecutionGuard.submit() after RiskEngine.check() passed.
"""
from __future__ import annotations

from ..core.schemas import ExecutionOrder
from ..adapters.broker.base import BrokerAdapter, BrokerAck
from .db_manager import DBManager
from .observability import Observability


class GuardRejection(RuntimeError):
    pass


class ExecutionGuard:
    def __init__(self, broker: BrokerAdapter, db: DBManager, obs: Observability):
        self.broker = broker
        self.db = db
        self.obs = obs

    def submit(self, order: ExecutionOrder, risk_passed: bool, trace_id: str) -> BrokerAck:
        if not risk_passed:
            # Defense in depth: even if a caller mistakenly reaches Guard, it refuses (I1).
            self.obs.error(trace_id, msg="guard_rejected_unrisked_order", order_id=order.order_id)
            raise GuardRejection("order did not pass RiskEngine; refusing to submit")

        if self.db.order_exists(order.idempotency_key):
            self.obs.warn(trace_id, msg="guard_blocked_duplicate_order", order_id=order.order_id)
            raise GuardRejection("duplicate idempotency_key; order already exists")

        self.db.save_order(order, status="submitted")
        ack = self.broker.submit_order(order)
        self.db.save_order(order, status=ack.status)
        self.obs.info(trace_id, msg="guard_submitted_order", order_id=order.order_id,
                       broker=self.broker.name, status=ack.status)
        self.obs.audit("order_submitted", order_id=order.order_id, side=order.side,
                        instrument=order.instrument, size=order.size, broker_status=ack.status)
        return ack


class FinalTools:
    """buy_system / sell_system / skip — pure execution, no decision authority (SUPER_PROMPT §9)."""
    def __init__(self, guard: ExecutionGuard, obs: Observability):
        self.guard = guard
        self.obs = obs

    def buy_system(self, order: ExecutionOrder, risk_passed: bool, trace_id: str) -> BrokerAck:
        assert order.side == "BUY"
        return self.guard.submit(order, risk_passed, trace_id)

    def sell_system(self, order: ExecutionOrder, risk_passed: bool, trace_id: str) -> BrokerAck:
        assert order.side == "SELL"
        return self.guard.submit(order, risk_passed, trace_id)

    def skip(self, reason: str, trace_id: str) -> None:
        self.obs.info(trace_id, msg="skip", reason=reason)
        self.obs.audit("skip", reason=reason)
