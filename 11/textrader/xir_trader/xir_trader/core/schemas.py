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


@dataclass
class DataBundle:
    """REQ-DR-01: DataBundle{source,timestamp,quality,payload}"""
    source: str
    timestamp: float
    quality: str  # "ok" | "degraded" | "missing"
    payload: dict = field(default_factory=dict)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    hash: Optional[str] = None


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

    def validate(self) -> "InitialDecision":
        if self.action not in (Action.BUY, Action.SELL, Action.WAIT):
            raise SchemaError(f"InitialDecision.action invalid: {self.action}")
        if not self.instrument:
            raise SchemaError("InitialDecision.instrument required")
        return self


@dataclass
class FailurePath:
    category: str
    description: str
    severity: str

    def validate(self) -> "FailurePath":
        if self.category not in [c.value for c in FailureCategory]:
            raise SchemaError(f"FailurePath.category invalid: {self.category}")
        if self.severity not in [s.value for s in Severity]:
            raise SchemaError(f"FailurePath.severity invalid: {self.severity}")
        return self


@dataclass
class FailureReport:
    """REQ-AG-03: must cover all 9 categories; empty category reported explicitly."""
    cycle_id: str
    paths: list = field(default_factory=list)  # list[FailurePath]

    def validate(self) -> "FailureReport":
        covered = {p["category"] if isinstance(p, dict) else p.category for p in self.paths}
        missing = set(c.value for c in FailureCategory) - covered
        if missing:
            raise SchemaError(f"FailureReport missing categories: {sorted(missing)}")
        return self

    def has_blocking(self) -> bool:
        for p in self.paths:
            sev = p["severity"] if isinstance(p, dict) else p.severity
            if sev == Severity.BLOCKING.value:
                return True
        return False


@dataclass
class FinalDecision:
    cycle_id: str
    decision: str  # BUY | SELL | WAIT | RE-EVALUATE
    overrode_initial: bool
    reason: str

    def validate(self) -> "FinalDecision":
        if self.decision not in [a.value for a in FinalAction]:
            raise SchemaError(f"FinalDecision.decision invalid: {self.decision}")
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
        if self.size <= 0:
            raise SchemaError("ExecutionOrder.size must be > 0")
        return self


@dataclass
class RiskRuleResult:
    rule: str
    passed: bool
    reason: str


@dataclass
class RiskResult:
    order_id: str
    rules: list = field(default_factory=list)  # list[RiskRuleResult]

    @property
    def passed(self) -> bool:
        return all(r["passed"] if isinstance(r, dict) else r.passed for r in self.rules)

    def first_failure(self) -> Optional[Any]:
        for r in self.rules:
            passed = r["passed"] if isinstance(r, dict) else r.passed
            if not passed:
                return r
        return None
