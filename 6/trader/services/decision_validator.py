"""
Decision Validator — chapter 03 C13 (n10) / REQ-DEC-02.

Validates the ExecutionOrder produced by Decision Engine BEFORE Risk Engine
runs. Reject ⇒ orchestrator goes to WAITING.

Checks:
- side ∈ {BUY, SELL}
- instrument non-empty and present in market data
- size > 0
- SL/TP present (per RiskConfig.require_stop_loss / require_take_profit)
- idempotency_key unique (duplicate ⇒ reject)
"""
from __future__ import annotations

from typing import Optional

from trader.core.schemas import ExecutionOrder, Context
from trader.core.config import RiskConfig
from trader.storage import repo


class DecisionValidator:
    def __init__(self, risk_config: RiskConfig, observability=None):
        self.rc = risk_config
        self._obs = observability

    def validate(self, order: ExecutionOrder, ctx: Context) -> tuple[bool, str]:
        if order.side not in ("BUY", "SELL"):
            return False, "invalid side"
        if not order.instrument or order.instrument == "UNKNOWN":
            return False, "instrument missing"
        if order.size <= 0:
            return False, "size must be > 0"
        if self.rc.require_stop_loss and order.sl <= 0:
            return False, "stop loss required but missing"
        if self.rc.require_take_profit and order.tp <= 0:
            return False, "take profit required but missing"
        # instrument present in market data?
        md = ctx.section("market_data")
        if md and not md.empty:
            symbols = {b["payload"]["instrument"]
                       for b in md.data.get("bundles", [])
                       if b.get("source", "").endswith("ohlcv")}
            if order.instrument not in symbols:
                return False, f"instrument {order.instrument} not in market data"
        # idempotency uniqueness
        try:
            existing = repo.get_order_by_idempotency(repo.get_db(), order.idempotency_key)
            if existing and existing.get("status") in ("filled", "submitted"):
                return False, "duplicate idempotency_key"
        except Exception:
            pass
        if self._obs:
            self._obs.info("decision_validator", trace_id=order.cycle_id,
                            data={"event": "validated", "order_id": order.order_id})
        return True, "ok"
