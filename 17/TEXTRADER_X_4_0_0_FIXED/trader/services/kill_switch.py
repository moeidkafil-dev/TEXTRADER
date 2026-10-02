"""
Kill Switch — chapter 07 / REQ-KS-01 / P-05.

Independent of every other component. Absolute priority: when active, the
orchestrator enters HALTED state and stays there until an explicit resume.

Activatable from Telegram/Email (per design). In this runtime, activation is
exposed as `KillSwitch.activate(reason)` and triggers state HALTED via the
orchestrator hook. Kill Switch writes to audit memory (I4) and observability.
"""
from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Callable, Optional


class KillSwitch:
    def __init__(self, observability, on_change: Optional[Callable[[bool, str], None]] = None):
        self._active = False
        self._reason = ""
        self._activated_at: Optional[datetime] = None
        self._lock = threading.RLock()
        self._obs = observability
        self._on_change = on_change

    @property
    def is_active(self) -> bool:
        with self._lock:
            return self._active

    @property
    def reason(self) -> str:
        with self._lock:
            return self._reason

    @property
    def activated_at(self) -> Optional[datetime]:
        with self._lock:
            return self._activated_at

    def activate(self, reason: str = "manual") -> None:
        with self._lock:
            if self._active:
                return
            self._active = True
            self._reason = reason
            self._activated_at = datetime.now(timezone.utc)
        if self._obs:
            self._obs.emit("kill_switch", "error", trace_id="kill_switch",
                            data={"event": "activated", "reason": reason})
        if self._on_change:
            try:
                self._on_change(True, reason)
            except Exception:
                pass

    def deactivate(self, reason: str = "manual_resume") -> None:
        """Explicit resume only — NEVER auto-recovered."""
        with self._lock:
            if not self._active:
                return
            self._active = False
            prev_reason = self._reason
            self._reason = ""
            self._activated_at = None
        if self._obs:
            self._obs.emit("kill_switch", "info", trace_id="kill_switch",
                            data={"event": "deactivated", "reason": reason,
                                   "prev_reason": prev_reason})
        if self._on_change:
            try:
                self._on_change(False, reason)
            except Exception:
                pass

    def to_dict(self) -> dict:
        with self._lock:
            return {
                "active": self._active,
                "reason": self._reason,
                "activated_at": self._activated_at.isoformat() if self._activated_at else None,
            }
