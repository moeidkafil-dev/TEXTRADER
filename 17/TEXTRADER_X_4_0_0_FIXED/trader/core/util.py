"""Tiny utility helpers — hashing, time, IDs."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def short_id(prefix: str = "") -> str:
    import uuid as _u
    return f"{prefix}{_u.uuid4().hex[:12]}"


def sha256_of(obj: Any) -> str:
    """Deterministic SHA-256 of a JSON-serializable object."""
    if isinstance(obj, (str, bytes)):
        s = obj if isinstance(obj, str) else obj.decode()
    else:
        s = json.dumps(obj, sort_keys=True, default=str)
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:16]


def now_ts() -> str:
    return utcnow().isoformat()


def in_session(sessions: list[str], now: datetime) -> bool:
    """Check whether `now` falls inside any of the configured trading sessions."""
    if not sessions:
        return True
    hhmm = int(now.strftime("%H%M"))
    for s in sessions:
        if "-" not in s:
            continue
        a, b = s.split("-", 1)
        a_int = int(a.replace(":", ""))
        b_int = int(b.replace(":", ""))
        if a_int <= b_int:
            if a_int <= hhmm <= b_int:
                return True
        else:
            # wrap-around session (e.g., 22:00-02:00)
            if hhmm >= a_int or hhmm <= b_int:
                return True
    return False
