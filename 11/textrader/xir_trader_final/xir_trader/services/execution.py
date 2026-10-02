"""
Execution Guard + Final Tools — 08_EXECUTION_MODEL/EXECUTION_MODEL.md, REQ-EX-*.

Final Tools = execution tools, NOT decision makers (buy_system / sell_system / skip).
Execution Guard sits between the Risk-approved order and the Broker adapter and is
the single choke point that turns a RiskResult into an actual broker call —
invariant I1 ("no order reaches X without passing R and G") is enforced by the
orchestrator only calling ExecutionGuard.submit() after RiskEngine.check() passed.
"""
from __future__ import annotations

import threading

from ..core.schemas import ExecutionOrder, RiskResult
from ..adapters.broker.base import BrokerAdapter, BrokerAck
from .db_manager import DBManager
from .observability import Observability
from .risk_engine import RiskEngine


class GuardRejection(RuntimeError):
    pass


class BrokerExecutionError(RuntimeError):
    pass


class ExecutionGuard:
    def __init__(self, broker: BrokerAdapter, db: DBManager, obs: Observability,
                 risk_engine: RiskEngine, safety_lock=None, allow_veto_silence: bool = False):
        self.broker = broker
        self.db = db
        self.obs = obs
        self.risk_engine = risk_engine
        self.allow_veto_silence = allow_veto_silence
        self.safety_lock = safety_lock or threading.RLock()

    def submit(self, order: ExecutionOrder, risk_result: RiskResult | None, system_state: str,
               human_stop: bool, trace_id: str) -> BrokerAck:
        with self.safety_lock:
            return self._submit_locked(order, risk_result, system_state, human_stop, trace_id)

    def _submit_locked(self, order: ExecutionOrder, risk_result: RiskResult | None, system_state: str,
                       human_stop: bool, trace_id: str) -> BrokerAck:
        try:
            order.validate()
        except Exception as exc:
            raise GuardRejection(f"invalid order rejected: {exc}") from exc
        persisted_state = self.db.get_system_state()
        if system_state != "EXECUTING" or persisted_state != "EXECUTING":
            raise GuardRejection(f"system state {system_state!r}/{persisted_state!r} is not EXECUTING")
        if human_stop:
            raise GuardRejection("human STOP/REJECT hold is active")
        if not self.risk_engine.verify_authorization(order, risk_result):
            self.obs.error(trace_id, msg="guard_rejected_missing_or_mismatched_risk_result", order_id=order.order_id)
            raise GuardRejection("authentic, complete, passing RiskEngine result for this exact order is required")
        veto_response = self.db.get_veto_response(order.order_id)
        if veto_response != "OK" and not (self.allow_veto_silence and veto_response == "SILENCE"):
            self.obs.error(trace_id, msg="guard_rejected_without_human_approval", order_id=order.order_id,
                           veto_response=veto_response)
            raise GuardRejection("an explicit recorded human OK is required before broker submission")

        if not self.db.reserve_order(order):
            self.obs.warn(trace_id, msg="guard_blocked_duplicate_order", order_id=order.order_id)
            raise GuardRejection("duplicate idempotency_key; order already exists")

        try:
            ack = self.broker.execute(order)
        except Exception as exc:
            self.db.update_order_status(order.order_id, "unknown")
            self.obs.audit("broker_execution_unknown", cycle_id=order.cycle_id, order_id=order.order_id,
                           idempotency_key=order.idempotency_key, error_type=type(exc).__name__)
            self.obs.error(trace_id, msg="broker_call_outcome_unknown", order_id=order.order_id,
                           error_type=type(exc).__name__)
            raise BrokerExecutionError("broker outcome is unknown; idempotency key remains reserved") from exc
        valid_ack = (isinstance(ack, BrokerAck) and ack.order_id == order.order_id
                     and ack.idempotency_key == order.idempotency_key
                     and ack.status in ("filled", "rejected"))
        if not valid_ack:
            self.db.update_order_status(order.order_id, "invalid_ack")
            self.obs.audit("broker_invalid_ack", cycle_id=order.cycle_id, order_id=order.order_id)
            raise BrokerExecutionError("broker returned an invalid or mismatched acknowledgement")
        self.db.update_order_status(order.order_id, ack.status)
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

    def buy_system(self, order: ExecutionOrder, risk_result: RiskResult | None, system_state: str,
                   human_stop: bool, trace_id: str) -> BrokerAck:
        if order.side != "BUY":
            raise GuardRejection("buy_system only accepts BUY orders")
        return self.guard.submit(order, risk_result, system_state, human_stop, trace_id)

    def sell_system(self, order: ExecutionOrder, risk_result: RiskResult | None, system_state: str,
                    human_stop: bool, trace_id: str) -> BrokerAck:
        if order.side != "SELL":
            raise GuardRejection("sell_system only accepts SELL orders")
        return self.guard.submit(order, risk_result, system_state, human_stop, trace_id)

    def skip(self, reason: str, trace_id: str) -> None:
        self.obs.info(trace_id, msg="skip", reason=reason)
        self.obs.audit("skip", reason=reason)
