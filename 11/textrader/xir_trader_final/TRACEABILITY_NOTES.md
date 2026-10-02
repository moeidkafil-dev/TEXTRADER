# Traceability — code ↔ spec

Maps this codebase back to `14_COMPLETE_PRD/COMPLETE_PRD.md` requirement IDs and
the other TRADER_XIR chapters. Not exhaustive line-by-line (the PRD defines ~60+
REQ-* IDs); this covers every module and the load-bearing requirements.

| Code | Spec requirement(s) | Notes |
|---|---|---|
| `core/state_machine.py` | `04_FORMAL_SYSTEM_SPECIFICATION/STATE_MACHINE.md`, `SYSTEM_MODEL.md` (I1-I5) | Transitions copied verbatim; invariants enforced at orchestration layer (`runtime.py`), documented per-state in that file's docstring |
| `core/schemas.py` | `04_FORMAL_SYSTEM_SPECIFICATION/AGENT_AND_TOOL_PROTOCOL.md` | Field names/enums unchanged from the JSON schemas; `.validate()` raises `SchemaError` → caller converts to WAIT (I5) |
| `core/memory_types.py` | `05_AGENT_AND_MEMORY_MODEL/AGENT_AND_MEMORY_MODEL.md` | All 28 types, original order, `assert len == 28` as a structural guard against accidental merging |
| `services/data_reader.py` | REQ-DR-01, REQ-DR-02 | Missing sources are retained; explicit timestamps, freshness, finite OHLCV, quote shape, and instrument identity are checked before Context Maker sees data |
| `services/context_service.py` | REQ-DR-03, REQ-DR-04 | 5 sections, each flagged empty rather than omitted; single-delivery contract (OI-01 interpretation) |
| `services/agents.py` | REQ-AG-01 .. REQ-AG-06 | Each agent logs all 10 internal-template steps (`_AgentPipelineTrace`) so REQ-AG-01's "full trace in log" acceptance criterion is literally checkable |
| `services/llm_provider.py` | OI-08 (provider-agnostic) | `RuleBasedProvider` is a deterministic stand-in, not a strategy; swap in a real model via the `LLMProvider` interface |
| `services/risk_engine.py` | `07_RISK_ENGINE/RISK_ENGINE.md`, P-03, P-05 | Deterministic checks for configured risk limits; emergency stop first (short-circuit) and last; HMAC authorization is bound to order and rule results |
| `services/execution.py` | `08_EXECUTION_MODEL/EXECUTION_MODEL.md`, REQ-EX-*, P-04 | Guard requires verifiable RiskEngine authorization, persisted EXECUTING state, non-held human state, recorded veto approval, and an unused idempotency key |
| `services/messaging.py` | `08_EXECUTION_MODEL/EXECUTION_MODEL.md` (veto window), P-02, SECURITY_MODEL "جعل پیام کاربر" | 2-minute default window; `UserWhitelist.authenticate()` is the hook for a real channel's sender-authentication |
| `services/memory_manager.py` | `05_AGENT_AND_MEMORY_MODEL/AGENT_AND_MEMORY_MODEL.md` (12-step Memory Manager) | All 12 steps logged per cycle; naive duplicate-content junk detector as a starting point for "find junks" |
| `services/db_manager.py` | `16_DATABASE_AND_API/DATABASE_AND_API.md` | Same table names/keys, SQLite instead of Postgres (ENGINEERING_SPEC marks the DB engine `[PROPOSED]`/replaceable); `audit_log` has no UPDATE/DELETE path anywhere in this module (I4) |
| `services/observability.py` | SUPER_PROMPT §5 ("Observability در همه") | Every service gets its own `Observability(component=...)`; every event also lands in `observability_events` |
| `adapters/data/*`, `adapters/broker/*` | `15_ENGINEERING_SPEC/ENGINEERING_SPEC.md` (Adapter پیشنهادی), P-06 | One adapter class per source/venue; swapping mocks for real ones is additive, no orchestrator changes needed |
| `core/config.py` | SECURITY_MODEL.md | `redact_secrets()` used on every write to logs/memory/audit; broker creds only from env vars; agents never get a mutable `RiskConfig` handle |
| `runtime.py` | `SYSTEM_MODEL.md` invariants I1–I5, OI-03 (Risk Engine invoked around Decision Engine/Validator) | See the module docstring for exactly which line enforces which invariant |
| `cli.py` | SUPER_PROMPT §3 ("اجرای live بدون پرچم صریح... ممنوع"), P-07 | `--mode live` refuses outright in this reference build; a real deployment must supply its own live `BrokerAdapter` in code, not via a flag alone |

## Deliberately deferred (needs a real deployment, not a reference build)

- `04_FORMAL_SYSTEM_SPECIFICATION` service boundaries as actual separate
  processes/microservices (`ENGINEERING_SPEC.md`'s suggested stack) — this
  build is single-process for testability; the module boundaries already
  match the suggested service list 1:1 if you do split it later.
- OpenTelemetry / structured log shipping — `observability.py` emits JSON
  lines + SQLite rows; wire a real OTel exporter when you have somewhere to
  send it.
- Redis/NATS queue between services — not needed until this is actually
  split into microservices.
- pgvector / RAG memory backing store — `memory_type="rag_memory"` items are
  stored like any other memory item; a real RAG pipeline needs embeddings +
  a vector index, which is out of scope for a reference build with no
  configured embedding provider.
- `12_PATENT_IRAN/*`, `13_PRIOR_ART/*` — legal/IP matters, not code.
