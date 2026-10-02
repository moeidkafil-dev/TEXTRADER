# TEXTRADER X — Release Validation Log

This is a running, dated log. Each section is a point-in-time record from
that release; older sections are kept for history and are **not** updated
retroactively — read the most recent (bottom) section for current numbers.

## 3.0.0 — 2026-09-26

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


## 3.0.0 additional checks

- Full suite after redesign: **81 passed**.
- Dynamic position sizing smoke test: **PASS**; sample paper cycle produced a portfolio-aware quantity instead of fixed size 1.0.
- Research command: **PASS**; when no search provider is configured it explicitly reports `searched=false` and returns a source registry rather than fabricating results.
- Real Binance network call from the builder: **BLOCKED by builder DNS**; the adapter returned a clean error. This does not verify exchange reachability from the user's machine.

## 4.0.2 — 2026-09-27 (kill-switch state synchronization fix)

Measured in a clean venv (`python -m venv` + `pip install -e ".[dev]"`), not
the host's system Python, so results are TEXTRADER's own dependency graph
only.

| Check | Result |
|---|---:|
| Pytest suite | **90 passed** |
| Coverage (`pytest --cov=trader`) | **71%** (now actually measured — `pytest-cov` was missing from the audit's environment, not from the project) |
| `pip check` (clean venv) | **No broken requirements found** |
| 1,000 sequential cycles, single process | **0 errors**, ~125 cycles/sec |
| 64 concurrent cycles, one process / 16 threads | **0 errors** |
| 4 processes × 100 cycles each (multiprocessing) | **0 errors** |
| 12 processes opening the same fresh DB file simultaneously | **0 errors** (previously: `sqlite3.OperationalError: database is locked`) |
| 100 concurrent `/api/health` requests | **100/100 OK** |
| Kill-switch activate in process A, resume in process B (separate OS processes, same DB file) | **PASS** |
| Kill-switch activate/resume across two Orchestrator instances in one process, older instance resumes after a newer one is built against the same DB path | **PASS** (previously: `sqlite3.ProgrammingError: Cannot operate on a closed database`) |

### Two P1 defects fixed

**1. Kill-switch resume crashed with a closed-database error.**
`Orchestrator.__init__` unconditionally called `reset_default_db()`, which
force-closed the process-wide shared SQLite connection every time *any*
Orchestrator was constructed — including a second one built against the
*same* database path while an earlier instance was still alive and in use
(e.g. `ControlPlane._build()` in `trader/web/server.py` rebuilds the
Orchestrator on every `/api/analyze` call; `resume_from_halted()` calling
`self.db.execute(...)` on the older, now-closed handle raised
`sqlite3.ProgrammingError: Cannot operate on a closed database`).
Fixed in `trader/storage/connection.py` / `trader/engine/orchestrator.py`:
the shared connection is now only closed when the requested database path
actually changes; constructing another Orchestrator against the same path
reuses the same live connection instead of yanking it out from under
whoever already holds it.

**2. Concurrent process startup could fail with "database is locked".**
`DB.__init__` set `PRAGMA busy_timeout` *after* `PRAGMA journal_mode = WAL`,
so the WAL-mode switch itself — which briefly needs an exclusive lock — had
no busy-wait behavior yet and raised immediately when several OS processes
raced to initialize the same new database file. Fixed in
`trader/storage/connection.py`: `busy_timeout` is now set first (so the WAL
switch itself waits-and-retries on contention), and connection open/PRAGMA
setup additionally retries with jittered backoff on `OperationalError:
database is locked` as a second line of defense. Verified with 12 OS
processes opening the same brand-new DB file at once.

### One correctness cleanup (non-blocking)
`DB._lock` was a *class* attribute, so every `DB` instance in a process —
even ones pointing at unrelated database files — serialized through one
shared lock. Moved to a per-instance lock in `__init__`.
