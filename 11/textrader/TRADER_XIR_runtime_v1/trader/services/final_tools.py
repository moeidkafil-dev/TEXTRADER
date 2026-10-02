"""
Final Tools — chapter 03 C17 (n5) / REQ-FT-01.

Three executable tools: `buy_system`, `sell_system`, `skip`.
These are NOT decision-makers — they only execute the broker-approved order
and record the result in DB + Observability.

`skip` ≡ WAIT: no action taken, no broker call. Recorded as a no-op result.
"""
from __future__ import annotations

from typing import Optional

from trader.adapters.broker.base import OrderRequest, BrokerAck
from trader.core.schemas import ExecutionOrder, ExecutionResult, OrderStatus


class FinalTools:
    def __init__(self, broker, observability=None):
        self._broker = broker
        self._obs = observability

    def buy_system(self, order: ExecutionOrder) -> ExecutionResult:
        return self._execute(order, side="BUY")

    def sell_system(self, order: ExecutionOrder) -> ExecutionResult:
        return self._execute(order, side="SELL")

    def skip(self, order: Optional[ExecutionOrder] = None) -> ExecutionResult:
        oid = order.order_id if order else "skip-noop"
        if self._obs:
            self._obs.info("final_tools.skip", trace_id=order.cycle_id if order else "skip",
                            data={"event": "skip"})
        return ExecutionResult(order_id=oid, status=OrderStatus.CANCELLED.value,
                                broker_ack="skip")

    def _execute(self, order: ExecutionOrder, side: str) -> ExecutionResult:
        if order.side != side:
            return ExecutionResult(order_id=order.order_id,
                                    status=OrderStatus.REJECTED.value,
                                    broker_ack=f"side mismatch: order={order.side} tool={side}")
        req = OrderRequest(
            order_id=order.order_id,
            idempotency_key=order.idempotency_key,
            side=order.side,
            instrument=order.instrument,
            size=order.size,
            sl=order.sl,
            tp=order.tp,
        )
        try:
            ack: BrokerAck = self._broker.submit(req)
        except Exception as e:
            if self._obs:
                self._obs.error("final_tools.broker_error", trace_id=order.cycle_id,
                                data={"event": "broker_exception", "error": str(e)})
            return ExecutionResult(order_id=order.order_id,
                                    status=OrderStatus.REJECTED.value,
                                    broker_ack=f"broker error: {e}")
        status = (OrderStatus.FILLED.value if ack.status == "filled"
                  else OrderStatus.SUBMITTED.value if ack.status == "submitted"
                  else OrderStatus.REJECTED.value)
        if self._obs:
            self._obs.info(f"final_tools.{side.lower()}_system", trace_id=order.cycle_id,
                            data={"event": "executed", "order_id": order.order_id,
                                   "status": status, "fill_price": ack.fill_price,
                                   "fill_size": ack.fill_size, "reason": ack.reason})
        return ExecutionResult(order_id=order.order_id, status=status,
                                fill_price=ack.fill_price,
                                fill_size=ack.fill_size,
                                broker_ack=ack.reason)
