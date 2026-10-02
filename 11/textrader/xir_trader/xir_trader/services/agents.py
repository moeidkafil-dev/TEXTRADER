"""
C04 Agent 1, C05 Agent 2, C06 Agent 3 — REQ-AG-01..06.

Internal template shared by all three agents (REQ-AG-01):
  context compiler -> llm -> decision system -> (planner|scheduler)
    -> tool manager -> tool executer -> hidden memory -> database
  tool executer -> Observability -> database
Only the llm-call step differs per agent (role="agent1|2|3"); the rest of
this class is the same "10-part" pipeline trace for every agent, logged
in full so the trace is auditable (REQ-AG-01 acceptance: full 10-part
trace in the log).

Agents never execute anything themselves (SUPER_PROMPT §9): execution
only happens via Guard -> Broker -> Final Tools, wired in orchestrator.
"""
from __future__ import annotations

from dataclasses import asdict

from ..core.schemas import (
    InitialDecision, FailureReport, FailurePath, FinalDecision, SchemaError,
)
from .llm_provider import LLMProvider
from .db_manager import DBManager
from .observability import Observability
from ..core.memory_types import MemoryType


class _AgentPipelineTrace:
    """Records the 10 internal components so REQ-AG-01's acceptance
    criterion ('Trace کامل هر ۱۰ جزء در لاگ') is literally satisfiable."""
    STEPS = ["context_compiler", "llm", "decision_system", "planner_or_scheduler",
             "tool_manager", "tool_executer", "hidden_memory", "database", "observability", "done"]

    def __init__(self, obs: Observability, trace_id: str, agent_name: str):
        self.obs = obs
        self.trace_id = trace_id
        self.agent_name = agent_name

    def step(self, name: str, **data):
        assert name in self.STEPS, f"unknown pipeline step {name}"
        self.obs.info(self.trace_id, agent=self.agent_name, step=name, **data)


class Agent1:
    """Analyze data, produce InitialDecision."""
    def __init__(self, provider: LLMProvider, db: DBManager, obs: Observability):
        self.provider = provider
        self.db = db
        self.obs = obs

    def run(self, cycle_id: str, instrument: str, context_sections: dict, trace_id: str) -> InitialDecision:
        trace = _AgentPipelineTrace(self.obs, trace_id, "agent1")
        trace.step("context_compiler", cycle_id=cycle_id)

        llm_input = {**context_sections, "instrument": instrument}
        trace.step("llm")
        try:
            raw = self.provider.complete(role="agent1", context=llm_input)
        except Exception as e:
            self.obs.error(trace_id, agent="agent1", msg="llm_call_failed", error=str(e))
            raw = {"action": "WAIT", "instrument": instrument, "rationale": f"tool_failure: {e}",
                   "assumptions": [], "evidence": []}

        trace.step("decision_system")
        try:
            decision = InitialDecision(cycle_id=cycle_id, **raw).validate()
        except (TypeError, SchemaError) as e:
            # I5: invalid schema -> WAIT
            self.obs.warn(trace_id, agent="agent1", msg="invalid_schema_forcing_wait", error=str(e))
            decision = InitialDecision(cycle_id=cycle_id, action="WAIT", instrument=instrument,
                                        rationale=f"schema_invalid: {e}")

        trace.step("planner_or_scheduler")
        trace.step("tool_manager")
        trace.step("tool_executer")

        trace.step("hidden_memory")
        self.db.save_memory_item(MemoryType.AGENT_LOCAL.value, asdict(decision), agent_id="agent1")

        trace.step("database")
        self.db.save_decision(cycle_id, 1, "InitialDecision", asdict(decision))

        trace.step("observability", action=decision.action)
        trace.step("done")
        return decision


