"""
C02 Context Maker + C03 Context Sender — REQ-DR-03, REQ-DR-04.

Context = data + memory + previous_decisions + market_state + user_config.
Every section carries a source/version; an empty section is flagged, never
dropped (PRD constraint). Per OI-01, the sender hands the context straight
to Agent 1's context-compiler input — implemented here as a plain function
call boundary (single process), keeping the same 1-delivery contract a
message queue would give in the microservice version.
"""
from __future__ import annotations

import hashlib
import json
import uuid

from ..core.schemas import Context, DataBundle
from .db_manager import DBManager
from .observability import Observability


def _section(value, source: str) -> dict:
    empty = value is None or value == {} or value == []
    return {"source": source, "value": value, "empty": empty}


class ContextMaker:
    def __init__(self, db: DBManager, obs: Observability):
        self.db = db
        self.obs = obs

    def make(self, cycle_id: str, data_bundles: list[DataBundle], memory_snapshot: dict,
              previous_decisions: list, market_state: dict, user_config: dict, trace_id: str) -> Context:
        sections = {
            "data": _section([b.payload for b in data_bundles], "data_reader"),
            "memory": _section(memory_snapshot, "memory_manager"),
            "previous_decisions": _section(previous_decisions, "db.decisions"),
            "market_state": _section(market_state, "data_reader.market_state"),
            "user_config": _section(user_config, "app_config"),
        }
        raw = json.dumps(sections, sort_keys=True, default=str).encode()
        ctx = Context(
            context_id=str(uuid.uuid4()),
            cycle_id=cycle_id,
            hash=hashlib.sha256(raw).hexdigest(),
            sections=sections,
        )
        self.db.save_context(ctx)
        empties = [k for k, v in sections.items() if v["empty"]]
        if empties:
            self.obs.warn(trace_id, msg="context_has_empty_sections", sections=empties)
        self.obs.info(trace_id, msg="context_built", context_id=ctx.context_id, hash=ctx.hash)
        return ctx


class ContextSender:
    """REQ-DR-04: deliver Context to Agent 1's compiler input exactly once."""
    def __init__(self, obs: Observability):
        self.obs = obs

    def send(self, ctx: Context, deliver_fn, trace_id: str) -> Context:
        delivered = deliver_fn(ctx)
        if delivered.hash != ctx.hash:
            # Ack mismatch -> per PRD: retry once, then warn. Kept simple in-process: raise.
            self.obs.error(trace_id, msg="context_delivery_hash_mismatch", context_id=ctx.context_id)
            raise RuntimeError("Context delivery ack hash mismatch")
        self.obs.info(trace_id, msg="context_delivered", context_id=ctx.context_id)
        return delivered
