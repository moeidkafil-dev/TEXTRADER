#!/usr/bin/env bash
set -u

ROOT="$(pwd)"
TS="$(date +%Y%m%d_%H%M%S)"
OUT="$ROOT/stress_report_$TS"
LOG="$OUT/full.log"

mkdir -p "$OUT"

exec > >(tee -a "$LOG") 2>&1

echo "============================================================"
echo " TEXTRADER — FULL MULTI-LAYER SYSTEM AUDIT"
echo " Started: $(date -Is)"
echo " Root: $ROOT"
echo " Report: $OUT"
echo "============================================================"

PASS=0
FAIL=0
WARN=0

run() {
    local name="$1"
    shift

    echo
    echo "------------------------------------------------------------"
    echo "[TEST] $name"
    echo "------------------------------------------------------------"

    if "$@" >"$OUT/${name// /_}.out" 2>&1; then
        echo "[PASS] $name"
        PASS=$((PASS+1))
    else
        echo "[FAIL] $name"
        FAIL=$((FAIL+1))
        cat "$OUT/${name// /_}.out"
    fi
}

section() {
    echo
    echo
    echo "============================================================"
    echo " $1"
    echo "============================================================"
}

# ------------------------------------------------------------
# 0. ENVIRONMENT
# ------------------------------------------------------------

section "0 — ENVIRONMENT"

python --version
python -m pip --version
python -m pip check || true

echo
echo "CPU:"
nproc

echo
echo "MEMORY:"
free -h

echo
echo "DISK:"
df -h .

echo
echo "PYTHON PACKAGES:"
python -m pip list | grep -Ei \
'fastapi|uvicorn|httpx|pydantic|pytest|pytest-cov|ccxt|pyyaml' || true

# ------------------------------------------------------------
# 1. PACKAGE / IMPORT / COMPILE
# ------------------------------------------------------------

section "1 — PACKAGE / IMPORT / COMPILE"

run "compileall" \
    python -m compileall -q trader

run "import_core" \
    python - <<'PY'
import trader
import trader.cli
import trader.web.server
print("core imports: OK")
PY

run "cli_help" \
    python -m trader.cli --help

run "cli_doctor" \
    python -m trader.cli doctor

# ------------------------------------------------------------
# 2. UNIT + COVERAGE
# ------------------------------------------------------------

section "2 — TEST SUITE / COVERAGE"

run "pytest_full" \
    python -m pytest -q --tb=short

echo
echo "[COVERAGE]"
python -m pytest \
    --cov=trader \
    --cov-report=term-missing \
    --cov-report="html:$OUT/coverage_html" \
    -q --tb=short \
    > "$OUT/coverage.out" 2>&1 || true

cat "$OUT/coverage.out"

# ------------------------------------------------------------
# 3. CLI FEATURE MATRIX
# ------------------------------------------------------------

section "3 — CLI FEATURE MATRIX"

run "cli_market_mock" \
    python -m trader.cli market BTC/USDT --interval 1m --limit 10

run "cli_analyze_mock" \
    python -m trader.cli analyze BTC/USDT --source mock --mode paper

run "cli_paper" \
    python -m trader.cli paper BTC/USDT --source mock --cycles 10 --interval 0

run "cli_backtest" \
    python -m trader.cli backtest --bars 200

run "cli_research" \
    python -m trader.cli research "BTC market microstructure"

run "cli_llm_list" \
    python -m trader.cli llm list

run "cli_llm_test" \
    python -m trader.cli llm test

run "cli_connector_list" \
    python -m trader.cli connector list

# ------------------------------------------------------------
# 4. DATABASE INTEGRITY
# ------------------------------------------------------------

section "4 — DATABASE / PERSISTENCE"

python - <<'PY' > "$OUT/database_report.txt"
import sqlite3
import os

db = "data/trader.db"

if not os.path.exists(db):
    print("DATABASE NOT FOUND:", db)
    raise SystemExit(1)

con = sqlite3.connect(db)

print("DATABASE:", db)
print("SIZE:", os.path.getsize(db))

print("\nTABLES:")
tables = con.execute("""
SELECT name
FROM sqlite_master
WHERE type='table'
ORDER BY name
""").fetchall()

for (name,) in tables:
    print(" ", name)

print("\nCOUNTS:")
for (name,) in tables:
    try:
        count = con.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0]
        print(f"{name:25} {count}")
    except Exception as e:
        print(name, "ERROR", e)

print("\nINTEGRITY:")
print(con.execute("PRAGMA integrity_check").fetchone()[0])

print("\nFOREIGN KEYS:")
print(con.execute("PRAGMA foreign_key_check").fetchall())

print("\nJOURNAL:")
print(con.execute("PRAGMA journal_mode").fetchone()[0])

con.close()
PY

cat "$OUT/database_report.txt"

# ------------------------------------------------------------
# 5. REAL PIPELINE AUDIT
# ------------------------------------------------------------

section "5 — END-TO-END DECISION PIPELINE"

python - <<'PY' > "$OUT/pipeline_audit.json"
import json
from trader.orchestrator import Orchestrator

o = Orchestrator()

r = o.run_cycle()

