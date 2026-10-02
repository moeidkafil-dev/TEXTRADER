"""SQLite connection wrapper."""
from __future__ import annotations

import sqlite3
import threading
from pathlib import Path
from typing import Optional


class DB:
    """Thread-safe SQLite wrapper. One shared connection per process; check_same_thread=False
    because the orchestrator may run from a worker thread (and tests too)."""

    _lock = threading.RLock()

    def __init__(self, path: str = "data/trader.db"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # check_same_thread=False because we serialize with _lock.
        self._conn = sqlite3.connect(str(self.path), check_same_thread=False,
                                     isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode = WAL;")
        self._conn.execute("PRAGMA foreign_keys = ON;")
        self._conn.execute("PRAGMA busy_timeout = 10000;")
        self._conn.execute("PRAGMA synchronous = NORMAL;")

    @property
    def conn(self) -> sqlite3.Connection:
        return self._conn

    def execute(self, sql: str, params: tuple = ()):  # type: ignore[assignment]
        with self._lock:
            cur = self._conn.execute(sql, params)
            self._conn.commit()
            return cur

    def executemany(self, sql: str, params_list):  # type: ignore[assignment]
        with self._lock:
            cur = self._conn.executemany(sql, params_list)
            self._conn.commit()
            return cur

    def query(self, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        with self._lock:
            cur = self._conn.execute(sql, params)
            return cur.fetchall()

    def query_one(self, sql: str, params: tuple = ()) -> Optional[sqlite3.Row]:
        with self._lock:
            cur = self._conn.execute(sql, params)
            return cur.fetchone()

    def close(self) -> None:
        with self._lock:
            self._conn.close()


_default_db: Optional[DB] = None
_default_lock = threading.Lock()


def get_db(path: str | None = None) -> DB:
    """Return the shared DB. If `path` is None or matches the current default,
    reuse it. If `path` differs from current default, switch to the new path.

    Most callers should call `get_db()` with no args to reuse the orchestrator's DB.
    """
    global _default_db
    with _default_lock:
        if path is None:
            if _default_db is None:
                _default_db = DB("data/trader.db")
            return _default_db
        if _default_db is None or _default_db.path != Path(path):
            if _default_db is not None:
                _default_db.close()
            _default_db = DB(path)
        return _default_db


def reset_default_db() -> None:
    """Used by tests to force a fresh DB."""
    global _default_db
    with _default_lock:
        if _default_db is not None:
            _default_db.close()
        _default_db = None
