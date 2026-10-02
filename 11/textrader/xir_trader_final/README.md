# XIR / TEXTRADER — Engineering Reference Release

A Python reference implementation preserving the XIR multi-agent design:
Data Reader → Context Maker → Agent 1 → adversarial Agent 2 → Agent 3 →
deterministic Risk Engine → Execution Guard → Broker, with persistent memory,
audit, and human override.

## What this is — and isn't

This is a **reference and paper-simulation implementation**, not a production
trading system. Passing software tests does not demonstrate predictive accuracy
or profitability. There is no reviewed live broker or authenticated external
human-control channel in this release:

- `SUPER_PROMPT.md §3` (absolute prohibitions): no live execution without an
  explicit flag *and* a paper-trading track record.
- `OPEN_ISSUES.md P-07`: "Paper trading اجباری قبل از live" (mandatory paper
  trading before live).

`--mode live` refuses to run. All included data and broker adapters are mocks;
the bundled rule-based LLM provider is a deterministic test stand-in, not an
AI model or trading strategy. External adapters must be independently
implemented and reviewed before any deployment.

## What actually works right now

- Full IDLE→READING→…→EXECUTING→IDLE cycle, driven by `xir_trader/runtime.py`
- Deterministic position, loss, drawdown, exposure, leverage, protection,
  correlation, session, liquidity, and emergency kill-switch checks
- 2-minute veto window (configurable), with `on_silence=execute|wait` (P-02)
- RE-EVALUATE loop with a configurable cap (`max_reevaluate_cycles`, P-01)
- Idempotent cycle and order submission, persisted before a broker call;
  unknown broker outcomes remain reserved and cannot silently retry
- RiskEngine-only HMAC authorization binds the complete passing rule result to
  the exact order; caller-constructed or modified approvals fail at the Guard
- The Guard also checks persisted HALTED state and the recorded veto response
- SQLite persistence matching the table list in `16_DATABASE_AND_API`
- Append-only audit log (I4) and structured observability events
- Memory Manager's 12-step maintenance cycle (dedup / junk removal), all 28
  memory types preserved verbatim (nothing merged or dropped)
- Secrets (broker API keys) are read only from environment variables and are
  redacted before anything is written to logs, memory, or the audit trail
- 65 unit, integration, backtest, and adversarial tests (run results in
  `FINAL_RELEASE_REPORT.md`)

## Quick start

```bash
pip install -r requirements.txt
python -m xir_trader.cli --instrument EURUSD --cycles 5 --veto-response OK
```

`--veto-response OK` is a test/development input that skips the configured veto
window. The included `ConsoleChannel` is a notification stub; it does not
authenticate operator messages. The safe default for silence is `wait`.

Run the tests:
```bash
pytest -q
```
`python -m compileall -q xir_trader tests` runs the syntax/type-independent
compile check. No static type checker is configured in this reference release.

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
  config/risk.yaml   illustrative RiskConfig values (review before use)
  cli.py             entry point; --mode live is refused by design
  runtime.py         orchestrator wiring services to the state machine
tests/               pytest suite (state machine, risk engine, invariants, memory, e2e)
docs/                architecture, protocols, risk, audit, testing, security, deployment
examples/            explicitly synthetic historical bars for CLI demonstration
```

## Limits and safety

- `paper` uses only mock market data and `MockBroker`; reported fills are
  simulations. `backtest` is an execution simulator and makes no performance
  claim. No supplied real historical market dataset is included.
- Critical feeds require explicit, finite timestamps and valid OHLCV; stale,
  malformed, future-dated, or instrument-mismatched data cannot approve trades.
- `RE-EVALUATE` re-runs the entire upstream pipeline from Data Reader and is
  capped by `RiskConfig.max_reevaluate_cycles`.
- Agent 2 must cover exactly nine failure categories. Invalid output is
  converted to blocking findings; deterministic policy overrides Agent 3.
- Read `docs/SECURITY_AND_DEPLOYMENT.md` and `FINAL_RELEASE_REPORT.md` before
  running anything beyond local simulation.

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
6. **Independent review**: risk parameters, the security model, real feed/broker
   integrations, market-specific behavior, and local regulatory obligations
   need qualified review before considering any live-capital integration.

## Mapping back to your documents

See `TRACEABILITY_NOTES.md` for how each module maps to `REQ-*` IDs, and
`DEBUG_AND_TEST_LOG.md` for exactly what was tested, what broke, and what was
fixed during this build.
