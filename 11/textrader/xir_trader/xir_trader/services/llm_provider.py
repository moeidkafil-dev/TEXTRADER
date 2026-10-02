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
from typing import Any


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
        closes = [d.get("close") for d in data if isinstance(d, dict) and "close" in d]
        if not closes:
            return {
                "action": "WAIT", "instrument": instrument,
                "rationale": "no price data available in context",
                "assumptions": [], "evidence": [],
            }
        close = closes[0]
        open_ = next((d.get("open") for d in data if isinstance(d, dict) and "open" in d), close)
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
        }

    # -- Agent 2: adversarial check across all 9 failure categories --
    def _agent2(self, context: dict) -> dict:
        initial = context.get("initial_decision", {})
        data_section = context.get("data", {})
        paths = []

        def add(cat, desc, sev):
            paths.append({"category": cat, "description": desc, "severity": sev})

        add("wrong_prediction", "momentum signal has no statistical validation in this reference build", "med")
        add("logical_inconsistency", "none detected in rationale text" if initial.get("rationale") else "no rationale given", "low" if initial.get("rationale") else "high")
        missing = data_section.get("empty", False)
        add("missing_data", "one or more data sections empty" if missing else "no missing sections", "high" if missing else "low")
        add("invalid_assumption", "assumption 'momentum continues' is not guaranteed", "med")
        add("risk_violation", "not evaluated here; deferred to RiskEngine", "low")
        add("contradictory_evidence", "no contradictory evidence sources configured", "low")
        add("tool_failure", "no tool failures observed this cycle", "low")
        add("model_uncertainty", "reference provider is a rule stub, not a calibrated model", "med")
        add("execution_impossibility", "not evaluated here; deferred to ExecutionGuard/session check", "low")
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
