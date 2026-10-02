# Master Technical Specification

## 1. System principles
1. Deterministic state over hidden state.
2. Explicit contracts between components.
3. Every decision is traceable.
4. AI output is untrusted input until validated.
5. Risk policies are explicit.
6. Execution is guarded.
7. Fail closed on safety-critical uncertainty.
8. All external integrations are adapter-based.
9. Replayability is a first-class feature.
10. Configuration is versioned.

## 2. Core domain objects

### MarketSnapshot
- timestamp
- instrument
- venue
- OHLCV / order-book fields as available
- source
- freshness
- quality flags

### Context
- market state
- historical window
- portfolio state
- strategy state
- relevant memory
- constraints
- external information
- context version

### Decision
- decision_id
- action
- instrument
- direction
- size
- entry/exit parameters
- confidence
- rationale
- invalidation conditions
- model/agent versions
- context version
- timestamp

### RiskEvaluation
- allowed / rejected / conditional
- exposure
- leverage
- loss limits
- concentration
- liquidity
- policy violations
- required approval
- risk version

### Order
- order_id
- decision_id
- broker
- instrument
- order type
- quantity
- price parameters
- lifecycle state
- timestamps

### AuditRecord
- event_id
- actor
- tenant
- action
- input hash
- output hash
- model version
- policy version
- timestamp
- correlation id

## 3. AI contract
AI modules MUST return machine-readable structured output. Free-form text is presentation metadata, not an execution contract.

## 4. Risk boundary
No AI component may bypass the risk policy layer. A rejected risk evaluation cannot become an executable order through prompt manipulation.

## 5. Execution boundary
Agents cannot possess unrestricted broker credentials. Broker access is mediated through an adapter and policy-controlled execution interface.

## 6. State machine
`PROPOSED → VALIDATED → RISK_CHECKED → APPROVAL_PENDING/APPROVED → SUBMITTED → PARTIALLY_FILLED/FILLED/REJECTED → RECONCILED → CLOSED`

## 7. Failure semantics
- stale data → reject/hold
- malformed decision → reject
- missing required context → request recomputation
- model timeout → fallback/retry policy
- repeated model failure → circuit breaker
- broker inconsistency → reconcile before new execution
- risk violation → reject
- kill switch → halt execution

## 8. Storage
Separate transactional, time-series, object/artifact, cache and semantic/vector workloads. The exact technologies remain implementation choices.

## 9. Observability
Every request receives a correlation ID. Every decision and order must be traceable across logs, metrics, traces and audit records.
