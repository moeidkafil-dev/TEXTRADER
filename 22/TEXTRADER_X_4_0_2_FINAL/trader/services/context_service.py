"""
Context Maker + Context Sender — chapter 03 C02/C03 (n0::n1, n0::n2).
REQ-DR-03, REQ-DR-04.

Context = data + memory + previous decisions + market state + user config + any
context required. Every section has a source and version; an empty section is
flagged with `empty=True`, NOT dropped (REQ-DR-03 failure handling).

The Context Sender delivers Context to Agent 1's context compiler (OI-01).
In this runtime, delivery is in-process; a real distributed deployment would
use a queue (chapter 16 API).
"""
from __future__ import annotations

from typing import Any, Optional

from trader.core.schemas import Context, ContextSection, DataBundle
from trader.core.util import sha256_of
from trader.storage import repo


class ContextMaker:
    def __init__(self, memory_manager=None, observability=None, user_config: Optional[dict] = None):
        self._mm = memory_manager
        self._obs = observability
        self._user_config = user_config or {"risk_appetite": "moderate"}

    def make(self, cycle_id: str, bundles: list[DataBundle],
             previous_decisions: list[dict] | None = None,
             market_state: dict | None = None) -> Context:
        sections: list[ContextSection] = []

        # Section 1: market data
        if bundles:
            data_payload = [b.to_dict() for b in bundles]
            sections.append(ContextSection(
                name="market_data",
                source="data_reader",
                version="1.0",
                data={"bundles": data_payload},
                empty=False,
            ))
        else:
            sections.append(ContextSection(
                name="market_data", source="data_reader", version="1.0",
                data={}, empty=True,
            ))

        # Section 2: memory snapshot (latest items per type from agent local + recent LTM/STM)
        memory_data: dict[str, Any] = {}
        if self._mm is not None:
            for mt in ["4", "3", "17", "18", "19", "10", "21"]:  # LTM, STM, Failure, Success, Reflection, Context, RAG
                try:
                    items = self._mm.read(mt, limit=3)
                    if items:
                        memory_data[mt] = items
                except Exception:
                    pass
        sections.append(ContextSection(
            name="memory", source="memory_manager", version="1.0",
            data=memory_data, empty=not memory_data,
        ))

        # Section 3: previous decisions (audit pull)
        try:
            db = repo.get_db()
            prev = previous_decisions if previous_decisions is not None else \
                repo.list_decisions(db, cycle_id)  # current cycle; usually empty for new
        except Exception:
            prev = []
        sections.append(ContextSection(
            name="previous_decisions", source="db.audit", version="1.0",
            data={"decisions": prev or []}, empty=not prev,
        ))

        # Section 4: market state
        ms = market_state or {}
        sections.append(ContextSection(
            name="market_state", source="context_service", version="1.0",
            data=ms, empty=not ms,
        ))

        # Section 5: user config
        sections.append(ContextSection(
            name="user_config", source="config", version="1.0",
            data=self._user_config, empty=not self._user_config,
        ))

        # Build context and compute its hash
        ctx = Context(cycle_id=cycle_id, sections=tuple(sections))
        ctx_dict = ctx.to_dict()
        ctx = Context(context_id=ctx.context_id, cycle_id=cycle_id,
                      sections=sections, hash=sha256_of(ctx_dict))
        return ctx


class ContextSender:
    """Delivers Context to Agent 1. In-process delivery here.

    The interface matches REQ-DR-04: exactly-once delivery, ack returned.
    A real distributed deployment would POST /context to the agent service.
    """

    def __init__(self, observability=None):
        self._obs = observability

    def deliver(self, ctx: Context, agent1) -> str:
        """Hand ctx to agent1. Returns ack (ctx.context_id)."""
        agent1.receive_context(ctx)
        if self._obs:
            self._obs.info("context_sender", trace_id=ctx.cycle_id,
                            data={"event": "delivered",
                                   "context_id": ctx.context_id,
                                   "hash": ctx.hash})
        return ctx.context_id
