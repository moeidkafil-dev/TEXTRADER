"""Deterministic portfolio-aware position sizing.

The LLM can propose a trade, but it cannot override these calculations.
Quantity is derived from account equity, configured risk budget, stop distance,
price, fees/slippage allowance and exposure caps.
"""
from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True)
class SizingResult:
    quantity: float
    notional: float
    risk_amount: float
    risk_fraction: float
    stop_distance: float
    reason: str


def size_position(*, equity: float, price: float, stop_price: float,
                  risk_fraction: float = 0.005, max_exposure_fraction: float = 0.10,
                  max_position_size: float = 1000.0, fee_fraction: float = 0.001,
                  slippage_fraction: float = 0.001) -> SizingResult:
    if equity <= 0 or price <= 0 or stop_price <= 0:
        return SizingResult(0.0, 0.0, 0.0, risk_fraction, 0.0, "invalid equity/price/stop")
    stop_distance = abs(price - stop_price)
    if stop_distance <= 0:
        return SizingResult(0.0, 0.0, 0.0, risk_fraction, 0.0, "zero stop distance")
    risk_budget = equity * max(0.0, risk_fraction)
    # Approximate round-trip friction so the risk budget is not consumed by fees.
    per_unit_loss = stop_distance + price * max(0.0, fee_fraction + slippage_fraction)
    qty_by_risk = risk_budget / per_unit_loss
    qty_by_exposure = (equity * max(0.0, max_exposure_fraction)) / price
    qty = min(qty_by_risk, qty_by_exposure, max(0.0, max_position_size))
    notional = qty * price
    risk_amount = qty * per_unit_loss
    return SizingResult(qty, notional, risk_amount, risk_fraction, stop_distance,
                        "risk-budgeted; capped by exposure and max position")
