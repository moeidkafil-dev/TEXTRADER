# TRADER / XIR — Final Release 1.1.0

A paper-first Python runtime for the TRADER/XIR architecture: three-agent
decision flow, deterministic 11-rule risk engine, execution guard, kill
switch, veto window, 28-type memory catalog, SQLite persistence, audit trail,
paper mode, and historical replay.

## Release status

**Verified release:** 1.1.0  
**Primary runtime:** `trader/`  
**Python:** 3.10+ (validated in this environment on Python 3.13)

This release is the cleaned production package derived from the
**stress-verified 2026-09-25 build**. The older duplicate `xir_trader/`
reference implementation has intentionally been removed from the shipped
runtime so there is one authoritative code path.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

pytest -q
python -m trader.scripts.run_demo
python -m trader.scripts.run_paper --cycles 20
python -m trader.scripts.run_backtest --bars 200
```

Or use the installed commands:

```bash
trader-demo
trader-paper --cycles 50
trader-backtest --bars 200
```

## Verification performed for this release

- Full automated suite: **75 tests passed** after adding adversarial/property-style regressions.
- Python bytecode compilation: passed.
- 100-cycle paper run: completed with **0 runtime errors**.
- 1,000-bar backtest replay: completed with **0 runtime errors**.
- Kill-switch activation/configuration, veto rejection/silence, idempotency,
  risk boundaries, RE-EVALUATE cap, and state-machine invariants were exercised.
- Static AST safety scan found no `eval`, `exec`, `os.system`, `os.popen`, or
  embedded private-key/API-key patterns in the production runtime.
- Runtime source footprint (`trader/*.py`): about **173 KB / 4.3k lines** in the
  stress-tested core before packaging. It is intentionally compact rather than
  artificially padded.

## Important boundary

The shipped broker is a mock broker. The included LLM is a deterministic mock
provider. Email/Telegram senders are non-networking stubs. Therefore the
validation demonstrates software/runtime behavior, not profitability or
production exchange connectivity.

Live trading is fail-closed and requires the explicit runtime safeguards in
the project specification, a supported live broker adapter, credential
isolation, independent operational/security review, and a meaningful
paper-trading record.

## Architecture

`trader/` is the only authoritative implementation:

- `core/` — schemas, configuration, state machine, invariants
- `services/` — agents, context, decision validation, risk, guard, messaging,
  observability, kill switch, final tools
- `engine/` — orchestration
- `memory/` — 28 logical memory types and maintenance pipeline
- `storage/` — SQLite persistence
- `adapters/` — pluggable LLM and broker interfaces
- `scripts/` — demo, paper, and backtest entry points
- `tests/` — unit, integration, regression, adversarial tests
- `benchmarks/` — deterministic microbenchmark

See `RELEASE_VALIDATION.md` for the detailed verification record and
`TRADER_XIR/` for the complete engineering/specification dossier.
