# XIR / TRADER — Reference Runtime (paper-mode)

A working Python implementation of the `TRADER` / `XIR` architecture described in
the `TRADER_XIR` documentation package (189-node / 217-edge design graph):
a 3-agent trading-decision pipeline, an 11-rule deterministic Risk Engine with
an absolute-priority Kill Switch, a 28-type memory catalog, a veto window, and
an Execution Guard that is the only path to a broker.

## What this is — and isn't

This is a **reference implementation**, not a certified production trading
system. It faithfully implements every requirement in `14_COMPLETE_PRD` against
the state machine in `04_FORMAL_SYSTEM_SPECIFICATION`, and it is fully tested —
but "release-ready for live trading with real money" is not something any
codebase can honestly claim after one build pass, and your own design package
says so explicitly:

- `SUPER_PROMPT.md §3` (absolute prohibitions): no live execution without an
  explicit flag *and* a paper-trading track record.
- `OPEN_ISSUES.md P-07`: "Paper trading اجباری قبل از live" (mandatory paper
  trading before live).

This build honors that by construction: **there is no live broker adapter
included**, `--mode live` refuses to run, and `Runtime` raises if you try to
mix `mode="live"` with anything other than a real, explicitly-supplied
`BrokerAdapter` with `is_live=True`. Wiring up a real venue, running it in
paper mode for a meaningful track record, and having someone qualified
review the risk parameters and security posture are on you before any real
money touches this.

## What actually works right now

- Full IDLE→READING→…→EXECUTING→IDLE cycle, driven by `xir_trader/runtime.py`
- All 11 Risk Engine rules, in the graph's order, deterministic, with the Kill
  Switch checked first (short-circuits everything) and again last
- 2-minute veto window (configurable), with `on_silence=execute|wait` (P-02)
- RE-EVALUATE loop with a configurable cap (`max_reevaluate_cycles`, P-01)
- Idempotent order submission (P-04) — a retried order with the same
  `(cycle_id, side, instrument)` is refused as a duplicate, never double-filled
- SQLite persistence matching the table list in `16_DATABASE_AND_API`
- Append-only audit log (I4) and structured observability events
- Memory Manager's 12-step maintenance cycle (dedup / junk removal), all 28
  memory types preserved verbatim (nothing merged or dropped)
- Secrets (broker API keys) are read only from environment variables and are
  redacted before anything is written to logs, memory, or the audit trail
- 25 tests covering the state machine, the risk engine, the I1/I5 invariants,
  the memory manager, and full end-to-end paper cycles — all passing

## Quick start

```bash
pip install -r requirements.txt
python -m xir_trader.cli --instrument EURUSD --cycles 5 --veto-response OK
```

`--veto-response OK` is a testing/dev shortcut that skips the interactive
2-minute wait — omit it for a real veto window (you'll need a real
`NotificationChannel`, see below).

Run the tests:
```bash
pytest -q
```
(This sandbox couldn't reach PyPI to install `pytest`, so everything above was
verified with an equivalent hand-rolled runner instead — see
`DEBUG_AND_TEST_LOG.md`. The test files themselves are plain pytest and will
run unmodified once you `pip install pytest`.)

## Project layout

```
xir_trader/
  core/              state_machine.py, schemas.py, memory_types.py (28, verbatim), config.py
  services/          data_reader, context_service, agents (1/2/3), risk_engine,
                      execution (Guard + Final Tools), messaging (veto), memory_manager,
                      db_manager (SQLite), observability, llm_provider (pluggable, OI-08)
  adapters/
    data/            DataSourceAdapter interface + mock price/orderbook/news/portfolio
    broker/          BrokerAdapter interface + MockBroker (paper fills only)
  config/risk.yaml   owner-tunable RiskConfig values (the 11 rules themselves are fixed)
  cli.py             entry point; --mode live is refused by design
  runtime.py         orchestrator wiring services to the state machine
tests/               pytest suite (state machine, risk engine, invariants, memory, e2e)
```

## Extending it toward a real deployment

1. **Real data**: implement `DataSourceAdapter.fetch()` for each venue/news/
   economic-data source you need (`adapters/data/`), replacing the mocks one
   at a time (P-06: one adapter per market, staged rollout).
2. **Real broker**: implement `BrokerAdapter` (`adapters/broker/`), set
   `is_live = True`, read credentials only via `AppConfig.broker_credentials()`
   (env vars — never commit them, never let them reach a log).
3. **Real LLM**: implement `LLMProvider.complete()` against whatever model you
   want per agent (`services/llm_provider.py`); the `RuleBasedProvider` here
   is a transparent stand-in, not a trading strategy.
4. **Real notification channels**: implement `NotificationChannel` for
   Telegram/Email (`services/messaging.py`) with the sender authenticated
   against `UserWhitelist` before any veto command is trusted.
5. **Paper track record**: run in `--mode paper` against real (or realistic)
   data for a meaningful period before anyone considers `--mode live`.
6. **Independent review**: the risk parameters in `config/risk.yaml`, the
   security model, and — given `12_PATENT_IRAN/PATENTABILITY_RISK.md` in your
   dossier — any IP/patentability questions all need review by people
   qualified in those areas; nothing here substitutes for that.

## Mapping back to your documents

See `TRACEABILITY_NOTES.md` for how each module maps to `REQ-*` IDs, and
`DEBUG_AND_TEST_LOG.md` for exactly what was tested, what broke, and what was
fixed during this build.
