"""
Agent 3 — Final decision + override — chapter 03 C06 / REQ-AG-04, REQ-AG-05.

Receives InitialDecision + FailureReport. Output ∈ {BUY, SELL, WAIT,
RE-EVALUATE}. Has authority to override the initial decision; override must
be recorded (`overrode_initial=True`, `reason`).

Hard rule (chapter 06): if any failure category is `blocking`, Agent 3 cannot
issue BUY/SELL unless it records a justification. Mock policy: blocking ⇒
WAIT or RE-EVALUATE (depending on category). Override examples:
  BUY → WAIT (after F3 missing_data blocking)
  BUY → RE-EVALUATE (after F9 execution_impossibility blocking)
  BUY → SELL (rare; only if contradictory_evidence high + no blocking)

RE-EVALUATE ⇒ orchestrator starts a new cycle from Data Reader (chapter 04).
"""
from __future__ import annotations

import json
from typing import Any

from trader.core.schemas import (
    Context, FinalDecision, InitialDecision, FailureReport, FailureCategory, Severity, Action,
)
from trader.services.agent_base import AgentBase


SYSTEM_PROMPT = """You are Agent 3 of the TRADER (XIR) system — final decision maker.
You receive InitialDecision and FailureReport. Output STRICT JSON only:
{"decision":"BUY|SELL|WAIT|RE-EVALUATE","overrode_initial":true|false,"reason":"..."}
Hard rule: if any failure path has severity 'blocking', you MUST NOT issue
BUY or SELL unless you record an explicit justification in 'reason'.
"""


class Agent3(AgentBase):
    AGENT_ID = "agent3"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, agent_id="agent3", **kwargs)

    def run(self, ctx: Context, initial: InitialDecision, report: FailureReport) -> FinalDecision:
        self._initial = initial
        self._report = report
        decision = self._run_parts(ctx, SYSTEM_PROMPT,
                                    lambda compiled, ctx: self._build_user(compiled, ctx, initial, report))
        # Coerce into FinalDecision schema
        try:
            d = decision["decision"]
            if d not in Action.final_values():
                d = Action.WAIT.value
            overrode = bool(decision.get("overrode_initial", False))
            reason = str(decision.get("reason", ""))
            return FinalDecision(cycle_id=ctx.cycle_id, decision=d,
                                 overrode_initial=overrode, reason=reason)
        except Exception as e:
            self._obs.error(self.agent_id, trace_id=ctx.cycle_id,
                            data={"event": "invalid_final_output", "error": str(e)})
            return FinalDecision(cycle_id=ctx.cycle_id, decision=Action.WAIT.value,
                                 overrode_initial=True,
                                 reason=f"agent3 invalid output: {e}")

    def _build_user(self, compiled, ctx, initial, report) -> str:
        return (
            f"InitialDecision:\n{json.dumps(initial.to_dict(), indent=2)}\n\n"
            f"FailureReport:\n{json.dumps(report.to_dict(), indent=2)}\n\n"
            f"Context compiled:\n{compiled}\n\n"
            f"Produce your FinalDecision JSON."
        )

    def _part_decision_system(self, raw: str, ctx: Context) -> dict:
        # Try JSON parse
        try:
            d = json.loads(raw)
            if isinstance(d, dict) and "decision" in d:
                return d
        except Exception:
            pass
        # Mock policy: enforce hard rule on blocking categories.
        initial: InitialDecision = getattr(self, "_initial", None)
        report: FailureReport = getattr(self, "_report", None)
        if not initial or not report:
            return {"decision": "WAIT", "overrode_initial": True, "reason": "missing inputs"}
        blocking = [p for p in report.paths if p.severity == Severity.BLOCKING.value]
        blocking_categories = {p.category for p in blocking}
        decision = initial.action
        overrode = False
        reason = "no blocking failures; accepting initial"
        if blocking:
            # Override logic:
            if FailureCategory.F3_MISSING_DATA.value in blocking_categories:
                decision = "WAIT"
                overrode = initial.action in ("BUY", "SELL")
                reason = "F3 missing_data blocking ⇒ WAIT until data restored"
            elif FailureCategory.F9_EXECUTION_IMPOSSIBILITY.value in blocking_categories:
                decision = "RE-EVALUATE"
                overrode = True
                reason = "F9 execution_impossibility blocking ⇒ RE-EVALUATE from Data Reader"
            else:
                decision = "WAIT"
                overrode = initial.action in ("BUY", "SELL")
                reason = f"blocking failure(s) in {sorted(blocking_categories)} ⇒ WAIT"
        else:
            # No blocking; check high-severity F6 contradictory_evidence
            for p in report.paths:
                if (p.category == FailureCategory.F6_CONTRADICTORY_EVIDENCE.value
                        and p.severity == Severity.HIGH.value
                        and initial.action == "BUY"):
                    decision = "WAIT"
                    overrode = True
                    reason = "F6 contradictory_evidence high ⇒ downgrade BUY→WAIT"
                    break
                if (p.category == FailureCategory.F6_CONTRADICTORY_EVIDENCE.value
                        and p.severity == Severity.HIGH.value
                        and initial.action == "SELL"):
                    decision = "WAIT"
                    overrode = True
                    reason = "F6 contradictory_evidence high ⇒ downgrade SELL→WAIT"
                    break
        return {"decision": decision, "overrode_initial": overrode, "reason": reason}
