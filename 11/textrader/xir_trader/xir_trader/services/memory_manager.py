"""
Memory Manager — AGENT_AND_MEMORY_MODEL.md, 12-step process:

  input reader -> input analyser -> input setter in memory -> memory analyser
  -> memory complete analyser -> find junks -> tables cleaner -> memory analyser
  -> being in sleep mode (every 2h) -> output request analyser -> result maker
  -> result/log

"find junks": duplicate/redundant/stale-with-newer-version/orphaned-from-deleted-files;
task caches are consolidated into a single lightweight cache file.
"tables cleaner": deletes junk and re-buckets dynamically.

Entry point per OI-06: "memory manager agent" (type 28) is where cycles begin;
the other 27 types are a catalog it reads/writes, not a forced pipeline.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

from ..core.memory_types import MemoryType, ORDERED_MEMORY_TYPES
from .db_manager import DBManager
from .observability import Observability


@dataclass
class MemoryManagerReport:
    step_log: list = field(default_factory=list)
    junks_found: int = 0
    junks_removed: int = 0
    items_scanned: int = 0


class MemoryManager:
    def __init__(self, db: DBManager, obs: Observability, sleep_interval_seconds: int = 7200):
        self.db = db
        self.obs = obs
        self.sleep_interval_seconds = sleep_interval_seconds
        self._last_cycle_ts: float = 0.0

    def due(self, now: float | None = None) -> bool:
        now = now if now is not None else time.time()
        return (now - self._last_cycle_ts) >= self.sleep_interval_seconds

    def remember(self, memory_type: MemoryType, content, meta: dict | None = None, agent_id: str = "") -> None:
        """input reader -> input analyser -> input setter in memory (steps 1-3, on-demand write path)."""
        self.db.save_memory_item(memory_type.value, content, meta=meta, agent_id=agent_id)

    def recall(self, memory_type: MemoryType | None = None, limit: int = 50) -> list:
        return self.db.query_memory(memory_type.value if memory_type else None, limit=limit)

    def run_cycle(self, trace_id: str, request: dict | None = None) -> MemoryManagerReport:
        """Runs the full 12-step maintenance cycle. Safe to call manually (tests / CLI
        `memory-cycle` command) or automatically once `due()` is True."""
        report = MemoryManagerReport()

        def log(step: str, **data):
            report.step_log.append({"step": step, **data})
            self.obs.info(trace_id, component="memory_manager", step=step, **data)

        log("input_reader")
        log("input_analyser")
        log("input_setter_in_memory")

        log("memory_analyser")
        all_items = self.db.query_memory(limit=10_000)
        report.items_scanned = len(all_items)

        log("memory_complete_analyser", items=len(all_items))

        # find junks: naive duplicate-content detector within the same memory_type
        log("find_junks")
        seen: dict[tuple, int] = {}
        junk_ids: list[int] = []
        for row in all_items:
            item_id, mtype, agent_id, content, meta, ts = row
            key = (mtype, agent_id, content)
            if key in seen:
                junk_ids.append(item_id)
            else:
                seen[key] = item_id
        report.junks_found = len(junk_ids)

        log("tables_cleaner", junk_ids=junk_ids[:50])  # cap logged ids for readability
        if junk_ids:
            with self.db.cursor() as c:
                c.executemany("DELETE FROM memory_items WHERE id=?", [(i,) for i in junk_ids])
            report.junks_removed = len(junk_ids)

        log("memory_analyser_post_clean")

        log("sleep_mode", interval_seconds=self.sleep_interval_seconds)
        self._last_cycle_ts = time.time()

        log("output_request_analyser", request=request or {})
        result = self._serve_request(request or {})

        log("result_maker", result_keys=list(result.keys()))
        log("result_log", junks_removed=report.junks_removed, items_scanned=report.items_scanned)

        self.obs.audit("memory_manager_cycle", junks_removed=report.junks_removed,
                        items_scanned=report.items_scanned)
        return report

    def _serve_request(self, request: dict) -> dict:
        mtype = request.get("memory_type")
        limit = request.get("limit", 20)
        items = self.recall(MemoryType(mtype) if mtype else None, limit=limit)
        return {"items": items}

    def snapshot_for_context(self, limit_per_type: int = 5) -> dict:
        """Small, bounded snapshot handed to ContextMaker's `memory` section —
        avoids dumping all 28 stores into every context."""
        snap = {}
        for mtype in (MemoryType.EXPERIENCE, MemoryType.FAILURE, MemoryType.SUCCESS,
                      MemoryType.USER_PROFILE, MemoryType.META):
            snap[mtype.value] = self.db.query_memory(mtype.value, limit=limit_per_type)
        return snap
