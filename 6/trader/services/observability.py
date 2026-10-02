"""
Observability — chapter 03 C18 / REQ-OBS-01.

Every agent and module writes structured events here. The default sink is the
`observability_events` SQLite table; an additional in-memory sink is provided
for tests and ad-hoc inspection.
"""
from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from typing import Any, Callable, Optional

from trader.core.schemas import ObservabilityEvent
from trader.storage import repo


class Observability:
    """Central observability hub. One instance per process.

    `component` is the graph-node name (e.g., 'agent1', 'risk_engine', 'guard').
    `level` is one of: debug | info | warn | error.
    `trace_id` is the cycle_id (or a generated id when no cycle yet).
    """

    def __init__(self, db_getter: Optional[Callable[[], Any]] = None,
                 level: str = "info"):
        self._db_getter = db_getter or repo.get_db
        self._level = level
        self._listeners: list[Callable[[ObservabilityEvent], None]] = []
        self._lock = threading.Lock()

    def set_level(self, level: str) -> None:
        self._level = level

    def add_listener(self, fn: Callable[[ObservabilityEvent], None]) -> None:
        with self._lock:
            self._listeners.append(fn)

    _LEVELS = {"debug": 0, "info": 1, "warn": 2, "error": 3}

    def _passes(self, level: str) -> bool:
        return self._LEVELS.get(level, 1) >= self._LEVELS.get(self._level, 1)

    def emit(self, component: str, level: str, trace_id: str,
             cycle_id: str = "", data: Optional[dict] = None) -> ObservabilityEvent:
        if not self._passes(level):
            # still notify listeners (useful for in-memory capture in tests)
            ev = ObservabilityEvent(component=component, level=level, trace_id=trace_id,
                                     cycle_id=cycle_id, data=data or {})
            with self._lock:
                for fn in self._listeners:
                    try:
                        fn(ev)
                    except Exception:
                        pass
            return ev
        ev = ObservabilityEvent(component=component, level=level, trace_id=trace_id,
                                 cycle_id=cycle_id, data=data or {})
        try:
            db = self._db_getter()
            repo.insert_observability(db, ev)
        except Exception:
            # never let observability failure break the runtime
            pass
        with self._lock:
            for fn in self._listeners:
                try:
                    fn(ev)
                except Exception:
                    pass
        return ev

    # Convenience shorthand
    def debug(self, component: str, trace_id: str, **kw) -> ObservabilityEvent:
        return self.emit(component, "debug", trace_id, **kw)

    def info(self, component: str, trace_id: str, **kw) -> ObservabilityEvent:
        return self.emit(component, "info", trace_id, **kw)

    def warn(self, component: str, trace_id: str, **kw) -> ObservabilityEvent:
        return self.emit(component, "warn", trace_id, **kw)

    def error(self, component: str, trace_id: str, **kw) -> ObservabilityEvent:
        return self.emit(component, "error", trace_id, **kw)
