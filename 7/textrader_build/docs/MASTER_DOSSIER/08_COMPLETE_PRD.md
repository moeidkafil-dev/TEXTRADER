# COMPLETE PRD — TRADER

## Product vision
ساخت یک پلتفرم معاملاتی AI-assisted که بتواند داده، context، تحلیل چندعاملی، تصمیم، validation، risk، execution، monitoring و replay را در یک زنجیره قابل ردیابی مدیریت کند.

## Product goals
### P0
- ingest market data;
- normalize/validate data;
- construct context;
- run agent analysis;
- produce structured decision;
- validate decision;
- enforce risk;
- simulate execution;
- record audit lineage.

### P1
- broker adapters;
- paper trading;
- live guarded execution;
- replay;
- dashboards;
- model/prompt registry;
- cost control.

### P2
- multi-tenancy;
- billing;
- advanced research;
- distributed execution;
- institutional controls.

## Non-goals
- guaranteed profit;
- autonomous bypass of risk controls;
- opaque execution;
- unrestricted agent access to secrets.

## Functional requirements
FR-001 Data ingestion MUST accept timestamped market data.
FR-002 Data quality MUST reject or flag stale/malformed inputs.
FR-003 Context builder MUST create versioned context.
FR-004 Agents MUST consume explicit context.
FR-005 Agent output MUST conform to schema.
FR-006 Validator MUST reject malformed decisions.
FR-007 Risk engine MUST evaluate exposure and configured policies.
FR-008 Execution guard MUST enforce risk result.
FR-009 Broker access MUST use adapters.
FR-010 Every order MUST have a decision lineage.
FR-011 The system MUST support simulation before live.
FR-012 Replay MUST reconstruct the decision path from stored artifacts.
FR-013 Kill switch MUST block execution.
FR-014 Secrets MUST be isolated.
FR-015 Every critical event MUST be auditable.

## Non-functional requirements
- reproducibility;
- idempotency for retried execution commands;
- bounded latency per execution mode;
- encryption in transit and at rest;
- RBAC;
- structured logging;
- health checks;
- horizontal scalability at service boundaries;
- deterministic risk behavior.

## Acceptance criteria
A release cannot be promoted to live unless:
1. all critical unit/integration tests pass;
2. risk bypass tests pass;
3. replay succeeds;
4. stale-data tests pass;
5. broker failure/reconciliation tests pass;
6. kill-switch tests pass;
7. secret-isolation tests pass;
8. audit lineage is complete.

## Suggested repository
```text
trader/
  apps/
    api/
    worker/
    dashboard/
  core/
    domain/
    decision/
    risk/
    execution/
    context/
    memory/
  agents/
    research/
    market/
    critic/
    risk_review/
  adapters/
    brokers/
    data/
    llm/
  simulation/
    backtest/
    paper/
    replay/
    scenarios/
  storage/
    sql/
    timeseries/
    object/
    vector/
    cache/
  security/
  observability/
  tests/
  docs/
```

## Definition of Done
A component is done only when code, schema, tests, logging, failure behavior and documentation exist.
