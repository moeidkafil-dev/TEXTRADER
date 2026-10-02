# Memory and audit model

Memory remains a distinct subsystem with the project's 28 `MemoryType` values.
Decision traces and Agent 2 reports are persisted as history; memory does not
replace current market facts, portfolio state, risk configuration, or broker
execution records. Context labels memory separately and provides current
market inputs from this cycle's Reader bundles. Current feed facts carry source,
timestamp, quality, and content hash.

SQLite tables separate `data_bundles`, `contexts`, `decisions`, `failure_paths`,
`orders`, `risk_results`, `veto_events`, `memory_items`, `audit_log`,
`observability_events`, and persistent system state. `audit_log` is append-only
through the DB manager API; it is not cryptographically tamper-evident against
someone with direct database-file access.

Each cycle has a UUID. The cycle's data bundles, context hash, three agent
outputs, failure paths, risk rule outcomes, veto, order attempt, execution
result, and state transitions are persisted or emitted with cycle/order IDs.
Queries need not re-run a provider to explain recorded decisions. Trace IDs
are observability correlation identifiers; cycle IDs are durable decision IDs.

Credentials are redacted from JSON log/database writes. Memory manager
maintenance is simple deduplication and is not an embeddings/vector retrieval
system. There is no RAG, independent risk-state store, distributed memory, or
multi-host audit service.
