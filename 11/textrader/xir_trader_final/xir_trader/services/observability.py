"""
Observability — structured logging present in every component
(SUPER_PROMPT.md §5: "Observability در همه"). Writes to stdout as JSON
lines AND to the observability_events / audit_log tables via DBManager.
"""
from __future__ import annotations

import json
import sys
import time
import uuid

from .db_manager import DBManager
from ..core.config import redact_secrets


class Observability:
    def __init__(self, db: DBManager, component: str):
        self.db = db
        self.component = component

    def _emit(self, level: str, trace_id: str, **data) -> None:
        now = time.time()
        record = {
            "timestamp": now,
            "ts": now,
            "component": self.component,
            "severity": level,
            "level": level,
            "trace_id": trace_id,
            "cycle_id": data.get("cycle_id"),
            "state": data.get("state"),
            "event": data.get("event", data.get("msg", "component_event")),
            "decision": data.get("decision"),
            "result": data.get("result"),
            "error": data.get("error_type", data.get("error")),
            **data,
        }
        record = redact_secrets(record)
        print(json.dumps(record, default=str), file=sys.stdout)
        self.db.log_event(self.component, level, trace_id, data)

    def info(self, trace_id: str, **data) -> None:
        self._emit("INFO", trace_id, **data)

    def warn(self, trace_id: str, **data) -> None:
        self._emit("WARN", trace_id, **data)

    def error(self, trace_id: str, **data) -> None:
        self._emit("ERROR", trace_id, **data)

    def audit(self, event: str, **data) -> None:
        """Append-only audit trail (I4: every decision is recorded)."""
        self.db.append_audit(event, data)


def new_trace_id() -> str:
    return str(uuid.uuid4())
