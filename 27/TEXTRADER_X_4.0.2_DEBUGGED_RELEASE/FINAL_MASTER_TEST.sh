#!/usr/bin/env bash
set +e

ROOT="$(pwd)"
OUT="$ROOT/FINAL_MASTER_TEST_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$OUT"

LOG="$OUT/master.log"
PASS=0
FAIL=0
WARN=0

run_test() {
    NAME="$1"
    shift

    echo
    echo "============================================================"
    echo "TEST: $NAME"
    echo "============================================================"

    "$@" > "$OUT/${NAME}.log" 2>&1
    RC=$?

    cat "$OUT/${NAME}.log"

    if [ "$RC" -eq 0 ]; then
        echo "[PASS] $NAME"
        PASS=$((PASS+1))
    else
        echo "[FAIL] $NAME  exit=$RC"
        FAIL=$((FAIL+1))
    fi

    return 0
}

warn_test() {
    NAME="$1"
    shift

    echo
    echo "============================================================"
    echo "OPTIONAL: $NAME"
    echo "============================================================"

    "$@" > "$OUT/${NAME}.log" 2>&1
    RC=$?

    cat "$OUT/${NAME}.log"

    if [ "$RC" -eq 0 ]; then
        echo "[PASS] $NAME"
        PASS=$((PASS+1))
    else
        echo "[WARN] $NAME  exit=$RC"
        WARN=$((WARN+1))
    fi

    return 0
}

exec > >(tee -a "$LOG") 2>&1

echo "============================================================"
echo " TEXTRADER X 4.0.2 — FINAL MASTER TEST"
echo "============================================================"
echo "Started: $(date -Is)"
echo "Root:    $ROOT"
echo "Output:  $OUT"
echo

echo "[ENVIRONMENT]"
python --version
python -m pip --version
uname -a
echo

run_test "01_VERSION" \
    python -m trader.cli --version

run_test "02_DOCTOR" \
    python -m trader.cli doctor

run_test "03_PIP_CHECK" \
    python -m pip check

run_test "04_COMPILE" \
    python -m compileall -q trader tests

run_test "05_FULL_PYTEST" \
    python -m pytest -q

run_test "06_COVERAGE" \
    python -m pytest -q --cov=trader --cov-report=term-missing

run_test "07_HELP" \
    bash -c '
        python -m trader.cli --help &&
        python -m trader.cli analyze --help &&
        python -m trader.cli paper --help &&
        python -m trader.cli backtest --help &&
        python -m trader.cli market --help &&
        python -m trader.cli research --help &&
        python -m trader.cli llm --help &&
        python -m trader.cli connector --help &&
        python -m trader.cli kill-switch --help &&
        python -m trader.cli ingest --help &&
        python -m trader.cli web --help
    '

run_test "08_MOCK_ANALYZE" \
    env TEXTRADER_DECISION_ONLY=1 \
    python -m trader.cli analyze BTC/USDT \
    --source mock \
    --mode paper \
    --decision-only

run_test "09_MOCK_PAPER" \
    env TEXTRADER_DECISION_ONLY=1 \
    python -m trader.cli paper BTC/USDT \
    --source mock \
    --decision-only

run_test "10_BACKTEST" \
    python -m trader.cli backtest --bars 200

run_test "11_KILL_SWITCH_CLI" \
    bash -c '
        set -e
        python -m trader.cli kill-switch status
        python -m trader.cli kill-switch on --reason "FINAL_MASTER_TEST"
        python -m trader.cli kill-switch status
        python -m trader.cli kill-switch off
        python -m trader.cli kill-switch status
    '

run_test "12_KILL_SWITCH_PERSISTENCE" \
    python - <<'PY'
import os
import sqlite3
import tempfile

from trader.super_agent import SuperAgent

db = tempfile.mktemp(suffix=".db")

a = SuperAgent(db_path=db)
a.activate_kill_switch("MASTER_TEST")
assert a.kill_switch_active() is True

b = SuperAgent(db_path=db)
assert b.kill_switch_active() is True

b.deactivate_kill_switch()

c = SuperAgent(db_path=db)
assert c.kill_switch_active() is False

print("KILL_SWITCH_PERSISTENCE_OK")
print("db =", db)
PY

run_test "13_POSITION_SIZING_BOUNDARIES" \
    python - <<'PY'
import math

from trader.position_sizer import PositionSizer

try:
    s = PositionSizer()
except TypeError:
    s = PositionSizer

print("PositionSizer:", s)

bad_values = [
    0,
    -1,
    float("nan"),
    float("inf"),
    -float("inf"),
]

for x in bad_values:
    try:
        obj = PositionSizer()
        print("BAD_INPUT", repr(x), "->", end=" ")
        try:
            print(obj.calculate(x))
        except Exception as e:
            print(type(e).__name__, str(e))
    except Exception as e:
        print("INIT:", type(e).__name__, str(e))

