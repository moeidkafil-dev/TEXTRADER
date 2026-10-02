"""
Agent 2 — Adversarial failure finder — chapter 03 C05 / REQ-AG-03.

Receives InitialDecision + Context. Must explicitly report status for all 9
failure categories F1..F9. A missing category must be reported as
`model_uncertainty` (F8) — not omitted. The report is the basis Agent 3 uses
to decide override / pass / WAIT / RE-EVALUATE.

Mock policy: deterministic heuristics that flag common failure modes for each
category, scaled by signal strength. Real LLMs replace this with their own
analysis — the validation contract (all 9 categories present) is the same.
"""
from __future__ import annotations

import json
from typing import Any

from trader.core.schemas import (
    Context, FailureReport, FailurePath, InitialDecision, FailureCategory, Severity,
)
from trader.services.agent_base import AgentBase


SYSTEM_PROMPT = """You are Agent 2 of the TRADER (XIR) system — adversarial critic.
You receive an InitialDecision and the context. Your job: try HARD to find ALL
ways the decision could fail. Cover ALL 9 categories explicitly:
  wrong_prediction, logical_inconsistency, missing_data, invalid_assumption,
  risk_violation, contradictory_evidence, tool_failure, model_uncertainty,
  execution_impossibility.
Output STRICT JSON only:
{"paths":[{"category":"<one_of_9>","description":"...","severity":"low|med|high|blocking"}, ...]}
Every missing category MUST be reported as model_uncertainty.
"""


