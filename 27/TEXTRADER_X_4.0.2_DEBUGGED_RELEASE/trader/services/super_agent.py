"""Deterministic supervisory layer around the specialist agents.

This layer does not invent market facts. It synthesizes specialist outputs,
computes confidence from observable agreement/contradiction, and produces a
machine-checkable trade thesis for the execution layer.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Any


@dataclass(frozen=True)
class TradeThesis:
    action: str
    instrument: str
    confidence: float
    regime: str
    supporting_factors: tuple[str, ...]
    contradicting_factors: tuple[str, ...]
    invalidation: tuple[str, ...]
    rationale: str

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["supporting_factors"] = list(self.supporting_factors)
        d["contradicting_factors"] = list(self.contradicting_factors)
        d["invalidation"] = list(self.invalidation)
        return d


def synthesize(initial, failure_report, ctx) -> TradeThesis:
    md = ctx.section("market_data")
    instrument = initial.instrument
    supporting: list[str] = []
    contradicting: list[str] = []
    invalidation: list[str] = []
    regime = "UNKNOWN"
    if md and not md.empty:
        b = next((x for x in md.data.get("bundles", []) if "ohlcv" in x.get("payload", {})), None)
        if b:
            o = b["payload"]["ohlcv"]
            regime = "TREND_UP" if o["close"] > o["open"] else "TREND_DOWN" if o["close"] < o["open"] else "RANGE"
            supporting.append(f"closed-bar direction={regime}")
            invalidation.append("market structure no longer supports the thesis")
    for p in failure_report.paths:
        if p.severity in {"high", "blocking"}:
            contradicting.append(f"{p.category}: {p.description}")
    base = 0.65 if initial.action in {"BUY", "SELL"} else 0.0
    penalty = min(0.60, 0.08 * len(contradicting))
    confidence = max(0.0, min(0.99, base - penalty))
    if any(p.severity == "blocking" for p in failure_report.paths):
        confidence = 0.0
    return TradeThesis(initial.action, instrument, confidence, regime,
                       tuple(supporting), tuple(contradicting), tuple(invalidation),
                       initial.rationale)