if hasattr(r, "to_dict"):
    data = r.to_dict()
else:
    data = r

print(json.dumps(data, indent=2, default=str))
PY

cat "$OUT/pipeline_audit.json"

# ------------------------------------------------------------
# 6. STRESS — SEQUENTIAL
# ------------------------------------------------------------

section "6 — SEQUENTIAL STRESS"

python - <<'PY' > "$OUT/sequential_stress.txt"
import time
from trader.orchestrator import Orchestrator

N = 1000

o = Orchestrator()

errors = 0
completed = 0

t0 = time.perf_counter()

for i in range(N):
    try:
        r = o.run_cycle()

        if getattr(r, "error", None):
            errors += 1

        completed += 1

    except Exception as e:
        errors += 1
        print("ERROR", i, repr(e))

dt = time.perf_counter() - t0

print("cycles =", N)
print("completed =", completed)
print("errors =", errors)
print("elapsed =", round(dt, 4), "sec")
print("cycles/sec =", round(N / dt, 2))

try:
    print("final_state =", o.state_machine.state)
except Exception:
    pass
PY

cat "$OUT/sequential_stress.txt"

# ------------------------------------------------------------
# 7. MULTIPROCESS STRESS
# ------------------------------------------------------------

section "7 — MULTIPROCESS STRESS"

python - <<'PY' > "$OUT/multiprocess_stress.txt"
import multiprocessing as mp
import time

def worker(n):
    from trader.orchestrator import Orchestrator

    o = Orchestrator()
    errors = 0

    for _ in range(n):
        try:
            r = o.run_cycle()
            if getattr(r, "error", None):
                errors += 1
        except Exception:
            errors += 1

    return n, errors

WORKERS = 4
PER_WORKER = 50

t0 = time.perf_counter()

with mp.Pool(WORKERS) as p:
    results = p.map(worker, [PER_WORKER] * WORKERS)

dt = time.perf_counter() - t0

total = sum(x[0] for x in results)
errors = sum(x[1] for x in results)

print("workers =", WORKERS)
print("cycles =", total)
print("errors =", errors)
print("elapsed =", round(dt, 4))
print("cycles/sec =", round(total/dt, 2))
PY

cat "$OUT/multiprocess_stress.txt"

# ------------------------------------------------------------
# 8. THREAD SAFETY TEST
# ------------------------------------------------------------

section "8 — THREAD SAFETY"

python - <<'PY' > "$OUT/thread_stress.txt"
from concurrent.futures import ThreadPoolExecutor, as_completed
from trader.orchestrator import Orchestrator

o = Orchestrator()

N = 40
errors = 0

def run(i):
    try:
        r = o.run_cycle()
        return i, getattr(r, "error", None), getattr(r, "status", None)
    except Exception as e:
        return i, repr(e), "exception"

with ThreadPoolExecutor(max_workers=8) as ex:
    futures = [ex.submit(run, i) for i in range(N)]

    for f in as_completed(futures):
        i, err, status = f.result()

        if err:
            errors += 1
            print("ERROR", i, err, status)

print("threads =", 8)
print("cycles =", N)
print("errors =", errors)
PY

cat "$OUT/thread_stress.txt"

# ------------------------------------------------------------
# 9. MANUAL DATA VALIDATION / ADVERSARIAL INPUTS
# ------------------------------------------------------------

section "9 — INPUT VALIDATION / ADVERSARIAL DATA"

python - <<'PY' > "$OUT/validation_audit.txt"
from trader.web.server import ManualDataRequest

tests = []

base = dict(
    schema_version="1.0",
    snapshot_id="stress-test",
    symbol="BTC/USDT",
    exchange="test",
    timestamp="2026-09-27T16:00:00Z",
    timeframe="1m",
    price=100,
    open=99,
    high=101,
    low=98,
    close=100,
    volume=1000,
    order_book={
        "bids":[[99,10],[98,20]],
        "asks":[[101,10],[102,20]]
    },
    trades=[],
    derivatives={},
    volatility={},
    technical={},
    sentiment=0,
    sentiment_detail={},
    news=[],
    macro={},
    onchain={},
    equity=100000,
    cash=100000,
    positions={},
    risk_limits={},
    execution={},
    data_quality={"completeness":1.0},
    agent_context={}
)

tests.append(("valid", base))

bad = dict(base)
bad["high"] = 90
tests.append(("bad_ohlc", bad))

bad = dict(base)
bad["volume"] = -1
tests.append(("negative_volume", bad))

bad = dict(base)
bad["equity"] = -100
tests.append(("negative_equity", bad))

bad = dict(base)
bad["data_quality"] = {"completeness": 2}
tests.append(("bad_completeness", bad))

for name, data in tests:
    try:
        ManualDataRequest(**data)
        print(name, "ACCEPTED")
    except Exception as e:
        print(name, "REJECTED", type(e).__name__)
PY

cat "$OUT/validation_audit.txt"

# ------------------------------------------------------------
# 10. KILL SWITCH
# ------------------------------------------------------------

section "10 — KILL SWITCH"

python - <<'PY' > "$OUT/kill_switch.txt"
from trader.orchestrator import Orchestrator

