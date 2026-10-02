"""
The 28 memory types — chapter 05 AGENT_AND_MEMORY_MODEL.md.

All 28 types are preserved as logical stores. Each type is named with both an
ordinal (1..28) and a slug; both are accepted as identifiers in the public API.
The "Agent Local Memory" (24) is per-agent (REQ-MEM-02); the store exposes a
sub-namespace per agent_id.

Catalog (signature of the owner — DO NOT merge or delete):
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional


class MemoryType(str, Enum):
    SENSORY = "1"
    WORKING = "2"
    STM = "3"
    LTM = "4"
    EPISODIC = "5"
    SEMANTIC = "6"
    PROCEDURAL = "7"
    GOAL = "8"
    TASK = "9"
    CONTEXT = "10"
    CONVERSATION = "11"
    TOOL = "12"
    ENVIRONMENT = "13"
    USER_PROFILE = "14"
    LEARNING = "15"
    EXPERIENCE = "16"
    FAILURE = "17"
    SUCCESS = "18"
    REFLECTION = "19"
    PLANNING = "20"
    RAG = "21"
    CACHE = "22"
    SHARED = "23"
    AGENT_LOCAL = "24"
    AUDIT = "25"
    TEMPORAL = "26"
    META = "27"
    MEMORY_MANAGER = "28"

    @classmethod
    def from_name(cls, name: str) -> "MemoryType":
        n = name.strip().lower()
        for k, v in MEMORY_TYPE_NAMES.items():
            if v.lower() == n:
                return cls(k)
        # accept ordinal too
        if n.isdigit():
            return cls(n)
        raise KeyError(f"Unknown memory type name: {name!r}")


# Map ordinal -> human name (chapter 05)
MEMORY_TYPE_NAMES = {
    "1":  "Sensory Memory",
    "2":  "Working Memory",
    "3":  "Short-Term Memory (STM)",
    "4":  "Long-Term Memory (LTM)",
    "5":  "Episodic Memory",
    "6":  "Semantic (Knowledge) Memory",
    "7":  "Procedural Memory",
    "8":  "Goal Memory",
    "9":  "Task Memory",
    "10": "Context Memory",
    "11": "Conversation Memory",
    "12": "Tool Memory",
    "13": "Environment / World State",
    "14": "User Profile Memory",
    "15": "Learning Memory",
    "16": "Experience Memory",
    "17": "Failure Memory",
    "18": "Success Memory",
    "19": "Reflection Memory",
    "20": "Planning Memory",
    "21": "RAG Memory",
    "22": "Cache Memory",
    "23": "Shared Memory",
    "24": "Agent Local Memory",
    "25": "Audit / History Memory",
    "26": "Temporal Memory",
    "27": "Meta Memory",
    "28": "memory manager agent",
}

ALL_MEMORY_TYPES = list(MEMORY_TYPE_NAMES.keys())  # 28 entries


@dataclass
class MemoryItem:
    memory_type: str
    agent_id: Optional[str]
    content: Any
    meta: dict[str, Any]
    ts: str
    rowid: Optional[int] = None


class MemoryStore:
    """In-memory front for the 28 logical stores, backed by `memory_items` table.

    Audit Memory (25) is write-once; nothing else is special-cased.
    Agent Local Memory (24) is namespaced by agent_id (REQ-MEM-02).
    """

    def __init__(self, repo_module):
        # Repo is injected so we can mock in tests.
        self._repo = repo_module

    def write(self, memory_type: str, content: Any, agent_id: Optional[str] = None,
              meta: Optional[dict] = None) -> int:
        mt = MemoryType.from_name(memory_type).value
        return self._repo.insert_memory_item(self._repo.get_db(), mt, content, agent_id, meta)

    def read(self, memory_type: str, agent_id: Optional[str] = None, limit: int = 100) -> list[MemoryItem]:
        mt = MemoryType.from_name(memory_type).value
        rows = self._repo.list_memory_items(self._repo.get_db(), memory_type=mt, agent_id=agent_id, limit=limit)
        return [MemoryItem(memory_type=r["memory_type"], agent_id=r["agent_id"],
                            content=r["content"], meta=r["meta"], ts=r["ts"], rowid=r["id"])
                for r in rows]

    def remove_junk(self, rowid: int) -> None:
        """Used by Memory Manager tables_cleaner. Refuses to drop audit memory."""
        row = self._repo.get_db().query_one(
            "SELECT memory_type FROM memory_items WHERE id=?", (rowid,))
        if row and row["memory_type"] == MemoryType.AUDIT.value:
            raise ValueError("Cannot delete Audit Memory (append-only invariant I4)")
        self._repo.delete_memory_item(self._repo.get_db(), rowid)

    def all_types(self) -> list[str]:
        return ALL_MEMORY_TYPES
