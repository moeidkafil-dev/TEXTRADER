"""Decision-to-order translation with deterministic risk-based sizing."""
from __future__ import annotations
from typing import Optional
from trader.core.schemas import FinalDecision, ExecutionOrder, Context, Side
from trader.core.util import short_id
from trader.services.position_sizer import size_position


class DecisionEngine:
    def __init__(self, observability=None, default_size: float | None = 1.0,
                 sl_pct: float = 0.01, tp_pct: float = 0.02,
                 risk_config=None, risk_fraction: float = 0.005,
                 max_exposure_fraction: float = 0.10):
        self._obs = observability
        self.default_size = default_size
        self.sl_pct = sl_pct
        self.tp_pct = tp_pct
        self.risk_config = risk_config
        self.risk_fraction = risk_fraction
        self.max_exposure_fraction = max_exposure_fraction

    def to_order(self, decision: FinalDecision, ctx: Context,
                 ref_price: Optional[float] = None) -> Optional[ExecutionOrder]:
        if decision.decision not in (Side.BUY.value, Side.SELL.value):
            return None
        md = ctx.section("market_data")
        instrument = "UNKNOWN"
        if md and not md.empty:
            for b in md.data.get("bundles", []):
                if "ohlcv" in b.get("payload", {}):
                    instrument = b["payload"]["instrument"]
                    ref_price = ref_price or b["payload"]["ohlcv"]["close"]
                    break
        if ref_price is None or ref_price <= 0:
            return None
        side = decision.decision
        sl = round(ref_price * (1 - self.sl_pct), 8) if side == Side.BUY.value else round(ref_price * (1 + self.sl_pct), 8)
        tp = round(ref_price * (1 + 2*self.sl_pct), 8) if side == Side.BUY.value else round(ref_price * (1 - 2*self.sl_pct), 8)

        # Explicit default_size remains a compatibility/testing escape hatch.
        # Production orchestrator sets it to None and therefore uses portfolio-aware sizing.
        if self.default_size is not None:
            size = float(self.default_size)
            sizing_reason = "explicit_size_override"
        else:
            ps = ctx.section("market_state")
            state = ps.data if ps and not ps.empty else {}
            equity = float(state.get("equity", 0.0) or 0.0)
            max_pos = getattr(self.risk_config, "max_position_size", 1000.0)
            s = size_position(equity=equity, price=float(ref_price), stop_price=sl,
                              risk_fraction=self.risk_fraction,
                              max_exposure_fraction=self.max_exposure_fraction,
                              max_position_size=max_pos)
            size = s.quantity
            sizing_reason = s.reason
            if size <= 0:
                return None
        order = ExecutionOrder(idempotency_key=short_id("ik_"), cycle_id=decision.cycle_id,
                               side=side, instrument=instrument, size=size, sl=sl, tp=tp)
        if self._obs:
            self._obs.info("decision_engine", trace_id=decision.cycle_id,
                           data={"event":"order_built","order_id":order.order_id,
                                 "side":side,"instrument":instrument,"size":size,
                                 "sl":sl,"tp":tp,"sizing":sizing_reason})
        return order