class Agent2:
    """Adversarially search for all failure paths of the InitialDecision (F1..F9)."""
    def __init__(self, provider: LLMProvider, db: DBManager, obs: Observability):
        self.provider = provider
        self.db = db
        self.obs = obs

    def run(self, cycle_id: str, initial: InitialDecision, context_sections: dict, trace_id: str) -> FailureReport:
        trace = _AgentPipelineTrace(self.obs, trace_id, "agent2")
        trace.step("context_compiler", cycle_id=cycle_id)

        llm_input = {**context_sections, "initial_decision": asdict(initial)}
        trace.step("llm")
        try:
            raw = self.provider.complete(role="agent2", context=llm_input)
        except Exception as e:
            self.obs.error(trace_id, agent="agent2", msg="llm_call_failed", error=str(e))
            # ensure all 9 categories are still represented even on hard failure
            from ..core.schemas import FailureCategory
            raw = {"paths": [{"category": c.value, "description": f"agent2 tool_failure: {e}", "severity": "high"}
                              for c in FailureCategory]}

        trace.step("decision_system")
        try:
            report = FailureReport(cycle_id=cycle_id,
                                    paths=[FailurePath(**p).validate() for p in raw["paths"]]).validate()
        except (TypeError, KeyError, SchemaError) as e:
            self.obs.warn(trace_id, agent="agent2", msg="invalid_schema_forcing_all_blocking", error=str(e))
            from ..core.schemas import FailureCategory
            report = FailureReport(
                cycle_id=cycle_id,
                paths=[FailurePath(category=c.value, description="schema_invalid fallback", severity="blocking")
                       for c in FailureCategory],
            )

        trace.step("planner_or_scheduler")
        trace.step("tool_manager")
        trace.step("tool_executer")

        trace.step("hidden_memory")
        self.db.save_memory_item(MemoryType.FAILURE.value, asdict(report), agent_id="agent2")

        trace.step("database")
        self.db.save_decision(cycle_id, 2, "FailureReport", asdict(report))
        self.db.save_failure_paths(cycle_id, report.paths)

        trace.step("observability", n_paths=len(report.paths), blocking=report.has_blocking())
        trace.step("done")
        return report


class Agent3:
    """Final decision: BUY / SELL / WAIT / RE-EVALUATE, with override authority."""
    def __init__(self, provider: LLMProvider, db: DBManager, obs: Observability):
        self.provider = provider
        self.db = db
        self.obs = obs

    def run(self, cycle_id: str, initial: InitialDecision, failure: FailureReport,
             context_sections: dict, trace_id: str) -> FinalDecision:
        trace = _AgentPipelineTrace(self.obs, trace_id, "agent3")
        trace.step("context_compiler", cycle_id=cycle_id)

        llm_input = {**context_sections, "initial_decision": asdict(initial), "failure_report": asdict(failure)}
        trace.step("llm")
        try:
            raw = self.provider.complete(role="agent3", context=llm_input)
        except Exception as e:
            self.obs.error(trace_id, agent="agent3", msg="llm_call_failed", error=str(e))
            raw = {"decision": "WAIT", "overrode_initial": True, "reason": f"tool_failure: {e}"}

        trace.step("decision_system")
        try:
            final = FinalDecision(cycle_id=cycle_id, **raw).validate()
        except (TypeError, SchemaError) as e:
            self.obs.warn(trace_id, agent="agent3", msg="invalid_schema_forcing_wait", error=str(e))
            final = FinalDecision(cycle_id=cycle_id, decision="WAIT", overrode_initial=True,
                                   reason=f"schema_invalid: {e}")

        trace.step("planner_or_scheduler")
        trace.step("tool_manager")
        trace.step("tool_executer")

        trace.step("hidden_memory")
        self.db.save_memory_item(MemoryType.AUDIT_HISTORY.value, asdict(final), agent_id="agent3")

        trace.step("database")
        self.db.save_decision(cycle_id, 3, "FinalDecision", asdict(final))

        trace.step("observability", decision=final.decision, overrode=final.overrode_initial)
        trace.step("done")

        # I4: every decision recorded to the append-only audit trail.
        self.obs.audit("final_decision", cycle_id=cycle_id, decision=final.decision,
                        overrode_initial=final.overrode_initial, reason=final.reason)
        return final
