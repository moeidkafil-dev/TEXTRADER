"""
Schema initialization — 11 tables from chapter 16 DATABASE_AND_API.

Schema is idempotent: re-running `init_schema` is safe.
`audit_log` is append-only (no UPDATE/DELETE API exposed).
"""
from __future__ import annotations

from trader.storage.connection import DB, get_db


_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS cycles (
    cycle_id       TEXT PRIMARY KEY,
    started_at     TEXT NOT NULL,
    ended_at       TEXT,
    status         TEXT NOT NULL,
    reeval_count   INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS data_bundles (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    bundle_id      TEXT NOT NULL UNIQUE,
    cycle_id       TEXT NOT NULL,
    source         TEXT NOT NULL,
    ts             TEXT NOT NULL,
    quality        TEXT NOT NULL,
    payload        TEXT,            -- JSON
    hash           TEXT,
    FOREIGN KEY(cycle_id) REFERENCES cycles(cycle_id)
);

CREATE TABLE IF NOT EXISTS contexts (
    context_id     TEXT PRIMARY KEY,
    cycle_id       TEXT NOT NULL,
    hash           TEXT,
    sections       TEXT,            -- JSON
    ts             TEXT NOT NULL,
    FOREIGN KEY(cycle_id) REFERENCES cycles(cycle_id)
);

CREATE TABLE IF NOT EXISTS decisions (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    cycle_id       TEXT NOT NULL,
    agent          TEXT NOT NULL,       -- '1' | '2' | '3'
    type           TEXT NOT NULL,       -- 'initial' | 'failure' | 'final'
    payload        TEXT,               -- JSON
    ts             TEXT NOT NULL,
    FOREIGN KEY(cycle_id) REFERENCES cycles(cycle_id)
);

CREATE TABLE IF NOT EXISTS failure_paths (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    cycle_id       TEXT NOT NULL,
    category       TEXT NOT NULL,       -- F1..F9 value
    severity       TEXT NOT NULL,
    text           TEXT,
    ts             TEXT NOT NULL,
    FOREIGN KEY(cycle_id) REFERENCES cycles(cycle_id)
);

CREATE TABLE IF NOT EXISTS orders (
    order_id       TEXT PRIMARY KEY,
    cycle_id       TEXT NOT NULL,
    idempotency_key TEXT NOT NULL UNIQUE,
    side           TEXT NOT NULL,
    instrument     TEXT NOT NULL,
    size           REAL NOT NULL,
    sl             REAL,
    tp             REAL,
    status         TEXT NOT NULL,
    ts             TEXT NOT NULL,
    FOREIGN KEY(cycle_id) REFERENCES cycles(cycle_id)
);

CREATE TABLE IF NOT EXISTS risk_results (
    order_id       TEXT NOT NULL,
    rule           TEXT NOT NULL,
    pass           INTEGER NOT NULL,
    reason         TEXT,
    ts             TEXT NOT NULL,
    PRIMARY KEY(order_id, rule),
    FOREIGN KEY(order_id) REFERENCES orders(order_id)
);

CREATE TABLE IF NOT EXISTS veto_events (
    order_id       TEXT NOT NULL,
    notified_at    TEXT NOT NULL,
    response       TEXT NOT NULL,
    responded_at   TEXT,
    ts             TEXT NOT NULL,
    PRIMARY KEY(order_id, notified_at),
    FOREIGN KEY(order_id) REFERENCES orders(order_id)
);

CREATE TABLE IF NOT EXISTS memory_items (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    memory_type    TEXT NOT NULL,       -- one of 28 types (1..28) or 'agent_local'
    agent_id       TEXT,                -- nullable
    content        TEXT,                -- JSON
    meta           TEXT,                -- JSON
    ts             TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_memory_type ON memory_items(memory_type);
CREATE INDEX IF NOT EXISTS idx_memory_agent ON memory_items(agent_id);

CREATE TABLE IF NOT EXISTS audit_log (
    record_id      TEXT PRIMARY KEY,
    cycle_id       TEXT NOT NULL,
    component      TEXT NOT NULL,
    event          TEXT NOT NULL,
    payload_hash   TEXT NOT NULL,
    ts             TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_audit_cycle ON audit_log(cycle_id);

CREATE TABLE IF NOT EXISTS observability_events (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    component      TEXT NOT NULL,
    level          TEXT NOT NULL,
    trace_id       TEXT NOT NULL,
    cycle_id       TEXT,
    data           TEXT,                -- JSON
    ts             TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_obs_cycle ON observability_events(cycle_id);
CREATE INDEX IF NOT EXISTS idx_obs_level ON observability_events(level);

CREATE TABLE IF NOT EXISTS portfolio_state (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    equity         REAL NOT NULL,
    peak_equity    REAL NOT NULL,
    cash           REAL NOT NULL,
    positions      TEXT,                -- JSON
    realized_pnl   REAL DEFAULT 0,
    unrealized_pnl REAL DEFAULT 0,
    daily_loss     REAL DEFAULT 0,
    ts             TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS state_machine_log (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    cycle_id       TEXT,
    from_state     TEXT NOT NULL,
    transition     TEXT NOT NULL,
    to_state       TEXT NOT NULL,
    ts             TEXT NOT NULL
);
"""


def init_schema(db: DB | None = None) -> None:
    """Apply the schema (idempotent)."""
    if db is None:
        db = get_db()
    db._conn.executescript(_SCHEMA_SQL)
    db._conn.commit()
