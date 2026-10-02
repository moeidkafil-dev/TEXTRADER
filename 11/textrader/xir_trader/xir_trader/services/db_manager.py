"""
DB Manager — tables per 16_DATABASE_AND_API/DATABASE_AND_API.md.
Reference stack uses SQLite (ENGINEERING_SPEC.md marks Postgres as
`[PROPOSED]`/replaceable; SQLite keeps this runnable with zero external
services while preserving the same table shapes).

audit_log is append-only (I4, SECURITY_MODEL.md "تخریب Audit"): there is
no UPDATE/DELETE statement anywhere in this module for that table.
"""
from __future__ import annotations

import json
import sqlite3
import time
from contextlib import contextmanager
from typing import Iterator, Optional

from ..core.config import redact_secrets

SCHEMA = """
CREATE TABLE IF NOT EXISTS cycles (
    cycle_id TEXT PRIMARY KEY,
    started_at REAL,
    status TEXT,
    reeval_count INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS data_bundles (
    id TEXT PRIMARY KEY,
    cycle_id TEXT,
    source TEXT,
    ts REAL,
    quality TEXT,
    payload TEXT,
    hash TEXT
);
CREATE TABLE IF NOT EXISTS contexts (
    context_id TEXT PRIMARY KEY,
    cycle_id TEXT,
    hash TEXT,
    sections TEXT
);
CREATE TABLE IF NOT EXISTS decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cycle_id TEXT,
    agent INTEGER,
    type TEXT,
    payload TEXT,
    ts REAL
);
CREATE TABLE IF NOT EXISTS failure_paths (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cycle_id TEXT,
    category TEXT,
    severity TEXT,
    text TEXT
);
CREATE TABLE IF NOT EXISTS orders (
    order_id TEXT PRIMARY KEY,
    idempotency_key TEXT UNIQUE,
    side TEXT,
    instrument TEXT,
    size REAL,
    sl REAL,
    tp REAL,
    status TEXT,
    cycle_id TEXT,
    ts REAL
);
CREATE TABLE IF NOT EXISTS risk_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id TEXT,
    rule TEXT,
    pass INTEGER,
    reason TEXT,
    ts REAL
);
CREATE TABLE IF NOT EXISTS veto_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id TEXT,
    notified_at REAL,
    response TEXT,
    ts REAL
);
CREATE TABLE IF NOT EXISTS memory_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    memory_type TEXT,
    agent_id TEXT,
    content TEXT,
    meta TEXT,
    ts REAL
);
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL,
    event TEXT,
    data TEXT
);
CREATE TABLE IF NOT EXISTS observability_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    component TEXT,
    level TEXT,
    trace_id TEXT,
    ts REAL,
    data TEXT
);
"""


