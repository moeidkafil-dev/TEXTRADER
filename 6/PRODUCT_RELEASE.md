# TRADER/XIR 2.0.1 — Product Release Notes

## Product surface added

This release promotes the tested XIR core into an operator-facing product.

### CLI

`xir` now provides:

- `xir doctor`
- `xir market SYMBOL`
- `xir analyze SYMBOL --source binance`
- `xir paper SYMBOL --source binance --cycles N`
- `xir backtest --bars N`
- `xir kill-switch on|off`
- `xir web --host HOST --port PORT --symbol SYMBOL`
- `xir --version`

### Real market data

`BinancePublicSource` reads public ticker, order book and OHLCV data and maps
it into the existing XIR `DataBundle` contract. No API key is required for
these public reads.

### Web control center

The built-in local dashboard exposes:

- real-time-ish market refresh
- OHLC close chart
- price / 24h change / bid / ask
- XIR cycle execution
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
- `XIR_API_KEY`
- `XIR_API_SECRET`
- `broker: ccxt`
- `mode: live`
- optional `XIR_TESTNET=1` where supported

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
