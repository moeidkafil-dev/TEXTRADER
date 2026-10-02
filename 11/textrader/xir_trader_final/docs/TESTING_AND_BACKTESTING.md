# Testing and backtesting

Run tests using `python -m pytest -q`; compile checks use
`python -m compileall -q xir_trader tests`. Development dependencies are listed
in `requirements-dev.txt`. Ruff and mypy are optional developer tools; see the
release report for which tools ran in the build environment.

Tests cover contracts/configuration, state transitions, deterministic risk,
memory, audit trail, full paper cycles, idempotency, concurrency on one
process, restart/corruption behavior, and adversarial provider/broker inputs.
Test success establishes software behavior only, not trading value.

## Backtest simulator

`services/backtest.py` runs a strategy callback with only historical bars
strictly before the current execution bar. Execution is assumed at the current
bar open. Configurable fee, slippage, and half-spread costs are deducted.
Output includes PnL, equity curve, win/loss counts, win rate, expectancy,
unannualized Sharpe-like value, maximum drawdown, exposure, turnover, and cost.
The metric is explicitly a simulation, not a profitability claim.

`walk_forward_splits` provides ordered development, validation, and unseen
test slices; it does not train a model or tune a strategy. No real historical
dataset is shipped. `examples/synthetic_bars.csv` is generated demonstration
data and must be labeled with `--synthetic-data`.