class Agent2(AgentBase):
    AGENT_ID = "agent2"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, agent_id="agent2", **kwargs)

    def run(self, ctx: Context, initial: InitialDecision) -> FailureReport:
        # stash initial so _part_decision_system can read it
        self._initial = initial
        decision = self._run_parts(ctx, SYSTEM_PROMPT,
                                    lambda compiled, ctx: self._build_user(compiled, ctx, initial))
        # Coerce into FailureReport schema
        try:
            paths_in = decision.get("paths", [])
            paths: list[FailurePath] = []
            for p in paths_in:
                paths.append(FailurePath(category=p["category"],
                                          description=p.get("description", ""),
                                          severity=p.get("severity", "low")))
            # Guarantee all 9 categories present; missing ⇒ F8 model_uncertainty
            covered = {p.category for p in paths}
            for c in FailureCategory.all():
                if c.value not in covered:
                    paths.append(FailurePath(
                        category=FailureCategory.F8_MODEL_UNCERTAINTY.value,
                        description=f"category {c.value} not explicitly analyzed",
                        severity=Severity.MED.value,
                    ))
            return FailureReport(cycle_id=ctx.cycle_id, paths=tuple(paths))
        except Exception as e:
            self._obs.error(self.agent_id, trace_id=ctx.cycle_id,
                            data={"event": "invalid_failure_report", "error": str(e)})
            # Fall back: all-9-as-model_uncertainty (still satisfies the contract)
            paths = tuple(FailurePath(
                category=FailureCategory.F8_MODEL_UNCERTAINTY.value,
                description=f"agent2 parse failure: {e}",
                severity=Severity.HIGH.value,
            ) for _ in FailureCategory.all())
            return FailureReport(cycle_id=ctx.cycle_id, paths=paths)

    def _build_user(self, compiled: str, ctx: Context, initial: InitialDecision) -> str:
        return (
            f"InitialDecision:\n{json.dumps(initial.to_dict(), indent=2)}\n\n"
            f"Context compiled:\n{compiled}\n\n"
            f"Produce your FailureReport JSON covering all 9 categories."
        )

    def _part_decision_system(self, raw: str, ctx: Context) -> dict:
        # Try JSON parse for real LLMs
        try:
            d = json.loads(raw)
            if isinstance(d, dict) and "paths" in d:
                return d
        except Exception:
            pass
        # Mock fallback: deterministic heuristics
        initial = getattr(self, "_initial", None)
        paths: list[dict] = []
        md = ctx.section("market_data")
        mem = ctx.section("memory")
        ucfg = ctx.section("user_config")
        # data quality?
        missing_data = False
        if md and md.empty:
            missing_data = True
        if md and not md.empty:
            for b in md.data.get("bundles", []):
                if b.get("quality") == "missing":
                    missing_data = True
                    break
        # F1 wrong_prediction — moderate by default (mock can't know)
        paths.append({"category": "wrong_prediction",
                       "description": "direction call may be wrong; no edge measurement available",
                       "severity": "med"})
        # F2 logical_inconsistency — check assumptions present
        if initial and not initial.assumptions:
            paths.append({"category": "logical_inconsistency",
                           "description": "no assumptions listed in initial decision",
                           "severity": "med"})
        else:
            paths.append({"category": "logical_inconsistency",
                           "description": "assumptions exist but logical chain not explicitly justified",
                           "severity": "low"})
        # F3 missing_data
        paths.append({"category": "missing_data",
                       "description": "market_data section has missing bundles" if missing_data
                                       else "no missing bundles detected",
                       "severity": "blocking" if missing_data else "low"})
        # F4 invalid_assumption — check instrument exists in context
        if initial and md and not md.empty:
            symbols = {b["payload"]["instrument"]
                       for b in md.data.get("bundles", [])
                       if b.get("source", "").endswith("ohlcv")}
            if initial.instrument not in symbols:
                paths.append({"category": "invalid_assumption",
                               "description": f"instrument {initial.instrument} not in market data: {symbols}",
                               "severity": "high"})
            else:
                paths.append({"category": "invalid_assumption",
                               "description": "instrument present; assumptions consistent",
                               "severity": "low"})
        else:
            paths.append({"category": "invalid_assumption",
                           "description": "cannot verify assumptions; no market data",
                           "severity": "med"})
        # F5 risk_violation — deferred to Risk Engine; Agent 2 only flags the gap
        paths.append({"category": "risk_violation",
                       "description": "Risk Engine check pending; cannot pre-judge numeric violations",
                       "severity": "low"})
        # F6 contradictory_evidence — news sentiment vs price action
        if md and not md.empty:
            news_b = next((b for b in md.data.get("bundles", [])
                           if b.get("source", "").endswith("news")), None)
            ohlcv_b = next((b for b in md.data.get("bundles", [])
                            if b.get("source", "").endswith("ohlcv")), None)
            if news_b and ohlcv_b and initial:
                o = ohlcv_b["payload"]["ohlcv"]
                news_sent = news_b["payload"].get("sentiment", 0)
                price_action_up = o["close"] > o["open"]
                if news_sent < 0 and price_action_up and initial.action == "BUY":
                    paths.append({"category": "contradictory_evidence",
                                   "description": "negative news vs BUY bias",
                                   "severity": "high"})
                elif news_sent > 0 and not price_action_up and initial.action == "SELL":
                    paths.append({"category": "contradictory_evidence",
                                   "description": "positive news vs SELL bias",
                                   "severity": "high"})
                else:
                    paths.append({"category": "contradictory_evidence",
                                   "description": "news and price action broadly consistent",
                                   "severity": "low"})
            else:
                paths.append({"category": "contradictory_evidence",
                               "description": "insufficient evidence to compare",
                               "severity": "med"})
        else:
            paths.append({"category": "contradictory_evidence",
                           "description": "no market data to check",
                           "severity": "med"})
        # F7 tool_failure — no tools called yet in agents; mark low
        paths.append({"category": "tool_failure",
                       "description": "no agent-side tools invoked yet",
                       "severity": "low"})
        # F8 model_uncertainty — always at least low (we can't measure LLM calibration)
        paths.append({"category": "model_uncertainty",
                       "description": "no calibrated probability estimate attached to initial decision",
                       "severity": "med"})
        # F9 execution_impossibility — liquidity/order book check
        if md and not md.empty:
            book_b = next((b for b in md.data.get("bundles", [])
                           if b.get("source", "").endswith("orderbook")), None)
            if book_b:
                bids = book_b["payload"]["order_book"]["bids"]
                asks = book_b["payload"]["order_book"]["asks"]
                if not bids or not asks:
                    paths.append({"category": "execution_impossibility",
                                   "description": "empty order book one side",
                                   "severity": "blocking"})
                else:
                    paths.append({"category": "execution_impossibility",
                                   "description": "order book has liquidity both sides",
                                   "severity": "low"})
            else:
                paths.append({"category": "execution_impossibility",
                               "description": "no order book data; cannot assess liquidity",
                               "severity": "med"})
        else:
            paths.append({"category": "execution_impossibility",
                           "description": "no market data at all",
                           "severity": "blocking"})
        return {"paths": paths}
