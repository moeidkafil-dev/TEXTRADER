"""
Agent 1 — Initial decision (BUY/SELL/WAIT) — chapter 03 C04 / REQ-AG-02.

System prompt instructs the LLM to analyze the context and produce a single
InitialDecision. Output is validated against the schema; failure ⇒ the
orchestrator downgrades to WAIT (invariant I5).

The mock LLM does NOT actually parse "reasoning"; instead, the agent applies a
small deterministic policy over the context (last close, simple momentum,
volatility, sentiment). Real LLMs replace this by producing the JSON
themselves — the validation contract is identical.
"""
from __future__ import annotations

import json
from typing import Any

from trader.core.schemas import (
    Context, InitialDecision, FailureCategory, Action,
)
from trader.services.agent_base import AgentBase


SYSTEM_PROMPT = """You are Agent 1 of the TRADER (XIR) system.
Your job: analyze the market context and produce an InitialDecision with a
single action in {BUY, SELL, WAIT}. Output STRICT JSON only:
{"action":"BUY|SELL|WAIT","instrument":"<symbol>","rationale":"<short>",
 "assumptions":[...],"evidence":[...]}
Do not invent data. Cite section names from the context as evidence. If a
section is empty, mention it as an assumption. Never produce RE-EVALUATE.
"""


class Agent1(AgentBase):
    AGENT_ID = "agent1"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, agent_id="agent1", **kwargs)

    def run(self, ctx: Context) -> InitialDecision:
        decision_dict = self._run_parts(ctx, SYSTEM_PROMPT, self._build_user)
        # Convert to InitialDecision schema
        try:
            action = decision_dict["action"]
            instrument = decision_dict["instrument"]
            rationale = decision_dict.get("rationale", "")
            assumptions = tuple(decision_dict.get("assumptions", []))
            evidence = tuple(decision_dict.get("evidence", []))
            return InitialDecision(cycle_id=ctx.cycle_id, action=action,
                                   instrument=instrument, rationale=rationale,
                                   assumptions=assumptions, evidence=evidence)
        except Exception as e:
            # I5: invalid output ⇒ WAIT
            self._obs.warn(self.agent_id, trace_id=ctx.cycle_id,
                           data={"event": "invalid_initial_output", "error": str(e)})
            return InitialDecision(cycle_id=ctx.cycle_id, action=Action.WAIT.value,
                                   instrument=ctx.section("market_data").data["bundles"][0]["payload"]["instrument"]
                                       if ctx.section("market_data") and not ctx.section("market_data").empty
                                       else "UNKNOWN",
                                   rationale=f"agent1 invalid output: {e}",
                                   assumptions=(), evidence=())

    def _build_user(self, compiled: str, ctx: Context) -> str:
        return (
            f"Context compiled:\n{compiled}\n\n"
            f"Produce your InitialDecision JSON now."
        )

    # ---- decision_system: parse LLM output OR apply deterministic policy for mock ----
    def _part_decision_system(self, raw: str, ctx: Context) -> dict:
        # Try to parse the raw LLM output as JSON (real LLMs)
        try:
            d = json.loads(raw)
            if isinstance(d, dict) and "action" in d:
                return d
        except Exception:
            pass
        # Mock LLM fallback: deterministic policy
        md = ctx.section("market_data")
        action = "WAIT"
        instrument = "UNKNOWN"
        rationale = "no market data"
        if md and not md.empty:
            bundles = md.data.get("bundles", [])
            ohlcv_b = next((b for b in bundles
                            if b.get("source", "").endswith("ohlcv")
                            or isinstance(b.get("payload"), dict) and "ohlcv" in b.get("payload", {})), None)
            news_b = next((b for b in bundles
                           if b.get("source", "").endswith("news")), None)
            if ohlcv_b:
                inst = ohlcv_b["payload"]["instrument"]
                o = ohlcv_b["payload"]["ohlcv"]
                instrument = inst
                # Simple momentum: close > open ⇒ BUY bias; < ⇒ SELL bias; flat ⇒ WAIT.
                # Confidence scaled by range (high-low)/open.
                o_, h, l, c = o["open"], o["high"], o["low"], o["close"]
                rng = (h - l) / max(o_, 1e-9)
                if c > o_ * 1.001:
                    action = "BUY"
                    rationale = f"close {c} > open {o_}; range {rng:.3f}"
                elif c < o_ * 0.999:
                    action = "SELL"
                    rationale = f"close {c} < open {o_}; range {rng:.3f}"
                else:
                    action = "WAIT"
                    rationale = f"flat: open={o_} close={c}"
                # Negative news sentiment flips BUY→WAIT
                if news_b and news_b["payload"].get("sentiment", 0) < 0 and action == "BUY":
                    action = "WAIT"
                    rationale += "; news sentiment negative flipped BUY→WAIT"
        return {
            "action": action,
            "instrument": instrument,
            "rationale": rationale,
            "assumptions": ["mock_llm_policy", "no_look_ahead"],
            "evidence": ["market_data", "memory", "user_config"],
        }
