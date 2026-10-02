# TEXTRADER X 3.1.1

Autonomous, fail-closed trading runtime built around specialist agents, deterministic risk, portfolio-aware sizing, auditable research, paper execution and optional exchange adapters.

## What changed from 2.0.1
- Portfolio-aware position sizing: risk budget + stop distance + exposure cap + fee/slippage allowance.
- No live order can bypass deterministic risk checks.
- Closed-candle Binance market data path to avoid partial-candle look-ahead.
- Supervisory thesis layer (`trader.services.super_agent`).
- Auditable research registry and configurable search provider.
- Performance metrics for paper/backtest reporting.
- Live mode remains explicitly fail-closed.

## Safety contract
No software can guarantee profit. TEXTRADER X deliberately reports measured performance rather than claiming certainty. Live trading requires explicit acknowledgement and should only follow historical, out-of-sample, paper and testnet validation.

## Quick start
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev,live]'
textrader --version
textrader doctor
pytest -q
textrader analyze BTC/USDT --source mock --mode paper
textrader research "position sizing volatility trading"
```

## Real market data
```bash
TEXTRADER_MARKET_DATA=binance textrader analyze BTC/USDT --source binance --mode paper
textrader paper BTC/USDT --source binance --cycles 100 --interval 60
```

## Research
Set `TEXTRADER_SEARCH_URL` to a trusted search provider that accepts `q=`. Without it, the system returns its explicit source registry and never pretends that a search occurred.

## Live gate
```bash
export TRADER_LIVE_ACK=I_UNDERSTAND_LIVE_TRADING
```
Do this only after validating the system. Credentials are never embedded in source code.
