"""
Provider-agnostic LLM interface (OI-08: "مدل LLM هر ایجنت مشخص نشده" -> provider-agnostic).

Ship a deterministic, dependency-free RuleBasedProvider so the whole
runtime is runnable and testable with no external API key. Swap in a
real provider (Anthropic, OpenAI, local model, ...) by implementing
LLMProvider and passing it to the agents — no other code changes needed.

Whatever the provider returns is treated as untrusted output and is
always schema-validated by the caller before use (I5: invalid -> WAIT).
This is also the prompt-injection control from SECURITY_MODEL.md: market
data / news text reaching the provider is *data*, never instructions.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
import math


class LLMProvider(ABC):
    @abstractmethod
    def complete(self, *, role: str, context: dict) -> dict:
        """Return a plain dict matching the schema the caller expects
        (InitialDecision / FailureReport / FinalDecision shape, pre-validation)."""
        raise NotImplementedError


class RuleBasedProvider(LLMProvider):
    """A transparent, deterministic stand-in for an LLM: simple momentum rule for
    Agent 1, exhaustive checklist for Agent 2, conservative arbiter for Agent 3.
    This is intentionally NOT a trading strategy recommendation — it exists so the
    pipeline is runnable end-to-end without a live model or market opinion."""

    def complete(self, *, role: str, context: dict) -> dict:
        if role == "agent1":
            return self._agent1(context)
        if role == "agent2":
            return self._agent2(context)
        if role == "agent3":
            return self._agent3(context)
        raise ValueError(f"unknown role: {role}")

    # -- Agent 1: initial decision from a naive momentum signal on mock/real OHLCV --
    def _agent1(self, context: dict) -> dict:
        data = context.get("data", {}).get("value", [])
        instrument = context.get("instrument", "UNKNOWN")
        market = next((row.get("payload", {}) for row in data
                       if isinstance(row, dict) and row.get("critical") and row.get("quality") == "VALID"), None)
        if not isinstance(market, dict):
            return {
                "action": "WAIT", "instrument": instrument,
                "rationale": "critical market data missing, stale, or invalid",
                "assumptions": [], "evidence": [], "confidence": 0.0,
            }
        close = market.get("close")
        open_ = market.get("open")
        if any(not isinstance(v, (int, float)) or not math.isfinite(v) or v <= 0 for v in (close, open_)):
            return {"action": "WAIT", "instrument": instrument,
                    "rationale": "critical price values failed deterministic validation",
                    "assumptions": [], "evidence": [], "confidence": 0.0}
        momentum = (close - open_) / open_ if open_ else 0.0
        if momentum > 0.002:
            action = "BUY"
        elif momentum < -0.002:
            action = "SELL"
        else:
            action = "WAIT"
        return {
            "action": action,
            "instrument": instrument,
            "rationale": f"naive intrabar momentum={momentum:.5f}",
            "assumptions": ["recent momentum continues briefly"],
            "evidence": [f"close={close}", f"open={open_}"],
            "confidence": 0.25 if action != "WAIT" else 0.0,
        }

    # -- Agent 2: adversarial check across all 9 failure categories --
    def _agent2(self, context: dict) -> dict:
        initial = context.get("initial_decision", {})
        data_section = context.get("data", {})
        rows = data_section.get("value", [])
        paths = []

        def add(cat, desc, sev, *, found=False, blocking=False, evidence=None, assumption="", confidence=0.75):
            paths.append({"category": cat, "description": desc, "severity": sev,
                          "failure_found": found, "blocking": blocking, "evidence": evidence or [],
                          "counter_evidence": [], "assumption": assumption, "confidence": confidence})

        critical = [row for row in rows if isinstance(row, dict) and row.get("critical")]
        invalid_critical = [row for row in critical if row.get("quality") != "VALID"]
        bars = [r.get("payload", {}) for r in rows if isinstance(r, dict) and isinstance(r.get("payload"), dict)]
        direction = initial.get("action")
        assumptions = initial.get("assumptions", [])

        add("wrong_prediction", "No out-of-sample calibration or predictive validation is supplied; the signal may fail.",
            "high" if direction in ("BUY", "SELL") else "low", found=direction in ("BUY", "SELL"),
            evidence=["reference provider is a rule-based stub; no validation dataset supplied"])
        add("logical_inconsistency", "Agent 1 rationale is absent or too weak to substantiate its decision." if not initial.get("rationale") else "Check rationale against the signed price move; no deterministic contradiction identified.",
            "high" if not initial.get("rationale") else "low", found=not bool(initial.get("rationale")),
            evidence=[str(initial.get("rationale", "missing rationale"))])
        missing = not critical or bool(invalid_critical)
        add("missing_data", "No valid critical market-data bundle is available." if missing else "Critical market-data bundle passed freshness and shape validation.",
            "blocking" if missing else "low", found=missing, blocking=missing,
            evidence=[f"source={r.get('source')} quality={r.get('quality')}" for r in (invalid_critical or critical)])
        unsupported = [str(a) for a in assumptions if isinstance(a, str)]
        add("invalid_assumption", "Momentum continuation is not guaranteed and is not evidenced by this single observation.",
            "high" if direction in ("BUY", "SELL") else "low", found=bool(unsupported),
            evidence=unsupported or ["no explicit assumptions provided"],
            assumption="Recent direction persists into the next decision interval.")
        add("risk_violation", "Portfolio limits are not an agent judgment; deterministic RiskEngine must evaluate them before any order.",
            "low", found=False, evidence=["risk checks are deferred to deterministic RiskEngine"])
        contradictions = []
        for bar in bars:
            if all(k in bar for k in ("open", "close")) and isinstance(bar["open"], (int, float)) and isinstance(bar["close"], (int, float)):
                if direction == "BUY" and bar["close"] < bar["open"]:
                    contradictions.append("Agent 1 BUY conflicts with observed close below open")
                if direction == "SELL" and bar["close"] > bar["open"]:
                    contradictions.append("Agent 1 SELL conflicts with observed close above open")
        add("contradictory_evidence", "; ".join(contradictions) if contradictions else "No contradictory price direction found in the supplied single-bar evidence; cross-source confirmation is unavailable.",
            "high" if contradictions else "med", found=bool(contradictions), evidence=contradictions or ["one validated OHLC observation only"])
        add("tool_failure", "A data bundle reports a missing, stale, or invalid source." if invalid_critical else "No adapter failure was reported in the supplied context.",
            "high" if invalid_critical else "low", found=bool(invalid_critical), evidence=[str(r.get("source")) for r in invalid_critical] or ["adapter status inspected; no failure reported"])
        add("model_uncertainty", "The bundled rule-based provider is not a calibrated predictive model.", "med",
            found=True, evidence=["provider=RuleBasedProvider", "confidence is not empirically calibrated"])
        add("execution_impossibility", "Liquidity, spread, fees, slippage, venue status, and order constraints require external adapter evidence.",
            "med", found=True, evidence=[f"available sources={[r.get('source') for r in rows if isinstance(r, dict)]}"])
        return {"paths": paths}

    # -- Agent 3: final arbiter; conservative override on any blocking failure --
    def _agent3(self, context: dict) -> dict:
        initial = context.get("initial_decision", {})
        failure = context.get("failure_report", {})
        blocking = any(p.get("severity") == "blocking" for p in failure.get("paths", []))
        proposed = initial.get("action", "WAIT")
        if blocking:
            return {"decision": "WAIT", "overrode_initial": proposed != "WAIT",
                    "reason": "blocking failure path present -> conservative override to WAIT"}
        highs = [p for p in failure.get("paths", []) if p.get("severity") == "high"]
        if highs and proposed in ("BUY", "SELL"):
            return {"decision": "WAIT", "overrode_initial": True,
                    "reason": f"{len(highs)} high-severity failure path(s) -> WAIT pending re-evaluation"}
        return {"decision": proposed, "overrode_initial": False, "reason": "no blocking/high failure paths"}
