"""
Decision Engine — chapter 03 C12 (n9) / REQ-DEC-01.

Converts a FinalDecision ∈ {BUY, SELL} into a structured ExecutionOrder
(satisfying ExecutionOrder schema from chapter 04). WAIT/RE-EVALUATE never
produce an order.

This engine is LLM-free in this runtime (chapter 06 risk rule: deterministic
numeric checks only — REQ-P-03); the engine only transforms the decision into
the execution contract. Size and SL/TP are derived from the context's user
config and the order book midpoint.
"""
from __future__ import annotations

from typing import Optional

from trader.core.schemas import FinalDecision, ExecutionOrder, Context, Side
from trader.core.util import short_id


class DecisionEngine:
    def __init__(self, observability=None,
                 default_size: float = 1.0,
                 sl_pct: float = 0.01,
                 tp_pct: float = 0.02):
        self._obs = observability
        self.default_size = default_size
        self.sl_pct = sl_pct
        self.tp_pct = tp_pct

    def to_order(self, decision: FinalDecision, ctx: Context,
                 ref_price: Optional[float] = None) -> Optional[ExecutionOrder]:
        if decision.decision not in (Side.BUY.value, Side.SELL.value):
            return None
        # find instrument + ref price from context
        md = ctx.section("market_data")
        instrument = "UNKNOWN"
        if md and not md.empty:
            for b in md.data.get("bundles", []):
                if b.get("source", "").endswith("ohlcv"):
                    instrument = b["payload"]["instrument"]
                    ref_price = ref_price or b["payload"]["ohlcv"]["close"]
                    break
        if ref_price is None or ref_price <= 0:
            ref_price = 100.0  # synthetic fallback for paper mode
        side = decision.decision
        if side == Side.BUY.value:
            sl = round(ref_price * (1 - self.sl_pct), 6)
            tp = round(ref_price * (1 + self.tp_pct), 6)
        else:
            sl = round(ref_price * (1 + self.sl_pct), 6)
            tp = round(ref_price * (1 - self.tp_pct), 6)
        order = ExecutionOrder(
            idempotency_key=short_id("ik_"),
            cycle_id=decision.cycle_id,
            side=side,
            instrument=instrument,
            size=self.default_size,
            sl=sl,
            tp=tp,
        )
        if self._obs:
            self._obs.info("decision_engine", trace_id=decision.cycle_id,
                            data={"event": "order_built",
                                   "order_id": order.order_id,
                                   "side": side, "instrument": instrument,
                                   "size": self.default_size, "sl": sl, "tp": tp})
        return order
