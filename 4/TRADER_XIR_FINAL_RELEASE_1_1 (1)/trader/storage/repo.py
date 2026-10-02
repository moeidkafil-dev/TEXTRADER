"""Repository layer — thin CRUD helpers over the 11 tables."""
from __future__ import annotations

import json
from typing import Any, Optional

from trader.storage.connection import DB, get_db
from trader.core.schemas import (
    DataBundle, Context, InitialDecision, FailureReport, FinalDecision,
    ExecutionOrder, RiskResult, VetoEvent, ObservabilityEvent, AuditRecord,
)
from trader.core.util import now_ts


# ---------------- cycles ----------------

def insert_cycle(db: DB, cycle_id: str, started_at: str, status: str, reeval_count: int = 0) -> None:
    db.execute(
        "INSERT OR REPLACE INTO cycles (cycle_id, started_at, status, reeval_count) VALUES (?, ?, ?, ?)",
        (cycle_id, started_at, status, reeval_count),
    )

def update_cycle_status(db: DB, cycle_id: str, status: str, ended_at: Optional[str] = None,
                       reeval_count: Optional[int] = None) -> None:
    if ended_at is None and reeval_count is None:
        db.execute("UPDATE cycles SET status=? WHERE cycle_id=?", (status, cycle_id))
    elif ended_at is None:
        db.execute("UPDATE cycles SET status=?, reeval_count=? WHERE cycle_id=?",
                   (status, reeval_count, cycle_id))
    elif reeval_count is None:
        db.execute("UPDATE cycles SET status=?, ended_at=? WHERE cycle_id=?",
                   (status, ended_at, cycle_id))
    else:
        db.execute("UPDATE cycles SET status=?, ended_at=?, reeval_count=? WHERE cycle_id=?",
                   (status, ended_at, reeval_count, cycle_id))

def get_cycle(db: DB, cycle_id: str) -> Optional[dict]:
    row = db.query_one("SELECT * FROM cycles WHERE cycle_id=?", (cycle_id,))
    return dict(row) if row else None


# ---------------- data_bundles ----------------

def insert_data_bundle(db: DB, b: DataBundle, cycle_id: str) -> None:
    db.execute(
        "INSERT OR IGNORE INTO data_bundles (bundle_id, cycle_id, source, ts, quality, payload, hash) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (b.bundle_id, cycle_id, b.source, b.timestamp.isoformat(), b.quality,
         json.dumps(b.payload, default=str), b.hash),
    )

def list_data_bundles(db: DB, cycle_id: str) -> list[dict]:
    rows = db.query("SELECT * FROM data_bundles WHERE cycle_id=? ORDER BY ts", (cycle_id,))
    return [dict(r) for r in rows]


# ---------------- contexts ----------------

def insert_context(db: DB, ctx: Context) -> None:
    db.execute(
        "INSERT OR IGNORE INTO contexts (context_id, cycle_id, hash, sections, ts) VALUES (?, ?, ?, ?, ?)",
        (ctx.context_id, ctx.cycle_id, ctx.hash, json.dumps(ctx.to_dict(), default=str),
         now_ts()),
    )


# ---------------- decisions ----------------

def insert_initial_decision(db: DB, d: InitialDecision) -> None:
    db.execute(
        "INSERT INTO decisions (cycle_id, agent, type, payload, ts) VALUES (?, ?, ?, ?, ?)",
        (d.cycle_id, "1", "initial", json.dumps(d.to_dict(), default=str), d.ts.isoformat()),
    )

def insert_failure_report(db: DB, r: FailureReport) -> None:
    db.execute(
        "INSERT INTO decisions (cycle_id, agent, type, payload, ts) VALUES (?, ?, ?, ?, ?)",
        (r.cycle_id, "2", "failure", json.dumps(r.to_dict(), default=str), r.ts.isoformat()),
    )
    for p in r.paths:
        db.execute(
            "INSERT INTO failure_paths (cycle_id, category, severity, text, ts) VALUES (?, ?, ?, ?, ?)",
            (r.cycle_id, p.category, p.severity, p.description, r.ts.isoformat()),
        )

def insert_final_decision(db: DB, d: FinalDecision) -> None:
    db.execute(
        "INSERT INTO decisions (cycle_id, agent, type, payload, ts) VALUES (?, ?, ?, ?, ?)",
        (d.cycle_id, "3", "final", json.dumps(d.to_dict(), default=str), d.ts.isoformat()),
    )

def list_decisions(db: DB, cycle_id: str) -> list[dict]:
    rows = db.query("SELECT * FROM decisions WHERE cycle_id=? ORDER BY id", (cycle_id,))
    return [dict(r) for r in rows]


# ---------------- orders ----------------

def insert_order(db: DB, o: ExecutionOrder, status: str = "draft") -> None:
    db.execute(
        "INSERT OR IGNORE INTO orders (order_id, cycle_id, idempotency_key, side, instrument, size, sl, tp, status, ts) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (o.order_id, o.cycle_id, o.idempotency_key, o.side, o.instrument, o.size, o.sl, o.tp,
         status, o.ts.isoformat()),
    )

def update_order_status(db: DB, order_id: str, status: str) -> None:
    db.execute("UPDATE orders SET status=? WHERE order_id=?", (status, order_id))

def get_order_by_idempotency(db: DB, idempotency_key: str) -> Optional[dict]:
    row = db.query_one("SELECT * FROM orders WHERE idempotency_key=?", (idempotency_key,))
    return dict(row) if row else None

