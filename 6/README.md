# TRADER / XIR — Product Release 2.0.1

TRADER/XIR is now packaged as a product surface, not only as a core runtime.
The 2.0 release keeps the tested safety core and adds a real public-market-data
adapter, professional CLI, local web control center, and an optional CCXT live
execution adapter.

## What ships

- Deterministic XIR core: A1/A2/A3, decision validation, 11-rule risk engine,
  veto window, execution guard, kill switch, state machine, memory and audit.
- **Real public market data:** Binance REST ticker, order book and OHLCV.
- **CLI:** `xir doctor`, `xir market`, `xir analyze`, `xir paper`, `xir backtest`,
  `xir kill-switch`, `xir web`.
- **Web UI:** local dashboard with live market chart, XIR decision panel,
  risk-rule status, raw audit/cycle output, and kill-switch controls.
- **Paper execution:** safe default; no real funds touched.
- **Optional live execution:** CCXT adapter, disabled unless explicitly
  configured with credentials and live acknowledgement.

## Kali Linux quick start

```bash
sudo apt update
sudo apt install -y python3 python3-venv unzip
unzip TRADER_XIR_FINAL_RELEASE_2_0.zip
cd TRADER_XIR_FINAL_RELEASE_2_0
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### Validate

```bash
xir doctor
pytest -q
```

### Read real market data

```bash
xir market BTC/USDT
```

### Run one XIR cycle against real public market data

```bash
xir analyze BTC/USDT --source binance
```

### Paper trading with real market data

```bash
xir paper BTC/USDT --source binance --cycles 100
```

The execution broker remains mock/paper unless the live configuration is
explicitly changed.

### Start Web UI

```bash
xir web --host 127.0.0.1 --port 8787 --symbol BTC/USDT
```

Open `http://127.0.0.1:8787` in a browser.

## Live execution

Live trading is deliberately not enabled by installing the package. For an
operator-approved live deployment, install the optional adapter:

```bash
pip install -e ".[live]"
export XIR_API_KEY='...'
export XIR_API_SECRET='...'
export XIR_EXCHANGE='binance'
export TRADER_LIVE_ACK='I_UNDERSTAND_LIVE_TRADING'
```

Then configure `broker: ccxt` and `mode: live`. Use a dedicated account/key,
minimum permissions, and testnet/sandbox where the exchange supports it.
Never commit credentials.

## Product boundary

Real market-data connectivity is included. Live order execution is an optional
adapter and requires explicit operator configuration. No software test can
prove that a trading strategy is profitable; profitability requires independent
market-data validation, realistic fees/slippage, out-of-sample evaluation and
long-running paper trading.