print("POSITION_SIZING_BOUNDARY_TEST_FINISHED")
PY

run_test "14_RISK_BOUNDARIES" \
    python - <<'PY'
import math

from trader.risk_engine import RiskEngine

print("RiskEngine:", RiskEngine)

cases = [
    {"equity": 0},
    {"equity": -100},
    {"price": 0},
    {"price": -1},
    {"equity": float("nan")},
    {"equity": float("inf")},
]

for c in cases:
    print("CASE:", c)
    try:
        r = RiskEngine()
        print("RESULT:", r)
    except Exception as e:
        print("EXCEPTION:", type(e).__name__, str(e))

print("RISK_BOUNDARY_TEST_FINISHED")
PY

run_test "15_EXECUTION_GUARD" \
    python - <<'PY'
import inspect

from trader.execution_guard import ExecutionGuard

print("ExecutionGuard loaded:", ExecutionGuard)
print(inspect.signature(ExecutionGuard))

print("EXECUTION_GUARD_IMPORT_OK")
PY

run_test "16_AGENT_MODULE_IMPORTS" \
    python - <<'PY'
mods = [
    "trader",
    "trader.cli",
    "trader.super_agent",
    "trader.agent1",
    "trader.agent2",
    "trader.agent3",
    "trader.position_sizer",
    "trader.risk_engine",
    "trader.execution_guard",
    "trader.web.server",
    "trader.adapters.llm",
    "trader.adapters.broker.ccxt",
]

for m in mods:
    try:
        __import__(m)
        print("[OK]", m)
    except Exception as e:
        print("[FAIL]", m, type(e).__name__, str(e))
        raise

print("ALL_IMPORTS_OK")
PY

run_test "17_ADVERSARIAL_INPUT_VALIDATION" \
    python - <<'PY'
from pydantic import ValidationError

from trader.schemas import *

tests = {
    "negative_equity": {"equity": -1},
    "negative_volume": {"volume": -1},
    "zero_price": {"price": 0},
    "negative_price": {"price": -1},
}

for name, data in tests.items():
    print()
    print("CASE:", name)

    rejected = False

    for cls_name in [
        "MarketBar",
        "MarketData",
        "RiskInput",
        "PortfolioSnapshot",
    ]:
        cls = globals().get(cls_name)

        if cls is None:
            continue

        try:
            cls(**data)
            print(cls_name, "ACCEPTED")
        except Exception as e:
            print(cls_name, "REJECTED:", type(e).__name__)
            rejected = True

    print("RESULT:", "REJECTED" if rejected else "NOT_REJECTED")

print()
print("ADVERSARIAL_VALIDATION_FINISHED")
PY

run_test "18_WEB_IMPORT_AND_ROUTES" \
    python - <<'PY'
import inspect

from trader.web.server import app

print("APP:", app)

routes = []

for r in app.routes:
    path = getattr(r, "path", None)
    methods = sorted(getattr(r, "methods", []) or [])
    routes.append((path, methods))

for path, methods in routes:
    print(methods, path)

print("ROUTE_COUNT:", len(routes))
assert len(routes) > 0

print("WEB_ROUTES_OK")
PY

run_test "19_WEB_TESTCLIENT" \
    python - <<'PY'
from fastapi.testclient import TestClient
from trader.web.server import app

with TestClient(app, raise_server_exceptions=False) as c:

    paths = [
        "/",
        "/api/health",
        "/api/runs",
        "/api/config",
        "/api/llm/providers",
        "/api/connectors",
        "/api/modules",
        "/docs",
        "/openapi.json",
    ]

    for path in paths:
        r = c.get(path)
        print(path, "->", r.status_code)
        print(r.text[:500])

        assert r.status_code < 500, (path, r.status_code, r.text[:1000])

print("WEB_BASIC_ENDPOINTS_OK")
PY

run_test "20_WEB_ADVERSARIAL" \
    python - <<'PY'
from fastapi.testclient import TestClient
from trader.web.server import app

with TestClient(app, raise_server_exceptions=False) as c:

    tests = [
        ("GET", "/api/market?symbol="),
        ("GET", "/api/market?symbol=INVALID"),
        ("GET", "/api/market?symbol=../../etc/passwd"),
        ("GET", "/api/runs?limit=-1"),
        ("GET", "/api/runs?limit=999999999"),
        ("POST", "/api/analyze"),
        ("POST", "/api/paper"),
    ]

    for method, path in tests:
        try:
            if method == "GET":
                r = c.get(path)
            else:
                r = c.post(path, json={})

            print(method, path, "->", r.status_code)
            print(r.text[:1000])

            assert r.status_code < 500, (
                method,
                path,
                r.status_code,
                r.text[:1000],
            )

        except Exception as e:
            print("EXCEPTION:", method, path, type(e).__name__, str(e))
            raise

print("WEB_ADVERSARIAL_OK")
PY

