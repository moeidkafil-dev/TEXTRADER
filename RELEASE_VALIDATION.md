# textrader — Release 2.0.1 Validation

Date: 2026-09-25

## Automated test suite

| Check | Result |
|---|---:|
| Pytest suite | **79 passed** |
| Adversarial/property-style tests | **4 passed** |
| Python `compileall` | **PASS** |
| Coverage (`pytest --cov=trader`) | **79%** |
| Paper run, 100 cycles | **100/100 completed, 0 errors** |
| Backtest replay, 1,000 bars | **1,000/1,000 completed, 0 errors** |

The suite includes state-machine tests, all 11 deterministic risk rules,
memory, agents, data reader, persistence, execution, veto paths, kill-switch
paths, RE-EVALUATE regression, and the final broker-boundary kill-switch
regression.

## Stress/benchmark measurements

Measured in the supplied execution environment:

- Risk engine: ~103,540 checks/sec, ~9.66 µs/check over 100,000 checks.
- Mock broker benchmark from the preceding stress build: ~4,754 submissions/sec, ~210.3 µs/submission over 10,000 unique submissions.
- 100-cycle paper session: **100/100 completed, 0 errors** in the final validation run.
- 1,000-bar backtest: **1,000/1,000 completed, 0 errors** in the final validation run.

These are environment-specific engineering measurements, not exchange latency
claims.

## Bugs specifically found by final-release validation

### 0. Packaging/CLI regressions fixed
The 2.0.0 package had an invalid `pyproject.toml` entry that placed the `live` dependency list under `project.scripts`; editable installation failed on setuptools validation. This was corrected in 2.0.1. A second regression in `textrader paper` referenced a non-existent `args.mode`; the CLI now uses safe optional argument access. Real-market snapshot processing also excludes the currently forming kline so the decision path uses closed candles.

## Bugs specifically found by adversarial testing

### 1. RE-EVALUATE state corruption
The previous release could transition `REEVAL → READING` and then attempt an
additional `IDLE → READING` transition inside the recursive cycle. The
stress-tested build added an explicit `_start_from_reading` path and a
regression test. Repeated RE-EVALUATE now terminates at the configured cap and
returns to `IDLE`.

### 2. Kill-switch race at final execution boundary
Execution Guard alone was not sufficient if a kill switch activated after
Guard approval but immediately before Final Tools. Final Tools now performs a
second fail-closed kill-switch check immediately before broker submission, with
a regression test proving that the broker receives zero submissions in the
simulated race.

## Static/security checks

A source-level AST scan was run over the production runtime. It found no
`eval`, `exec`, `os.system`, `os.popen`, hard-coded private-key blocks, or
obvious API-key/secret assignments.

`pip check` in the host environment reported an unrelated global
`moviepy`/`Pillow` dependency mismatch; textrader itself does not depend on
moviepy and the project's test suite remained green.

## Trading/backtest validation boundary

The backtest engine is software infrastructure validation, not evidence of
profitability. Sound backtesting requires controls for look-ahead bias,
transaction costs/slippage, market impact, survivorship bias, data snooping,
and regime changes. Those are external research/validation concerns beyond
the deterministic mock data shipped here.

## External testing standards consulted

The validation plan was aligned with current documentation/practice around
property-based testing, static security analysis, linting, microbenchmarking,
and trading-backtest failure modes. See the project conversation's cited
sources for Hypothesis, Bandit, Ruff, pytest-benchmark, and backtesting
methodology.

## 2.0 Product surface validation

- CLI surface: **PASS**
- Web server `/api/health`: **PASS**
- Web dashboard root: **PASS**
- Real market adapter unit/normalization tests: **PASS**
- Real Binance network call from build sandbox: **NOT AVAILABLE** because the
  sandbox has no DNS/network access. The adapter returns a clean actionable
  error instead of a raw stack trace.