def get_order(db: DB, order_id: str) -> Optional[dict]:
    row = db.query_one("SELECT * FROM orders WHERE order_id=?", (order_id,))
    return dict(row) if row else None


# ---------------- risk_results ----------------

def insert_risk_result(db: DB, r: RiskResult) -> None:
    for rule in r.rules:
        db.execute(
            "INSERT OR REPLACE INTO risk_results (order_id, rule, pass, reason, ts) VALUES (?, ?, ?, ?, ?)",
            (r.order_id, rule.rule, 1 if rule.passed else 0, rule.reason, r.ts.isoformat()),
        )

def get_risk_results(db: DB, order_id: str) -> list[dict]:
    rows = db.query("SELECT * FROM risk_results WHERE order_id=?", (order_id,))
    return [dict(r) for r in rows]


# ---------------- veto_events ----------------

def insert_veto_event(db: DB, v: VetoEvent) -> None:
    db.execute(
        "INSERT OR IGNORE INTO veto_events (order_id, notified_at, response, responded_at, ts) VALUES (?, ?, ?, ?, ?)",
        (v.order_id, v.notified_at.isoformat(), v.response,
         v.responded_at.isoformat() if v.responded_at else None, now_ts()),
    )


# ---------------- memory_items ----------------

def insert_memory_item(db: DB, memory_type: str, content: Any, agent_id: Optional[str] = None,
                      meta: Optional[dict] = None) -> int:
    cur = db.execute(
        "INSERT INTO memory_items (memory_type, agent_id, content, meta, ts) VALUES (?, ?, ?, ?, ?)",
        (memory_type, agent_id, json.dumps(content, default=str),
         json.dumps(meta or {}, default=str), now_ts()),
    )
    return cur.lastrowid  # type: ignore[return-value]

def list_memory_items(db: DB, memory_type: Optional[str] = None,
                     agent_id: Optional[str] = None, limit: int = 100) -> list[dict]:
    sql = "SELECT * FROM memory_items WHERE 1=1"
    params: list[Any] = []
    if memory_type:
        sql += " AND memory_type=?"
        params.append(memory_type)
    if agent_id:
        sql += " AND agent_id=?"
        params.append(agent_id)
    sql += " ORDER BY id DESC LIMIT ?"
    params.append(limit)
    rows = db.query(sql, tuple(params))
    return [dict(r) for r in rows]

def delete_memory_item(db: DB, rowid: int) -> None:
    """Used by Memory Manager 'tables cleaner' to drop junk.
    Audit memory (memory_type='Audit / History Memory') is never deleted here."""
    db.execute("DELETE FROM memory_items WHERE id=?", (rowid,))


# ---------------- audit_log (append-only) ----------------

def insert_audit(db: DB, r: AuditRecord) -> None:
    db.execute(
        "INSERT OR IGNORE INTO audit_log (record_id, cycle_id, component, event, payload_hash, ts) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (r.record_id, r.cycle_id, r.component, r.event, r.payload_hash, r.ts.isoformat()),
    )

def list_audit(db: DB, cycle_id: Optional[str] = None, limit: int = 100) -> list[dict]:
    if cycle_id:
        rows = db.query("SELECT * FROM audit_log WHERE cycle_id=? ORDER BY id DESC LIMIT ?",
                        (cycle_id, limit))
    else:
        rows = db.query("SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (limit,))
    return [dict(r) for r in rows]


# ---------------- observability_events ----------------

def insert_observability(db: DB, e: ObservabilityEvent) -> None:
    db.execute(
        "INSERT INTO observability_events (component, level, trace_id, cycle_id, data, ts) VALUES (?, ?, ?, ?, ?, ?)",
        (e.component, e.level, e.trace_id, e.cycle_id, json.dumps(e.data, default=str), e.ts.isoformat()),
    )

def list_observability(db: DB, cycle_id: Optional[str] = None, level: Optional[str] = None,
                      limit: int = 200) -> list[dict]:
    sql = "SELECT * FROM observability_events WHERE 1=1"
    params: list[Any] = []
    if cycle_id:
        sql += " AND cycle_id=?"
        params.append(cycle_id)
    if level:
        sql += " AND level=?"
        params.append(level)
    sql += " ORDER BY id DESC LIMIT ?"
    params.append(limit)
    rows = db.query(sql, tuple(params))
    return [dict(r) for r in rows]


# ---------------- portfolio_state ----------------

def upsert_portfolio_state(db: DB, equity: float, peak_equity: float, cash: float,
                           positions: dict, realized_pnl: float, unrealized_pnl: float,
                           daily_loss: float) -> None:
    db.execute(
        "INSERT INTO portfolio_state (equity, peak_equity, cash, positions, realized_pnl, "
        "unrealized_pnl, daily_loss, ts) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (equity, peak_equity, cash, json.dumps(positions, default=str),
         realized_pnl, unrealized_pnl, daily_loss, now_ts()),
    )

def latest_portfolio_state(db: DB) -> Optional[dict]:
    row = db.query_one("SELECT * FROM portfolio_state ORDER BY id DESC LIMIT 1")
    if row:
        d = dict(row)
        d["positions"] = json.loads(d["positions"] or "{}")
        return d
    return None


# ---------------- state_machine_log ----------------

def log_state_transition(db: DB, from_state: str, transition: str, to_state: str,
                        cycle_id: Optional[str] = None) -> None:
    db.execute(
        "INSERT INTO state_machine_log (cycle_id, from_state, transition, to_state, ts) VALUES (?, ?, ?, ?, ?)",
        (cycle_id, from_state, transition, to_state, now_ts()),
    )