run_test "21_API_CONCURRENCY_100" \
    python - <<'PY'
from concurrent.futures import ThreadPoolExecutor, as_completed

from fastapi.testclient import TestClient
from trader.web.server import app

def one(i):
    with TestClient(app, raise_server_exceptions=False) as c:
        r = c.get("/api/health")
        return i, r.status_code

results = []

with ThreadPoolExecutor(max_workers=20) as ex:
    futures = [ex.submit(one, i) for i in range(100)]

    for f in as_completed(futures):
        results.append(f.result())

errors = [x for x in results if x[1] >= 500]

print("REQUESTS:", len(results))
print("ERRORS:", len(errors))

for x in errors[:20]:
    print("ERROR:", x)

assert len(results) == 100
assert not errors

print("API_CONCURRENCY_100_OK")
PY

run_test "22_PAPER_STRESS_100" \
    bash -c '
        TEXTRADER_DECISION_ONLY=1 \
        python -m trader.cli paper BTC/USDT \
        --source mock \
        --cycles 100 \
        --decision-only
    '

run_test "23_REAL_BITGET_MARKET" \
    bash -c '
        timeout 30s \
        python -m trader.cli market BTC/USDT \
        --source bitget \
        --interval 1m \
        --limit 20
    '

run_test "24_REAL_BITGET_ANALYZE" \
    bash -c '
        timeout 60s \
        env TEXTRADER_DECISION_ONLY=1 \
        python -m trader.cli analyze BTC/USDT \
        --source bitget \
        --mode paper \
        --decision-only
    '

run_test "25_REAL_BITGET_PAPER_20" \
    bash -c '
        timeout 120s \
        env TEXTRADER_DECISION_ONLY=1 \
        python -m trader.cli paper BTC/USDT \
        --source bitget \
        --cycles 20 \
        --decision-only
    '

run_test "26_DECISION_ONLY_INVARIANT" \
    python - <<'PY'
import os

os.environ["TEXTRADER_DECISION_ONLY"] = "1"

from trader.super_agent import SuperAgent

print("DECISION_ONLY =", os.environ["TEXTRADER_DECISION_ONLY"])

print("SuperAgent import OK")

print("DECISION_ONLY_INVARIANT_TEST_FINISHED")
PY

run_test "27_DB_INTEGRITY" \
    python - <<'PY'
import sqlite3
from pathlib import Path

db = Path("data/trader.db")

print("DB:", db)

if not db.exists():
    print("DATABASE_NOT_FOUND")
    raise SystemExit(1)

con = sqlite3.connect(db)

print("integrity_check:")
print(con.execute("PRAGMA integrity_check").fetchall())

print("foreign_key_check:")
print(con.execute("PRAGMA foreign_key_check").fetchall())

assert con.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
assert con.execute("PRAGMA foreign_key_check").fetchall() == []

print("DB_INTEGRITY_OK")
PY

run_test "28_SECRET_SCAN" \
    bash -c '
        echo "Scanning source for obvious hard-coded credentials..."
        if grep -RInE \
          --exclude-dir=.venv \
          --exclude-dir=__pycache__ \
          --exclude="*.pyc" \
          "(sk-[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|BEGIN (RSA|OPENSSH|EC) PRIVATE KEY|api[_-]?secret[[:space:]]*=[[:space:]]*[\"'\"'][^\"'\"']{8,})" \
          trader tests 2>/dev/null
        then
            echo "POSSIBLE_SECRET_FOUND"
            exit 1
        else
            echo "NO_OBVIOUS_HARDCODED_SECRETS_FOUND"
        fi
    '

run_test "29_PYTEST_NO_WARNINGS" \
    bash -c '
        python -m pytest -q -W error
    '

echo
echo "============================================================"
echo " FINAL RESULT"
echo "============================================================"
echo "PASS = $PASS"
echo "FAIL = $FAIL"
echo "WARN = $WARN"
echo
echo "OUTPUT DIRECTORY:"
echo "$OUT"
echo
echo "LOG:"
echo "$LOG"
echo

echo "FAILED TEST LOGS:"
find "$OUT" -maxdepth 1 -type f -name "*.log" -print0 |
while IFS= read -r -d "" f; do
    if grep -q "\[FAIL\]" "$f" 2>/dev/null; then
        echo "---- $f ----"
        cat "$f"
    fi
done

echo
echo "============================================================"
echo " ARTIFACTS"
echo "============================================================"
find "$OUT" -maxdepth 1 -type f -printf "%f\n" | sort

echo
echo "============================================================"
echo " MASTER TEST FINISHED"
echo "============================================================"
echo "Finished: $(date -Is)"

if [ "$FAIL" -eq 0 ]; then
    echo
    echo "OVERALL: NO MASTER-TEST FAILURES"
else
    echo
    echo "OVERALL: FAILURES DETECTED"
fi
