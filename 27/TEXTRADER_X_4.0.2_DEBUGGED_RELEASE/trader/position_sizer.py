"""Backward-compatible public API for position sizing."""
from __future__ import annotations

import math
from typing import Any

from .services.position_sizer import SizingResult, size_position


class PositionSizer:
    """Compatibility facade over the deterministic ``size_position`` function.

    Full sizing parameters may be supplied at construction time. ``calculate``
    accepts either the historical scalar input or explicit keyword parameters.
    Invalid scalar inputs fail closed and return zero quantity.
    """

    def __init__(
        self,
        *,
        price: float = 1.0,
        stop_price: float = 0.99,
        risk_fraction: float = 0.005,
        max_exposure_fraction: float = 0.10,
        max_position_size: float = 1000.0,
        fee_fraction: float = 0.001,
        slippage_fraction: float = 0.001,
    ):
        self.defaults = {
            "price": price,
            "stop_price": stop_price,
            "risk_fraction": risk_fraction,
            "max_exposure_fraction": max_exposure_fraction,
            "max_position_size": max_position_size,
            "fee_fraction": fee_fraction,
            "slippage_fraction": slippage_fraction,
        }

    def calculate(self, equity: float, **overrides: Any) -> SizingResult:
        if not isinstance(equity, (int, float)) or not math.isfinite(float(equity)) or equity <= 0:
            return SizingResult(0.0, 0.0, 0.0,
                                float(self.defaults["risk_fraction"]),
                                0.0, "invalid equity")
        params = {**self.defaults, **overrides, "equity": float(equity)}
        return size_position(**params)


__all__ = ["PositionSizer", "SizingResult", "size_position"]
