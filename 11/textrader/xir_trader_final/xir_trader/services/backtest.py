"""Small deterministic, no-look-ahead execution simulator.

This evaluates an explicitly supplied signal callback and execution assumptions;
it does not validate that the signal is profitable or statistically sound.
Signals at bar i receive only bars strictly before i and execute at bar i's open.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable, Iterable


@dataclass(frozen=True)
class HistoricalBar:
    timestamp: float
    open: float
    high: float
    low: float
    close: float
    volume: float

    def validate(self) -> "HistoricalBar":
        values = (self.timestamp, self.open, self.high, self.low, self.close, self.volume)
        if any(not isinstance(v, (int, float)) or isinstance(v, bool) or not math.isfinite(v) for v in values):
            raise ValueError("bar values must be finite numbers")
        if min(self.open, self.high, self.low, self.close) <= 0 or self.volume < 0:
            raise ValueError("OHLC prices must be positive and volume non-negative")
        if self.high < max(self.open, self.close) or self.low > min(self.open, self.close) or self.low > self.high:
            raise ValueError("contradictory OHLC values")
        return self


@dataclass(frozen=True)
class BacktestConfig:
    initial_equity: float = 10_000.0
    position_units: float = 1.0
    fee_bps: float = 0.0
    slippage_bps: float = 0.0
    spread_bps: float = 0.0

    def __post_init__(self):
        for name in ("initial_equity", "position_units"):
            value = getattr(self, name)
            if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value) or value <= 0:
                raise ValueError(f"{name} must be finite and positive")
        for name in ("fee_bps", "slippage_bps", "spread_bps"):
            value = getattr(self, name)
            if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value) or value < 0:
                raise ValueError(f"{name} must be finite and non-negative")


def run_backtest(bars: Iterable[HistoricalBar], signal: Callable[[tuple[HistoricalBar, ...]], str],
                 config: BacktestConfig = BacktestConfig(), *, synthetic: bool = False) -> dict:
    data = tuple(bar.validate() for bar in bars)
    if any(data[i].timestamp >= data[i + 1].timestamp for i in range(len(data) - 1)):
        raise ValueError("historical bars must have strictly increasing timestamps")
    equity = config.initial_equity
    peak = equity
    max_drawdown = 0.0
    position = 0
    entry_equity = None
    completed = []
    total_fees = 0.0
    turnover = 0.0
    max_exposure = 0.0
    equity_curve = [equity]
    cost_rate = (config.fee_bps + config.slippage_bps + config.spread_bps / 2) / 10_000

    for index, bar in enumerate(data):
        history = data[:index]  # current/future bar is intentionally withheld from the signal
        choice = signal(history)
        if choice not in ("BUY", "SELL", "WAIT"):
            raise ValueError(f"strategy returned invalid action: {choice!r}")
        target = 1 if choice == "BUY" else -1 if choice == "SELL" else position

        # Mark existing exposure from previous close to this bar's open.
        if index and position:
            equity += position * config.position_units * (bar.open - data[index - 1].close)
        if target != position:
            traded_units = config.position_units * (abs(target - position))
            cost = traded_units * bar.open * cost_rate
            equity -= cost
            total_fees += cost
            turnover += traded_units * bar.open
            if position and entry_equity is not None:
                completed.append(equity - entry_equity)
                entry_equity = None
            if target:
                entry_equity = equity
            position = target
        if position:
            equity += position * config.position_units * (bar.close - bar.open)
            max_exposure = max(max_exposure, config.position_units * bar.close)
        peak = max(peak, equity)
        drawdown = (peak - equity) / peak if peak > 0 else 1.0
        max_drawdown = max(max_drawdown, drawdown)
        equity_curve.append(equity)

    # Liquidate at final close using the same documented cost model.
    if position and data:
        cost = config.position_units * data[-1].close * cost_rate
        equity -= cost
        total_fees += cost
        turnover += config.position_units * data[-1].close
        if entry_equity is not None:
            completed.append(equity - entry_equity)
        position = 0
        equity_curve.append(equity)
        peak = max(peak, equity)
        max_drawdown = max(max_drawdown, (peak - equity) / peak if peak > 0 else 1.0)

    wins = [p for p in completed if p > 0]
    losses = [p for p in completed if p < 0]
    bar_returns = [(equity_curve[i] - equity_curve[i - 1]) / equity_curve[i - 1]
                   for i in range(1, len(equity_curve)) if equity_curve[i - 1] > 0]
    mean = sum(bar_returns) / len(bar_returns) if bar_returns else 0.0
    variance = sum((r - mean) ** 2 for r in bar_returns) / len(bar_returns) if bar_returns else 0.0
    std = math.sqrt(variance)
    return {
        "available": bool(data), "synthetic": bool(synthetic), "bars": len(data),
        "initial_equity": config.initial_equity, "final_equity": equity,
        "pnl": equity - config.initial_equity,
        "return_fraction": (equity - config.initial_equity) / config.initial_equity,
        "max_drawdown": max_drawdown, "trades": len(completed),
        "wins": len(wins), "losses": len(losses),
        "win_rate": len(wins) / len(completed) if completed else None,
        "expectancy": sum(completed) / len(completed) if completed else None,
        "sharpe_like_unannualized": mean / std * math.sqrt(len(bar_returns)) if std else None,
        "fees_slippage_spread_cost": total_fees, "turnover": turnover,
        "max_exposure": max_exposure, "equity_curve": equity_curve,
        "performance_claim": "simulation only; not evidence of future profitability",
    }


def walk_forward_splits(bars: Iterable[HistoricalBar], train_fraction: float = 0.6,
                        validation_fraction: float = 0.2) -> dict:
    data = tuple(bars)
    if not 0 < train_fraction < 1 or not 0 < validation_fraction < 1 or train_fraction + validation_fraction >= 1:
        raise ValueError("fractions must be positive and leave a non-empty unseen test period")
    first = int(len(data) * train_fraction)
    second = int(len(data) * (train_fraction + validation_fraction))
    if first == 0 or second <= first or second >= len(data):
        raise ValueError("insufficient bars for non-empty development, validation, and test splits")
    return {"development": data[:first], "validation": data[first:second], "unseen_test": data[second:],
            "indices": {"development": (0, first), "validation": (first, second),
                        "unseen_test": (second, len(data))}}
