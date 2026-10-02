"""
Data contracts. Mirrors the JSON schemas in
04_FORMAL_SYSTEM_SPECIFICATION/AGENT_AND_TOOL_PROTOCOL.md exactly
(field names and enums unchanged — REQ-AG-* / REQ-EX-*).

Rule (protocol doc): "خروجی LLM قبل از استفاده با schema اعتبارسنجی
می‌شود؛ شکست = WAIT." -> validate_* functions below raise SchemaError;
callers must convert that into a WAIT decision (invariant I5).
"""
from __future__ import annotations

import time
import uuid
import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class SchemaError(ValueError):
    """Raised when agent/tool output does not conform to protocol. -> caller must WAIT (I5)."""


class Action(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    WAIT = "WAIT"


class FinalAction(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    WAIT = "WAIT"
    RE_EVALUATE = "RE-EVALUATE"


class FailureCategory(str, Enum):
    """F1..F9 per 06_DECISION_AND_FAILURE_MODEL/DECISION_AND_FAILURE_MODEL.md"""
    WRONG_PREDICTION = "wrong_prediction"          # F1
    LOGICAL_INCONSISTENCY = "logical_inconsistency"  # F2
    MISSING_DATA = "missing_data"                   # F3
    INVALID_ASSUMPTION = "invalid_assumption"        # F4
    RISK_VIOLATION = "risk_violation"                # F5
    CONTRADICTORY_EVIDENCE = "contradictory_evidence"  # F6
    TOOL_FAILURE = "tool_failure"                    # F7
    MODEL_UNCERTAINTY = "model_uncertainty"           # F8
    EXECUTION_IMPOSSIBILITY = "execution_impossibility"  # F9


ALL_FAILURE_CATEGORIES = list(FailureCategory)  # Agent 2 must report on all 9 (REQ-AG-03)


class Severity(str, Enum):
    LOW = "low"
    MED = "med"
    HIGH = "high"
    BLOCKING = "blocking"


class VetoResponse(str, Enum):
    OK = "OK"
    REJECT = "REJECT"
    STOP = "STOP"
    SILENCE = "SILENCE"


def _now() -> float:
    return time.time()


def _finite_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


@dataclass
class DataBundle:
    """REQ-DR-01: DataBundle{source,timestamp,quality,payload}"""
    source: str
    timestamp: float
    quality: str  # VALID | STALE | MISSING | INVALID | PARTIAL
    payload: dict = field(default_factory=dict)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    hash: Optional[str] = None
    critical: bool = False


@dataclass
class Context:
    """REQ-DR-03: Context{context_id,hash,sections}
    sections must cover all 5: data, memory, previous_decisions, market_state, user_config
    (missing -> flagged empty, never dropped, per PRD constraint).
    """
    context_id: str
    cycle_id: str
    hash: str
    sections: dict  # keys: data, memory, previous_decisions, market_state, user_config


@dataclass
class InitialDecision:
    cycle_id: str
    action: str            # BUY | SELL | WAIT
    instrument: str
    rationale: str
    assumptions: list = field(default_factory=list)
    evidence: list = field(default_factory=list)
    confidence: float = 0.0
    stop_loss: float = 0.0
    take_profit: float = 0.0
    validated: bool = True  # set only by the local schema/data-validation boundary

    def validate(self) -> "InitialDecision":
        if self.action not in (Action.BUY.value, Action.SELL.value, Action.WAIT.value):
            raise SchemaError(f"InitialDecision.action invalid: {self.action}")
        if not isinstance(self.instrument, str) or not self.instrument.strip():
            raise SchemaError("InitialDecision.instrument required")
        if not isinstance(self.rationale, str) or not self.rationale.strip():
            raise SchemaError("InitialDecision.rationale required")
        if not isinstance(self.assumptions, list) or not all(isinstance(x, str) for x in self.assumptions):
            raise SchemaError("InitialDecision.assumptions must be a list of strings")
        if not isinstance(self.evidence, list) or not all(isinstance(x, str) and x.strip() for x in self.evidence):
            raise SchemaError("InitialDecision.evidence must be a list of non-empty strings")
        if not _finite_number(self.confidence) or not 0 <= self.confidence <= 1:
            raise SchemaError("InitialDecision.confidence must be finite and in [0, 1]")
        if not isinstance(self.validated, bool):
            raise SchemaError("InitialDecision.validated must be boolean")
        for name, value in (("stop_loss", self.stop_loss), ("take_profit", self.take_profit)):
            if not _finite_number(value) or value < 0:
                raise SchemaError(f"InitialDecision.{name} must be finite and non-negative")
        if self.action in (Action.BUY.value, Action.SELL.value) and not self.evidence:
            raise SchemaError("trade decisions require cited evidence")
        return self


@dataclass
class FailurePath:
    category: str
    description: str
    severity: str
    failure_found: bool = False
    blocking: bool = False
    evidence: list = field(default_factory=list)
    counter_evidence: list = field(default_factory=list)
    assumption: str = ""
    confidence: float = 0.0

    def validate(self) -> "FailurePath":
        if self.category not in [c.value for c in FailureCategory]:
            raise SchemaError(f"FailurePath.category invalid: {self.category}")
        if self.severity not in [s.value for s in Severity]:
            raise SchemaError(f"FailurePath.severity invalid: {self.severity}")
        if not isinstance(self.description, str) or not self.description.strip():
            raise SchemaError("FailurePath.description required")
        if not isinstance(self.failure_found, bool) or not isinstance(self.blocking, bool):
            raise SchemaError("FailurePath flags must be booleans")
        if self.severity == Severity.BLOCKING.value:
            self.blocking = True
        if self.blocking and not self.failure_found:
            self.failure_found = True
        if not isinstance(self.evidence, list) or not all(isinstance(x, str) and x.strip() for x in self.evidence):
            raise SchemaError("FailurePath.evidence must be a list of non-empty strings")
        if not self.evidence:
            raise SchemaError("FailurePath must cite evidence or the inspected scope")
        if not isinstance(self.counter_evidence, list) or not all(isinstance(x, str) for x in self.counter_evidence):
            raise SchemaError("FailurePath.counter_evidence must be a list of strings")
        if not isinstance(self.assumption, str):
            raise SchemaError("FailurePath.assumption must be a string")
        if not _finite_number(self.confidence) or not 0 <= self.confidence <= 1:
            raise SchemaError("FailurePath.confidence must be finite and in [0, 1]")
        return self


@dataclass
class FailureReport:
    """REQ-AG-03: must cover all 9 categories; empty category reported explicitly."""
    cycle_id: str
    paths: list = field(default_factory=list)  # list[FailurePath]

    def validate(self) -> "FailureReport":
        if not isinstance(self.paths, list):
            raise SchemaError("FailureReport.paths must be a list")
        for p in self.paths:
            if isinstance(p, dict):
                try:
                    FailurePath(**p).validate()
                except (TypeError, SchemaError) as exc:
                    raise SchemaError(f"invalid failure path: {exc}") from exc
            elif not isinstance(p, FailurePath):
                raise SchemaError("FailureReport paths must be FailurePath objects")
            else:
                p.validate()
        covered = {p["category"] if isinstance(p, dict) else p.category for p in self.paths}
        missing = set(c.value for c in FailureCategory) - covered
        if missing:
            raise SchemaError(f"FailureReport missing categories: {sorted(missing)}")
        if len(self.paths) != len(ALL_FAILURE_CATEGORIES) or len(covered) != len(self.paths):
            raise SchemaError("FailureReport must contain exactly one path for each failure category")
        return self

    def has_blocking(self) -> bool:
        for p in self.paths:
            sev = p["severity"] if isinstance(p, dict) else p.severity
            blocking = p.get("blocking", False) if isinstance(p, dict) else p.blocking
            if sev == Severity.BLOCKING.value or blocking:
                return True
        return False


@dataclass
class FinalDecision:
    cycle_id: str
    decision: str  # BUY | SELL | WAIT | RE-EVALUATE
    overrode_initial: bool
    reason: str
    confidence: float = 0.0
    supporting_evidence: list = field(default_factory=list)
    blocking_issues: list = field(default_factory=list)
    risk_summary: str = ""
    agent1_decision: str = ""
    agent2_findings: list = field(default_factory=list)
    stop_loss: float = 0.0
    take_profit: float = 0.0

    def validate(self) -> "FinalDecision":
        if self.decision not in [a.value for a in FinalAction]:
            raise SchemaError(f"FinalDecision.decision invalid: {self.decision}")
        if not isinstance(self.reason, str) or not self.reason.strip():
            raise SchemaError("FinalDecision.reason required")
        if not isinstance(self.overrode_initial, bool):
            raise SchemaError("FinalDecision.overrode_initial must be boolean")
        if not _finite_number(self.confidence) or not 0 <= self.confidence <= 1:
            raise SchemaError("FinalDecision.confidence must be finite and in [0, 1]")
        for name, collection in (("supporting_evidence", self.supporting_evidence), ("blocking_issues", self.blocking_issues)):
            if not isinstance(collection, list) or not all(isinstance(x, str) for x in collection):
                raise SchemaError(f"FinalDecision.{name} must be a list of strings")
        if not isinstance(self.agent1_decision, str) or not isinstance(self.agent2_findings, list):
            raise SchemaError("FinalDecision agent trace fields have invalid types")
        for name, numeric_value in (("stop_loss", self.stop_loss), ("take_profit", self.take_profit)):
            if not _finite_number(numeric_value) or numeric_value < 0:
                raise SchemaError(f"FinalDecision.{name} must be finite and non-negative")
        return self


@dataclass
class ExecutionOrder:
    side: str
    instrument: str
    size: float
    sl: float = 0.0
    tp: float = 0.0
    order_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    idempotency_key: str = ""
    cycle_id: str = ""

    def __post_init__(self):
        if not self.idempotency_key:
            # deterministic per (cycle, side, instrument) so retries don't duplicate (P-04)
            self.idempotency_key = f"{self.cycle_id}:{self.side}:{self.instrument}"

    def validate(self) -> "ExecutionOrder":
        if self.side not in (Action.BUY.value, Action.SELL.value):
            raise SchemaError(f"ExecutionOrder.side invalid: {self.side}")
        if not isinstance(self.instrument, str) or not self.instrument.strip():
            raise SchemaError("ExecutionOrder.instrument required")
        for name, value in (("size", self.size), ("sl", self.sl), ("tp", self.tp)):
            if not _finite_number(value):
                raise SchemaError(f"ExecutionOrder.{name} must be finite")
        if self.size <= 0:
            raise SchemaError("ExecutionOrder.size must be > 0")
        if self.sl < 0 or self.tp < 0:
            raise SchemaError("ExecutionOrder.sl/tp must not be negative")
        if not self.cycle_id:
            raise SchemaError("ExecutionOrder.cycle_id required")
        expected_key = f"{self.cycle_id}:{self.side}:{self.instrument}"
        if self.idempotency_key != expected_key:
            raise SchemaError("ExecutionOrder.idempotency_key does not match order intent")
        return self


@dataclass
class RiskRuleResult:
    rule: str
    passed: bool
    reason: str
    observed: Any = None
    limit: Any = None


@dataclass
class RiskResult:
    order_id: str
    rules: list = field(default_factory=list)  # list[RiskRuleResult]
    # Only RiskEngine can produce a valid authorization for the exact order
    # and rule set. A dataclass assembled by a caller has no authorization.
    authorization: str | None = field(default=None, repr=False, compare=False)

    @property
    def passed(self) -> bool:
        return all(r["passed"] if isinstance(r, dict) else r.passed for r in self.rules)

    def first_failure(self) -> Optional[Any]:
        for r in self.rules:
            passed = r["passed"] if isinstance(r, dict) else r.passed
            if not passed:
                return r
        return None
