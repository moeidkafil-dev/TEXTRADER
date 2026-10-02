# TEXTRADER X 3.0.0 — Product Release Notes

## Product surface added

This release promotes the tested TEXTRADER core into an operator-facing product.

### CLI

`textrader` now provides:

- `textrader doctor`
- `textrader market SYMBOL`
- `textrader analyze SYMBOL --source binance`
- `textrader paper SYMBOL --source binance --cycles N`
- `textrader backtest --bars N`
- `textrader kill-switch on|off`
- `textrader web --host HOST --port PORT --symbol SYMBOL`
- `textrader --version`

### Real market data

`BinancePublicSource` reads public ticker, order book and OHLCV data and maps
it into the existing TEXTRADER `DataBundle` contract. No API key is required for
these public reads.

### Web control center

The built-in local dashboard exposes:

- real-time-ish market refresh
- OHLC close chart
- price / 24h change / bid / ask
- TEXTRADER cycle execution
- decision and risk-rule display
- raw cycle output
- health state
- kill switch and explicit resume

The server uses Python's standard library so the dashboard does not require a
Node/npm build pipeline.

### Live execution boundary

`CCXTBroker` is included as an optional adapter. It is not enabled by default.
Live mode requires:

- `TRADER_LIVE_ACK=I_UNDERSTAND_LIVE_TRADING`
- `TEXTRADER_API_KEY`
- `TEXTRADER_API_SECRET`
- `broker: ccxt`
- `mode: live`
- optional `TEXTRADER_TESTNET=1` where supported

Credentials are read only from environment variables and are not logged by
this adapter.

## Verification

- Full project tests: **79 passed**.
- CLI parser surface tests: passed.
- Web server health endpoint: passed.
- Web UI root/static serving: passed.
- Python compile/test import path: passed.
- Real-market-data code path: implemented and error-handled.

The execution environment used for building this artifact had DNS/network
access disabled. Therefore the Binance endpoint itself could not be contacted
from the builder; a real network call returned a DNS failure. This is an
infrastructure limitation of the build environment, not evidence that the
adapter endpoint is unavailable. The CLI now reports such failures cleanly.

## Safety posture

Paper/mock execution remains the default. The existing fail-closed risk engine,
execution guard and final kill-switch check remain in the path. Adding the
product surface does not bypass the safety core.

## X architecture

3.0.0 adds portfolio-aware position sizing, a supervisory trade-thesis layer, auditable knowledge-source registry, optional research search, and performance metrics. The LLM remains advisory: deterministic risk and execution guards retain final authority.

## Profitability claim

This release makes no guarantee of profitability. The validation artifact intentionally separates software correctness from trading performance and requires out-of-sample, paper and testnet validation before live use.
