# Security and deployment

## Included security controls

- `--mode live` always refuses; no reviewed live broker implementation exists.
- Secrets are read by configured environment-variable names and redacted from
  logs, memory, decisions, and audit payloads. `.env.example` contains only
  obvious dummy strings. The project does not load `.env` automatically.
- Agent output and external data are treated as untrusted; schemas, strict
  market-data quality/freshness checks, current evidence policy, deterministic
  risk, and Guard authorization precede broker invocation.
- Unknown/invalid data, agent output, state, broker acknowledgement, and broker
  outcome fail closed. Prompt-injection content is data only; there are no
  agent-exposed execution tools.
- SQLite statements use parameter binding. The project does not execute
  shell commands from model or provider input.

## Not implemented / not reviewed

There is no real market-data provider, broker, notification transport,
authenticated STOP/REJECT sender, external secret manager, network API,
dependency vulnerability scan, cryptographically tamper-evident audit, or
multi-process state lock. The included mock channel cannot authenticate real
humans. Broker timeout recovery and actual fills require venue-specific
idempotency and reconciliation. These boundaries need independent review and
implementation before any real-capital use.

## Local run and deployment status

For local tests and synthetic paper simulation, install dependencies and use
the commands in README. This release is safe for local mock-only testing. Do
not connect real credentials or real capital: the system is not approved for
live execution, and CLI live mode is disabled by design. Risk defaults are
examples and are not suitable as generic investment controls.
