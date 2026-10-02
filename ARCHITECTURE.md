# TEXTRADER X — Architecture

## 1. Architectural Intent

TEXTRADER X is organized as a layered decision-engineering system.

```mermaid
flowchart LR
    DATA["Market / Manual Data"]
    ADAPTER["Adapters"]
    CONTEXT["Context"]
    AGENT["Super-Agent"]
    SIZE["Position Sizer"]
    RISK["Risk Engine"]
    SAFETY["Safety Interlocks"]
    EXEC["Execution"]
    MEMORY["Memory"]
    AUDIT["Audit"]
    API["FastAPI"]
    CLI["CLI"]

    DATA --> ADAPTER
    ADAPTER --> CONTEXT
    CONTEXT --> AGENT
    AGENT --> SIZE
    SIZE --> RISK
    RISK --> SAFETY
    SAFETY --> EXEC
    EXEC --> MEMORY
    MEMORY --> AUDIT
    API --> AGENT
    CLI --> AGENT
```

## 2. Core Principles

1. Explicit component boundaries.
2. Separation of decision and execution.
3. Deterministic risk gates.
4. Safety-first failure boundaries.
5. Persistent state and auditability.
6. Reproducible validation.
7. Historical provenance.
8. Clear operator interfaces.

## 3. Failure Boundary

```mermaid
flowchart TD
    INPUT["Input"]
    VALIDATE["Validation"]
    DECISION["Decision"]
    RISK["Risk Gate"]
    EXEC["Execution Gate"]
    FAIL["Safe Failure"]
    AUDIT["Audit"]

    INPUT --> VALIDATE
    VALIDATE -->|valid| DECISION
    VALIDATE -->|invalid| FAIL
    DECISION --> RISK
    RISK -->|approved| EXEC
    RISK -->|rejected| FAIL
    EXEC -->|failure| FAIL
    EXEC -->|success| AUDIT
    FAIL --> AUDIT
```

## 4. Control Plane

CLI and web interfaces are control/observability surfaces. Core business logic
should remain testable independently of the presentation layer.

## 5. Historical Boundary

Release-specific source and documentation are preserved under `releases/`.
Provenance is recorded under `provenance/`.