class DBManager:
    def __init__(self, path: str = "xir_trader.db"):
        self.path = path
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._conn.executescript(SCHEMA)
        self._conn.commit()

    @contextmanager
    def cursor(self) -> Iterator[sqlite3.Cursor]:
        cur = self._conn.cursor()
        try:
            yield cur
            self._conn.commit()
        finally:
            cur.close()

    # ---- cycles ----
    def create_cycle(self, cycle_id: str) -> None:
        with self.cursor() as c:
            c.execute(
                "INSERT OR IGNORE INTO cycles (cycle_id, started_at, status, reeval_count) VALUES (?,?,?,0)",
                (cycle_id, time.time(), "started"),
            )

    def set_cycle_status(self, cycle_id: str, status: str) -> None:
        with self.cursor() as c:
            c.execute("UPDATE cycles SET status=? WHERE cycle_id=?", (status, cycle_id))

    def increment_reeval(self, cycle_id: str) -> int:
        with self.cursor() as c:
            c.execute("UPDATE cycles SET reeval_count = reeval_count + 1 WHERE cycle_id=?", (cycle_id,))
            c.execute("SELECT reeval_count FROM cycles WHERE cycle_id=?", (cycle_id,))
            row = c.fetchone()
            return row[0] if row else 0

    # ---- data bundles ----
    def save_data_bundle(self, bundle) -> None:
        with self.cursor() as c:
            c.execute(
                "INSERT OR REPLACE INTO data_bundles (id,cycle_id,source,ts,quality,payload,hash) VALUES (?,?,?,?,?,?,?)",
                (bundle.id, getattr(bundle, "cycle_id", ""), bundle.source, bundle.timestamp,
                 bundle.quality, json.dumps(bundle.payload), bundle.hash),
            )

    # ---- context ----
    def save_context(self, ctx) -> None:
        with self.cursor() as c:
            c.execute(
                "INSERT OR REPLACE INTO contexts (context_id,cycle_id,hash,sections) VALUES (?,?,?,?)",
                (ctx.context_id, ctx.cycle_id, ctx.hash, json.dumps(ctx.sections)),
            )

    # ---- decisions ----
    def save_decision(self, cycle_id: str, agent: int, type_: str, payload: dict) -> None:
        with self.cursor() as c:
            c.execute(
                "INSERT INTO decisions (cycle_id,agent,type,payload,ts) VALUES (?,?,?,?,?)",
                (cycle_id, agent, type_, json.dumps(redact_secrets(payload)), time.time()),
            )

    # ---- failure paths ----
    def save_failure_paths(self, cycle_id: str, paths: list) -> None:
        with self.cursor() as c:
            for p in paths:
                cat = p["category"] if isinstance(p, dict) else p.category
                sev = p["severity"] if isinstance(p, dict) else p.severity
                desc = p["description"] if isinstance(p, dict) else p.description
                c.execute(
                    "INSERT INTO failure_paths (cycle_id,category,severity,text) VALUES (?,?,?,?)",
                    (cycle_id, cat, sev, desc),
                )

    # ---- orders ----
    def save_order(self, order, status: str) -> None:
        with self.cursor() as c:
            c.execute(
                "INSERT OR REPLACE INTO orders (order_id,idempotency_key,side,instrument,size,sl,tp,status,cycle_id,ts) "
                "VALUES (?,?,?,?,?,?,?,?,?,?)",
                (order.order_id, order.idempotency_key, order.side, order.instrument,
                 order.size, order.sl, order.tp, status, order.cycle_id, time.time()),
            )

    def order_exists(self, idempotency_key: str) -> bool:
        with self.cursor() as c:
            c.execute("SELECT 1 FROM orders WHERE idempotency_key=?", (idempotency_key,))
            return c.fetchone() is not None

    # ---- risk results ----
    def save_risk_results(self, order_id: str, rules: list) -> None:
        with self.cursor() as c:
            for r in rules:
                rule = r["rule"] if isinstance(r, dict) else r.rule
                passed = r["passed"] if isinstance(r, dict) else r.passed
                reason = r["reason"] if isinstance(r, dict) else r.reason
                c.execute(
                    "INSERT INTO risk_results (order_id,rule,pass,reason,ts) VALUES (?,?,?,?,?)",
                    (order_id, rule, int(bool(passed)), reason, time.time()),
                )

    # ---- veto events ----
    def save_veto_event(self, order_id: str, notified_at: float, response: str) -> None:
        with self.cursor() as c:
            c.execute(
                "INSERT INTO veto_events (order_id,notified_at,response,ts) VALUES (?,?,?,?)",
                (order_id, notified_at, response, time.time()),
            )

    # ---- memory items ----
    def save_memory_item(self, memory_type: str, content, meta: Optional[dict] = None, agent_id: str = "") -> None:
        with self.cursor() as c:
            c.execute(
                "INSERT INTO memory_items (memory_type,agent_id,content,meta,ts) VALUES (?,?,?,?,?)",
                (memory_type, agent_id, json.dumps(redact_secrets(content)),
                 json.dumps(redact_secrets(meta or {})), time.time()),
            )

    def query_memory(self, memory_type: Optional[str] = None, limit: int = 100) -> list:
        with self.cursor() as c:
            if memory_type:
                c.execute(
                    "SELECT id,memory_type,agent_id,content,meta,ts FROM memory_items "
                    "WHERE memory_type=? ORDER BY id DESC LIMIT ?",
                    (memory_type, limit),
                )
            else:
                c.execute(
                    "SELECT id,memory_type,agent_id,content,meta,ts FROM memory_items ORDER BY id DESC LIMIT ?",
                    (limit,),
                )
            return c.fetchall()

    # ---- audit (append-only, I4) ----
    def append_audit(self, event: str, data: dict) -> None:
        with self.cursor() as c:
            c.execute(
                "INSERT INTO audit_log (ts,event,data) VALUES (?,?,?)",
                (time.time(), event, json.dumps(redact_secrets(data))),
            )

    # ---- observability ----
    def log_event(self, component: str, level: str, trace_id: str, data: dict) -> None:
        with self.cursor() as c:
            c.execute(
                "INSERT INTO observability_events (component,level,trace_id,ts,data) VALUES (?,?,?,?,?)",
                (component, level, trace_id, time.time(), json.dumps(redact_secrets(data))),
            )

    def close(self) -> None:
        self._conn.close()
