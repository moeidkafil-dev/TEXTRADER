"""SQLite connection wrapper."""
from __future__ import annotations

import random
import sqlite3
import threading
import time
from pathlib import Path
from typing import Optional

# How many times a single process will retry opening/initializing a DB
# file that another OS process currently holds locked (see DB.__init__).
_INIT_RETRIES = 6


class DB:
    """Thread-safe SQLite wrapper. One connection per DB instance; check_same_thread=False
    because the orchestrator may run from a worker thread (and tests too)."""

    def __init__(self, path: str = "data/trader.db"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # Per-instance lock. This was previously a *class* attribute, which
        # meant every DB object in the process — even ones pointing at
        # different database files — serialized through the same lock.
        # Harmless for correctness (just needless contention) but still a
        # bug: two independent DB files should not block each other.
        self._lock = threading.RLock()

        # `timeout=` gives sqlite3's own busy-wait (seconds) on the *first*
        # statement issued on this connection, before any PRAGMA has run.
        # We still retry the whole open below because several OS processes
        # can race to create/upgrade the same brand-new file at once
        # (multiprocessing), which can raise "database is locked" even
        # with a timeout set, if the first process hasn't released the
        # lock yet when this one's timeout elapses.
        last_err: Optional[sqlite3.OperationalError] = None
        for attempt in range(_INIT_RETRIES):
            try:
                self._conn = sqlite3.connect(str(self.path), check_same_thread=False,
                                             isolation_level=None, timeout=30.0)
                self._conn.row_factory = sqlite3.Row
                # PRAGMA busy_timeout MUST be set BEFORE journal_mode=WAL.
                # Switching journal modes briefly needs an exclusive lock on
                # the file; only statements issued *after* busy_timeout is
                # set will wait-and-retry on that lock instead of raising
                # sqlite3.OperationalError("database is locked") right away.
                # With the old ordering (WAL first, busy_timeout second),
                # concurrent first-time initialization from multiple
                # processes against the same file failed immediately.
                self._conn.execute("PRAGMA busy_timeout = 30000;")
                self._conn.execute("PRAGMA journal_mode = WAL;")
                self._conn.execute("PRAGMA foreign_keys = ON;")
                self._conn.execute("PRAGMA synchronous = NORMAL;")
                break
            except sqlite3.OperationalError as e:
                last_err = e
                if "locked" not in str(e).lower() or attempt == _INIT_RETRIES - 1:
                    raise
                try:
                    self._conn.close()
                except Exception:
                    pass
                time.sleep(min(0.05 * (2 ** attempt), 1.0) + random.uniform(0, 0.05))
        else:  # pragma: no cover - loop always breaks or raises
            if last_err:
                raise last_err

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

    IMPORTANT: this only *closes* the previous default connection when the
    requested path genuinely differs from it. Any caller still holding a
    reference to that previous DB object (e.g. an older Orchestrator
    instance) would see every subsequent call on it fail with
    "Cannot operate on a closed database." When the path is unchanged we
    must hand back the *same still-open* connection instead of recycling it,
    since multiple live objects (an old and a new Orchestrator, several
    ControlPlane rebuilds, etc.) can legitimately point at the same file at
    the same time within one process.
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
    """Force-close and drop the shared DB.

    Only call this when you are certain nothing else in the process still
    holds a reference to the current default DB — closing it out from under
    a live caller is exactly the bug this function used to cause when it
    was invoked unconditionally from Orchestrator.__init__ (see
    trader/engine/orchestrator.py). Test code that wants a guaranteed-fresh
    handle should prefer a unique db_path (e.g. pytest's tmp_path) over
    calling this.
    """
    global _default_db
    with _default_lock:
        if _default_db is not None:
            _default_db.close()
        _default_db = None