o = Orchestrator()

print("initial:", getattr(o.state_machine, "state", None))

try:
    o.kill_switch.activate("stress-test")
    print("activated")
except Exception as e:
    print("activate error:", repr(e))

try:
    r = o.run_cycle()
    print("cycle while killed:", r)
except Exception as e:
    print("cycle error:", repr(e))

try:
    o.kill_switch.deactivate()
    print("deactivated")
except Exception as e:
    print("deactivate error:", repr(e))

try:
    r = o.run_cycle()
    print("cycle after resume:", r)
except Exception as e:
    print("resume cycle error:", repr(e))
PY

cat "$OUT/kill_switch.txt"

# ------------------------------------------------------------
# 11. CLI KILL SWITCH BUG CHECK
# ------------------------------------------------------------

section "11 — CLI KILL SWITCH"

python -m trader.cli kill-switch on --reason stress-test \
    > "$OUT/cli_killswitch_on.txt" 2>&1 || true

python -m trader.cli kill-switch off \
    > "$OUT/cli_killswitch_off.txt" 2>&1 || true

cat "$OUT/cli_killswitch_on.txt"
cat "$OUT/cli_killswitch_off.txt"

# ------------------------------------------------------------
# 12. WEB SERVER
# ------------------------------------------------------------

section "12 — WEB CONTROL PLANE"

WEBLOG="$OUT/web.log"

python -m trader.cli web \
    --host 127.0.0.1 \
    --port 8787 \
    > "$WEBLOG" 2>&1 &

WEBPID=$!

cleanup() {
    kill "$WEBPID" 2>/dev/null || true
}

trap cleanup EXIT

sleep 3

python - <<'PY' > "$OUT/web_api_audit.txt"
import urllib.request
import json

base = "http://127.0.0.1:8787"

paths = [
    "/",
    "/api/health",
    "/api/market",
    "/api/runs",
    "/api/config",
    "/api/llm/providers",
    "/api/connectors",
    "/api/modules",
    "/docs",
    "/openapi.json",
]

for path in paths:
    try:
        with urllib.request.urlopen(base + path, timeout=5) as r:
            data = r.read(500)
            print(path, r.status, data[:200])
    except Exception as e:
        print(path, "ERROR", repr(e))
PY

cat "$OUT/web_api_audit.txt"

# ------------------------------------------------------------
# 13. WEB CONCURRENCY
# ------------------------------------------------------------

section "13 — API CONCURRENCY"

python - <<'PY' > "$OUT/api_concurrency.txt"
from concurrent.futures import ThreadPoolExecutor
import urllib.request

URL = "http://127.0.0.1:8787/api/health"

N = 100

def req(i):
    try:
        with urllib.request.urlopen(URL, timeout=10) as r:
            return r.status
    except Exception as e:
        return repr(e)

with ThreadPoolExecutor(max_workers=16) as ex:
    results = list(ex.map(req, range(N)))

ok = sum(x == 200 for x in results)

print("requests =", N)
print("200 =", ok)
print("errors =", N-ok)
PY

cat "$OUT/api_concurrency.txt"

# ------------------------------------------------------------
# 14. MEMORY / DB GROWTH
# ------------------------------------------------------------

section "14 — RESOURCE GROWTH"

python - <<'PY' > "$OUT/resource_report.txt"
import os
import sqlite3

db = "data/trader.db"

if os.path.exists(db):
    print("db_bytes =", os.path.getsize(db))

    con = sqlite3.connect(db)

    for table in [
        "cycles",
        "data_bundles",
        "decisions",
        "orders",
        "risk_results",
        "audit_log",
        "observability_events",
        "state_machine_log"
    ]:
        try:
            n = con.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
            print(table, n)
        except Exception as e:
            print(table, repr(e))

    con.close()
PY

cat "$OUT/resource_report.txt"

# ------------------------------------------------------------
# 15. SOURCE STRUCTURE
# ------------------------------------------------------------

section "15 — SOURCE / FEATURE INVENTORY"

find trader -type f | sort > "$OUT/source_files.txt"

echo "Python files:"
find trader -name '*.py' | wc -l

echo
echo "Tests:"
find tests -type f | wc -l

echo
echo "Feature files:"
find trader -type f | sort

# ------------------------------------------------------------
# 16. SECURITY / SECRET SCAN
# ------------------------------------------------------------

section "16 — BASIC SECRET / CONFIG SCAN"

grep -RInE \
'api[_-]?key|secret[_-]?key|password|token|private[_-]?key' \
trader config.yaml .env 2>/dev/null \
> "$OUT/secret_scan.txt" || true

cat "$OUT/secret_scan.txt"

# ------------------------------------------------------------
# 17. FINAL SUMMARY
# ------------------------------------------------------------

section "FINAL SUMMARY"

echo "PASS = $PASS"
echo "FAIL = $FAIL"
echo "WARN = $WARN"

echo
echo "Generated reports:"
find "$OUT" -maxdepth 2 -type f | sort

echo
echo "============================================================"
echo " AUDIT FINISHED"
echo " $(date -Is)"
echo " REPORT: $OUT"
echo "============================================================"

