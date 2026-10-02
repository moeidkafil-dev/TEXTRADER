"""
Agent base — chapter 03 C04/C05/C06 / REQ-AG-01.

Each agent has 10 internal parts: llm, context_compiler, decision_system,
planner, scheduler, tool_manager, tool_executer, hidden_memory, database,
observability. The internal flow is enforced (compiler → llm → decision →
(planner|scheduler) → tool_manager → tool_executer; all → hidden_memory →
database; tool_executer → observability → database).

In this reference runtime the parts are co-located inside one Python object
per agent; the flow order is preserved by named private methods called in
sequence, so the observability trace shows the full 10-step walk for every
agent invocation.
"""
from __future__ import annotations

from typing import Any, Optional

from trader.adapters.llm import LLMAdapter
from trader.core.schemas import Context
from trader.memory.manager import MemoryManager


class AgentBase:
    """Common scaffold for agents 1, 2, 3."""

    AGENT_ID = "agent"

    # The 10 internal parts (named to match the graph catalog).
    def __init__(self, llm: LLMAdapter, memory: MemoryManager, observability,
                 agent_id: str):
        self.llm = llm
        self.memory = memory
        self._obs = observability
        self.agent_id = agent_id
        self._last_ctx: Optional[Context] = None

    # ----- the 10 parts (each is a small named function so traces show it) -----
    def _part_context_compiler(self, ctx: Context) -> str:
        self._obs.debug(f"{self.agent_id}.context_compiler", trace_id=ctx.cycle_id,
                        data={"ctx_id": ctx.context_id})
        # Build a textual prompt from the context sections.
        parts = []
        for s in ctx.sections:
            tag = "[empty]" if s.empty else "[ok]"
            parts.append(f"# section {s.name} {tag} (source={s.source}, v{s.version})\n"
                         + str(s.data)[:2000])
        return "\n\n".join(parts)

    def _part_llm(self, system: str, user: str, ctx: Context) -> str:
        self._obs.debug(f"{self.agent_id}.llm", trace_id=ctx.cycle_id,
                        data={"system_len": len(system), "user_len": len(user)})
        return self.llm.complete(system=system, user=user)

    def _part_decision_system(self, raw: str, ctx: Context) -> dict:
        # Each subclass overrides this to parse into its schema.
        raise NotImplementedError

    def _part_planner(self, decision: dict, ctx: Context) -> dict:
        self._obs.debug(f"{self.agent_id}.planner", trace_id=ctx.cycle_id)
        return decision

    def _part_scheduler(self, decision: dict, ctx: Context) -> dict:
        self._obs.debug(f"{self.agent_id}.scheduler", trace_id=ctx.cycle_id)
        return decision

    def _part_tool_manager(self, decision: dict, ctx: Context) -> list:
        # Agents have no executable tools in this runtime — they produce decisions only.
        self._obs.debug(f"{self.agent_id}.tool_manager", trace_id=ctx.cycle_id)
        return []

    def _part_tool_executer(self, tools: list, ctx: Context) -> list:
        self._obs.debug(f"{self.agent_id}.tool_executer", trace_id=ctx.cycle_id)
        return []

    def _part_hidden_memory(self, decision: dict, ctx: Context) -> None:
        # write to agent-local memory (REQ-MEM-02)
        try:
            self.memory.write("24", decision, agent_id=self.agent_id,
                              meta={"cycle_id": ctx.cycle_id, "kind": "hidden"})
        except Exception as e:
            self._obs.warn(f"{self.agent_id}.hidden_memory", trace_id=ctx.cycle_id,
                            data={"error": str(e)})

    def _part_database(self, decision: dict, ctx: Context) -> None:
        # Persist via db_manager (handled by orchestrator audit step).
        self._obs.debug(f"{self.agent_id}.database", trace_id=ctx.cycle_id)

    def _part_observability(self, decision: dict, ctx: Context, parts_log: list[str]) -> None:
        self._obs.info(self.agent_id, trace_id=ctx.cycle_id,
                       data={"event": "agent_run_complete",
                              "parts": parts_log,
                              "decision_kind": decision.get("kind", "unknown")})

    # ----- public entrypoint -----
    def receive_context(self, ctx: Context) -> None:
        self._last_ctx = ctx

    def _run_parts(self, ctx: Context, system_prompt: str, user_prompt_builder) -> dict:
        parts_log: list[str] = []
        compiled = self._part_context_compiler(ctx); parts_log.append("context_compiler")
        user = user_prompt_builder(compiled, ctx)
        raw = self._part_llm(system_prompt, user, ctx); parts_log.append("llm")
        decision = self._part_decision_system(raw, ctx); parts_log.append("decision_system")
        decision = self._part_planner(decision, ctx); parts_log.append("planner")
        decision = self._part_scheduler(decision, ctx); parts_log.append("scheduler")
        tools = self._part_tool_manager(decision, ctx); parts_log.append("tool_manager")
        self._part_tool_executer(tools, ctx); parts_log.append("tool_executer")
        self._part_hidden_memory(decision, ctx); parts_log.append("hidden_memory")
        self._part_database(decision, ctx); parts_log.append("database")
        self._part_observability(decision, ctx, parts_log); parts_log.append("observability")
        return decision
