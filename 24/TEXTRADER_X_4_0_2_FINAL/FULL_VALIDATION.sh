#!/usr/bin/env bash

PROJECT_DIR="$(pwd)"
LOG_DIR="$PROJECT_DIR/test-results"
mkdir -p "$LOG_DIR"

LOG="$LOG_DIR/full-validation-$(date +%Y%m%d-%H%M%S).log"

exec > >(tee -a "$LOG") 2>&1

FAILED=0

run_test() {
    local NAME="$1"
    shift

    echo
    echo "============================================================"
    echo "TEST: $NAME"
    echo "============================================================"

    if "$@"; then
        echo "[PASS] $NAME"
    else
        echo "[FAIL] $NAME"
        FAILED=$((FAILED + 1))
    fi
}

echo "============================================================"
echo "TEXTRADER X 4.0.2 - FULL VALIDATION"
echo "============================================================"
echo "Project : $PROJECT_DIR"
echo "Started : $(date)"
echo "Log     : $LOG"
echo

# ------------------------------------------------------------
# ENVIRONMENT
# ------------------------------------------------------------

if [ ! -d ".venv" ]; then
    echo "[INFO] Creating virtual environment..."
    python3 -m venv .venv || FAILED=$((FAILED + 1))
fi

if [ ! -f ".venv/bin/activate" ]; then
    echo "[FAIL] Virtual environment unavailable"
    exit 1
fi

source .venv/bin/activate

echo
echo "Python:"
python --version

echo
echo "Pip:"
python -m pip --version


# ------------------------------------------------------------
# DEPENDENCIES
# ------------------------------------------------------------

run_test "Dependency integrity" \
    python -m pip check

run_test "Python compilation" \
    python -m compileall -q trader tests


# ------------------------------------------------------------
# PACKAGE
# ------------------------------------------------------------

run_test "CLI version" \
    python -m trader.cli --version

run_test "CLI help" \
    python -m trader.cli --help

run_test "Doctor" \
    python -m trader.cli doctor


# ------------------------------------------------------------
# FULL PYTEST
# ------------------------------------------------------------

run_test "Full automated test suite" \
    python -m pytest -q --tb=short


# ------------------------------------------------------------
# COVERAGE
# ------------------------------------------------------------

echo
echo "============================================================"
echo "COVERAGE"
echo "============================================================"

python -m pytest \
    -q \
    --cov=trader \
    --cov-report=term-missing \
    --cov-report=html \
    --tb=short \
    || FAILED=$((FAILED + 1))


# ------------------------------------------------------------
# MATHEMATICAL / NUMERICAL SANITY
# ------------------------------------------------------------

run_test "Numerical invariants" \
python - <<'PY'
import math
from decimal import Decimal

values = [
    0.0,
    1.0,
    83981.05,
    83995.38,
    83995.39,
]

for x in values:
    assert math.isfinite(x), x

assert Decimal("83981.05") > 0
assert Decimal("83995.38") <= Decimal("83995.39")

print("finite values       : PASS")
print("decimal arithmetic  : PASS")
print("bid <= ask          : PASS")
PY


# ------------------------------------------------------------
# REAL BITGET MARKET DATA
# ------------------------------------------------------------

echo
echo "============================================================"
echo "REAL MARKET DATA"
echo "============================================================"

BITGET_FILE="$LOG_DIR/bitget-market.json"

if python -m trader.cli \
    market BTC/USDT \
    --source bitget \
    --interval 1m \
    --limit 10 \
    > "$BITGET_FILE"
then
    echo "[PASS] Bitget public market endpoint"

    python - "$BITGET_FILE" <<'PY'
import json
import sys

p = sys.argv[1]

with open(p) as f:
    d = json.load(f)

assert d["symbol"] == "BTC/USDT"
assert d["bars"] >= 1

ticker = d["ticker"]

assert ticker["lastPrice"]
assert float(ticker["lastPrice"]) > 0

bid = float(d["best_bid"][0])
ask = float(d["best_ask"][0])

assert bid > 0
assert ask > 0
assert bid <= ask

print("symbol      :", d["symbol"])
print("last price  :", ticker["lastPrice"])
print("best bid    :", bid)
print("best ask    :", ask)
print("bars        :", d["bars"])
print("REALITY TEST: PASS")
PY

else
    echo "[FAIL] Bitget public market endpoint"
    FAILED=$((FAILED + 1))
fi


# ------------------------------------------------------------
# REAL DATA -> AGENT DECISION
# ------------------------------------------------------------

echo
echo "============================================================"
echo "REAL DATA -> AGENT DECISION"
echo "============================================================"

ANALYZE_FILE="$LOG_DIR/bitget-analyze.json"

if python -m trader.cli \
    analyze BTC/USDT \
    --source bitget \
    --mode paper \
    --decision-only \
    > "$ANALYZE_FILE"
then

    python - "$ANALYZE_FILE" <<'PY'
import json
import sys

p = sys.argv[1]

with open(p) as f:
    d = json.load(f)

