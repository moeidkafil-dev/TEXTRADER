"""
Schemas — JSON-equivalent data contracts for the system.

These mirror `04_FORMAL_SYSTEM_SPECIFICATION/AGENT_AND_TOOL_PROTOCOL.md` 1:1:
  InitialDecision, FailureReport, FinalDecision, ExecutionOrder, RiskResult

Plus the auxiliary contracts used by internal services:
  DataBundle, Context, AuditRecord, VetoEvent, ObservabilityEvent, ExecutionResult

All schemas are validated before being trusted. An invalid agent output ⇒ WAIT
(invariant I5). All schemas are immutable `dataclass(frozen=True)` to make audit
integrity easy to enforce.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _uuid() -> str:
    return str(uuid.uuid4())


# ----------------------------------------------------------------------------
# Enums
# ----------------------------------------------------------------------------

class Action(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    WAIT = "WAIT"
    RE_EVALUATE = "RE-EVALUATE"  # FinalDecision only

    @classmethod
    def values(cls) -> set[str]:
        return {a.value for a in cls if a != cls.RE_EVALUATE}

    @classmethod
    def final_values(cls) -> set[str]:
        return {a.value for a in cls}


class FailureCategory(str, Enum):
    F1_WRONG_PREDICTION = "wrong_prediction"
    F2_LOGICAL_INCONSISTENCY = "logical_inconsistency"
    F3_MISSING_DATA = "missing_data"
    F4_INVALID_ASSUMPTION = "invalid_assumption"
    F5_RISK_VIOLATION = "risk_violation"
    F6_CONTRADICTORY_EVIDENCE = "contradictory_evidence"
    F7_TOOL_FAILURE = "tool_failure"
    F8_MODEL_UNCERTAINTY = "model_uncertainty"
    F9_EXECUTION_IMPOSSIBILITY = "execution_impossibility"

    @classmethod
    def all(cls) -> list["FailureCategory"]:
        return list(cls)


class Severity(str, Enum):
    LOW = "low"
    MED = "med"
    HIGH = "high"
    BLOCKING = "blocking"


class Side(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class RunMode(str, Enum):
    BACKTEST = "backtest"
    PAPER = "paper"
    LIVE = "live"


class VetoResponse(str, Enum):
    SILENCE = "SILENCE"
    OK = "OK"
    REJECT = "REJECT"
    STOP = "STOP"
    WAIT = "WAIT"  # explicit non-execution outcome for on_silence=wait


class OrderStatus(str, Enum):
    DRAFT = "draft"
    VALIDATED = "validated"
    RISK_PASS = "risk_pass"
    GUARD_PASS = "guard_pass"
    SUBMITTED = "submitted"
    FILLED = "filled"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


# ----------------------------------------------------------------------------
# Data Reader / Context
# ----------------------------------------------------------------------------

@dataclass(frozen=True)
class DataBundle:
    source: str
    timestamp: datetime
    quality: str  # "ok" | "missing" | "stale" | "partial"
    payload: dict[str, Any]
    bundle_id: str = field(default_factory=_uuid)
    hash: str = ""

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["timestamp"] = self.timestamp.isoformat()
        return d


@dataclass(frozen=True)
class ContextSection:
    name: str
    source: str
    version: str
    data: dict[str, Any]
    empty: bool = False


@dataclass(frozen=True)
class Context:
    context_id: str = field(default_factory=_uuid)
    cycle_id: str = ""
    sections: tuple[ContextSection, ...] = ()
    hash: str = ""

    def section(self, name: str) -> Optional[ContextSection]:
        for s in self.sections:
            if s.name == name:
                return s
        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "context_id": self.context_id,
            "cycle_id": self.cycle_id,
            "hash": self.hash,
            "sections": [
                {"name": s.name, "source": s.source, "version": s.version,
                 "empty": s.empty, "data": s.data}
                for s in self.sections
            ],
        }


# ----------------------------------------------------------------------------
# Agent outputs (chapter 04 protocol)
# ----------------------------------------------------------------------------

@dataclass(frozen=True)
class InitialDecision:
    cycle_id: str
    action: str            # BUY | SELL | WAIT
    instrument: str
    rationale: str
    assumptions: tuple[str, ...] = ()
    evidence: tuple[str, ...] = ()
    ts: datetime = field(default_factory=_utcnow)

    def to_dict(self) -> dict[str, Any]:
        return {
            "cycle_id": self.cycle_id,
            "action": self.action,
            "instrument": self.instrument,
            "rationale": self.rationale,
            "assumptions": list(self.assumptions),
            "evidence": list(self.evidence),
            "ts": self.ts.isoformat(),
        }


@dataclass(frozen=True)
class FailurePath:
    category: str       # FailureCategory value
    description: str
    severity: str       # Severity value


@dataclass(frozen=True)
class FailureReport:
    cycle_id: str
    paths: tuple[FailurePath, ...] = ()
    ts: datetime = field(default_factory=_utcnow)

    def categories_covered(self) -> set[str]:
        return {p.category for p in self.paths}

    def has_blocking(self) -> bool:
        return any(p.severity == Severity.BLOCKING.value for p in self.paths)

    def to_dict(self) -> dict[str, Any]:
        return {
            "cycle_id": self.cycle_id,
            "paths": [
                {"category": p.category, "description": p.description,
                 "severity": p.severity}
                for p in self.paths
            ],
            "ts": self.ts.isoformat(),
        }


@dataclass(frozen=True)
class FinalDecision:
    cycle_id: str
    decision: str       # Action.final_values()
    overrode_initial: bool
    reason: str
    ts: datetime = field(default_factory=_utcnow)

    def to_dict(self) -> dict[str, Any]:
        return {
            "cycle_id": self.cycle_id,
            "decision": self.decision,
            "overrode_initial": self.overrode_initial,
            "reason": self.reason,
            "ts": self.ts.isoformat(),
        }


@dataclass(frozen=True)
class ExecutionOrder:
    order_id: str = field(default_factory=_uuid)
    idempotency_key: str = field(default_factory=_uuid)
    cycle_id: str = ""
    side: str = ""       # Side.BUY | Side.SELL
    instrument: str = ""
    size: float = 0.0
    sl: float = 0.0
    tp: float = 0.0
    ts: datetime = field(default_factory=_utcnow)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["ts"] = self.ts.isoformat()
        return d


@dataclass(frozen=True)
class RuleResult:
    rule: str
    passed: bool
    reason: str = ""


@dataclass(frozen=True)
class RiskResult:
    order_id: str
    rules: tuple[RuleResult, ...] = ()
    passed: bool = True
    ts: datetime = field(default_factory=_utcnow)

    def rejected_by(self) -> list[str]:
        return [r.rule for r in self.rules if not r.passed]

    def to_dict(self) -> dict[str, Any]:
        return {
            "order_id": self.order_id,
            "rules": [
                {"rule": r.rule, "pass": r.passed, "reason": r.reason}
                for r in self.rules
            ],
            "passed": self.passed,
            "ts": self.ts.isoformat(),
        }


# ----------------------------------------------------------------------------
# Message / Veto
# ----------------------------------------------------------------------------

@dataclass(frozen=True)
class VetoEvent:
    order_id: str
    notified_at: datetime
    response: str = VetoResponse.SILENCE.value
    responded_at: Optional[datetime] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "order_id": self.order_id,
            "notified_at": self.notified_at.isoformat(),
            "response": self.response,
            "responded_at": self.responded_at.isoformat() if self.responded_at else None,
        }


# ----------------------------------------------------------------------------
# Execution
# ----------------------------------------------------------------------------

@dataclass(frozen=True)
class ExecutionResult:
    order_id: str
    status: str        # OrderStatus value
    fill_price: Optional[float] = None
    fill_size: Optional[float] = None
    broker_ack: str = ""
    ts: datetime = field(default_factory=_utcnow)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["ts"] = self.ts.isoformat()
        return d


# ----------------------------------------------------------------------------
# Observability & Audit
# ----------------------------------------------------------------------------

@dataclass(frozen=True)
class ObservabilityEvent:
    component: str
    level: str          # "debug" | "info" | "warn" | "error"
    trace_id: str
    cycle_id: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    ts: datetime = field(default_factory=_utcnow)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["ts"] = self.ts.isoformat()
        return d


@dataclass(frozen=True)
class AuditRecord:
    cycle_id: str
    component: str
    event: str
    payload_hash: str
    ts: datetime = field(default_factory=_utcnow)
    record_id: str = field(default_factory=_uuid)


# ----------------------------------------------------------------------------
# Validation helpers — invariant I5
# ----------------------------------------------------------------------------

def is_valid_initial(d: InitialDecision) -> bool:
    return d.action in Action.values() and bool(d.instrument) and bool(d.rationale)


def is_valid_failure_report(r: FailureReport) -> bool:
    covered = r.categories_covered()
    # Must report explicitly on all 9 categories (missing ⇒ model_uncertainty F8).
    if len(covered) != len(FailureCategory.all()):
        # Missing categories must be represented at least as F8 model_uncertainty.
        return False
    for p in r.paths:
        if p.category not in {c.value for c in FailureCategory.all()}:
            return False
        if p.severity not in {s.value for s in Severity}:
            return False
    return True


def is_valid_final(d: FinalDecision) -> bool:
    return d.decision in Action.final_values() and bool(d.reason)


def is_valid_order(o: ExecutionOrder) -> bool:
    return (o.side in {s.value for s in Side}
            and bool(o.instrument)
            and o.size > 0
            and bool(o.idempotency_key))
