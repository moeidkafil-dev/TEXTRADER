"""Performance and risk metrics for paper/backtest reports."""
from __future__ import annotations
import math


def max_drawdown(equity_curve):
    peak = -float("inf"); mdd = 0.0
    for x in equity_curve:
        peak = max(peak, x)
        if peak > 0: mdd = max(mdd, (peak - x) / peak)
    return mdd


def summarize(returns, equity_curve=None):
    r = [float(x) for x in returns]
    if not r:
        return {"observations": 0}
    mean = sum(r) / len(r)
    var = sum((x - mean) ** 2 for x in r) / max(1, len(r) - 1)
    std = math.sqrt(var)
    downside = math.sqrt(sum(min(0.0, x) ** 2 for x in r) / len(r))
    wins = [x for x in r if x > 0]
    losses = [x for x in r if x < 0]
    gross_win = sum(wins); gross_loss = abs(sum(losses))
    out = {"observations": len(r), "mean_return": mean,
           "volatility": std, "sharpe_like": mean / std if std else 0.0,
           "sortino_like": mean / downside if downside else 0.0,
           "win_rate": len(wins) / len(r),
           "profit_factor": gross_win / gross_loss if gross_loss else float("inf"),
           "expectancy": mean}
    if equity_curve:
        out["max_drawdown"] = max_drawdown(equity_curve)
    return out