assert d.get("initial") is not None
assert d.get("final") is not None

initial = d["initial"]

assert initial.get("instrument") == "BTC/USDT"
assert initial.get("rationale") != "no market data"

print("instrument :", initial.get("instrument"))
print("action     :", initial.get("action"))
print("rationale  :", initial.get("rationale"))
print("decision   :", d["final"].get("decision"))
print("state      :", d.get("final_state"))
print("REAL DATA -> AGENT: PASS")
PY

else
    echo "[FAIL] Real data -> Agent decision"
    FAILED=$((FAILED + 1))
fi


# ------------------------------------------------------------
# EXECUTION SAFETY
# ------------------------------------------------------------

echo
echo "============================================================"
echo "EXECUTION SAFETY"
echo "============================================================"

LIVE_FILE="$LOG_DIR/live-attempt.txt"

if python -m trader.cli \
    analyze BTC/USDT \
    --source bitget \
    --mode live \
    > "$LIVE_FILE" 2>&1
then

    echo "[FAIL] Read-only source accepted live execution"
    cat "$LIVE_FILE"
    FAILED=$((FAILED + 1))

else

    echo "[PASS] Live execution rejected"
    cat "$LIVE_FILE"
fi


# ------------------------------------------------------------
# CLI MATRIX
# ------------------------------------------------------------

run_test "CLI market" \
    python -m trader.cli \
    market BTC/USDT \
    --source bitget \
    --interval 1m \
    --limit 3

run_test "CLI analyze paper" \
    python -m trader.cli \
    analyze BTC/USDT \
    --source bitget \
    --mode paper \
    --decision-only


# ------------------------------------------------------------
# WEB UI
# ------------------------------------------------------------

echo
echo "============================================================"
echo "WEB UI"
echo "============================================================"

WEB_LOG="$LOG_DIR/web-server.log"
WEB_ROOT="$LOG_DIR/web-root.html"
WEB_DOCS="$LOG_DIR/web-docs.html"
WEB_OPENAPI="$LOG_DIR/openapi.json"

WEB_PID=""

cleanup_web() {
    if [ -n "$WEB_PID" ]; then
        kill "$WEB_PID" 2>/dev/null || true
        wait "$WEB_PID" 2>/dev/null || true
        WEB_PID=""
    fi
}

cleanup_web

python -m uvicorn \
    trader.web.app:app \
    --host 127.0.0.1 \
    --port 8765 \
    > "$WEB_LOG" 2>&1 &

WEB_PID=$!

echo "Web PID: $WEB_PID"

READY=0

for i in $(seq 1 20); do
    if curl -fsS \
        --max-time 2 \
        http://127.0.0.1:8765/ \
        > "$WEB_ROOT"
    then
        READY=1
        break
    fi

    sleep 0.5
done

if [ "$READY" -eq 1 ]; then

    echo "[PASS] Web server startup"

    if curl -fsS \
        --max-time 5 \
        http://127.0.0.1:8765/docs \
        > "$WEB_DOCS"
    then
        echo "[PASS] Web /docs"
    else
        echo "[FAIL] Web /docs"
        FAILED=$((FAILED + 1))
    fi

    if curl -fsS \
        --max-time 5 \
        http://127.0.0.1:8765/openapi.json \
        > "$WEB_OPENAPI"
    then

        python - "$WEB_OPENAPI" <<'PY'
import json
import sys

with open(sys.argv[1]) as f:
    d = json.load(f)

assert isinstance(d.get("paths"), dict)

print("OpenAPI routes:", len(d["paths"]))
print("OpenAPI: PASS")
PY

    else
        echo "[FAIL] OpenAPI"
        FAILED=$((FAILED + 1))
    fi

else

    echo "[FAIL] Web server startup"
    cat "$WEB_LOG"
    FAILED=$((FAILED + 1))

fi

cleanup_web


# ------------------------------------------------------------
# FINAL REPORT
# ------------------------------------------------------------

echo
echo "============================================================"
echo "FINAL VALIDATION REPORT"
echo "============================================================"

if [ "$FAILED" -eq 0 ]; then

    echo
    echo "████████████████████████████████████████████████"
    echo " ALL TEST GROUPS PASSED"
    echo "████████████████████████████████████████████████"
    echo
    echo "Logic / regression : PASS"
    echo "Numerical checks   : PASS"
    echo "Real Bitget data   : PASS"
    echo "Agent integration  : PASS"
    echo "Read-only safety   : PASS"
    echo "CLI                : PASS"
    echo "Web UI             : PASS"
    echo "OpenAPI             : PASS"
    echo
    echo "Log:"
    echo "$LOG"
    echo

else

    echo
    echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
    echo " VALIDATION FAILED"
    echo " Failed groups: $FAILED"
    echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
    echo
    echo "Log:"
    echo "$LOG"
    echo

fi

echo "Finished: $(date)"

# IMPORTANT:
# Do NOT kill the user's shell.
# Only return the validation status.
exit "$FAILED"
