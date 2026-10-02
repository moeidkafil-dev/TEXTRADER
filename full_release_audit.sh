#!/usr/bin/env bash

set -uo pipefail

PROJECT="$(pwd)"
TIMESTAMP="$(date '+%Y%m%d_%H%M%S')"
REPORT_DIR="$PROJECT/release_audit_$TIMESTAMP"
LOG="$REPORT_DIR/audit.log"
SUMMARY="$REPORT_DIR/RELEASE_AUDIT_SUMMARY.txt"

mkdir -p "$REPORT_DIR"

PASS=0
FAIL=0
WARN=0

say() {
    echo "$*" | tee -a "$LOG"
}

pass() {
    PASS=$((PASS+1))
    echo "[PASS] $*" | tee -a "$LOG"
}

fail() {
    FAIL=$((FAIL+1))
    echo "[FAIL] $*" | tee -a "$LOG"
}

warn() {
    WARN=$((WARN+1))
    echo "[WARN] $*" | tee -a "$LOG"
}

run_check() {
    local name="$1"
    shift

    say ""
    say "============================================================"
    say "CHECK: $name"
    say "============================================================"

    if "$@" >>"$LOG" 2>&1; then
        pass "$name"
        return 0
    else
        fail "$name"
        return 1
    fi
}

run_shell_check() {
    local name="$1"
    local cmd="$2"

    say ""
    say "============================================================"
    say "CHECK: $name"
    say "CMD: $cmd"
    say "============================================================"

    if bash -c "$cmd" >>"$LOG" 2>&1; then
        pass "$name"
        return 0
    else
        fail "$name"
        return 1
    fi
}

START="$(date '+%Y-%m-%d %H:%M:%S')"

say "============================================================"
say "TEXTRADER X 4.0.2 — FULL RELEASE AUDIT"
say "============================================================"
say "Project : $PROJECT"
say "Started : $START"
say "Report  : $REPORT_DIR"
say ""

# ------------------------------------------------------------
# 1. Basic environment
# ------------------------------------------------------------

say "### ENVIRONMENT ###"

python3 --version 2>&1 | tee -a "$LOG" || true
uname -a 2>&1 | tee -a "$LOG" || true

if command -v curl >/dev/null 2>&1; then
    pass "curl available"
else
    fail "curl missing"
fi

if command -v unzip >/dev/null 2>&1; then
    pass "unzip available"
else
    warn "unzip missing"
fi

# ------------------------------------------------------------
# 2. Virtual environment
# ------------------------------------------------------------

say ""
say "### VIRTUAL ENVIRONMENT ###"

if [ ! -d ".venv" ]; then
    say "Creating .venv ..."
    if python3 -m venv .venv >>"$LOG" 2>&1; then
        pass "virtual environment created"
    else
        fail "virtual environment creation"
        exit 1
    fi
else
    pass ".venv already exists"
fi

# shellcheck disable=SC1091
source .venv/bin/activate

run_check "Python executable" python --version
run_check "pip available" python -m pip --version

# ------------------------------------------------------------
# 3. Upgrade packaging tools
# ------------------------------------------------------------

run_check "pip upgrade" python -m pip install --upgrade pip setuptools wheel

# ------------------------------------------------------------
# 4. Install project
# ------------------------------------------------------------

say ""
say "### INSTALLATION ###"

if [ -f "pyproject.toml" ]; then
    run_check "editable project installation" python -m pip install -e .
else
    fail "pyproject.toml missing"
fi

if [ -f "requirements.txt" ]; then
    run_check "requirements installation" python -m pip install -r requirements.txt
else
    warn "requirements.txt not present"
fi

run_check "pip dependency consistency" python -m pip check

# ------------------------------------------------------------
# 5. Package identity
# ------------------------------------------------------------

say ""
say "### PACKAGE IDENTITY ###"

run_check "CLI version" python -m trader.cli --version
run_check "CLI help" python -m trader.cli --help
run_check "Doctor" python -m trader.cli doctor

# ------------------------------------------------------------
# 6. Python compilation
# ------------------------------------------------------------

say ""
say "### STATIC PYTHON VALIDATION ###"

run_check "compileall trader" python -m compileall -q trader
run_check "compileall tests" python -m compileall -q tests

# ------------------------------------------------------------
# 7. Pytest collection
# ------------------------------------------------------------

run_check "pytest collection" python -m pytest --collect-only -q

# ------------------------------------------------------------
# 8. Full automated test suite
# ------------------------------------------------------------

say ""
say "### FULL AUTOMATED TEST SUITE ###"

run_check "FULL PYTEST SUITE" python -m pytest -q

# Coverage if supported
if python -m pytest --help 2>&1 | grep -q -- '--cov'; then
    run_check \
        "pytest coverage" \
        python -m pytest -q --cov=trader --cov-report=term-missing --cov-report=html:"$REPORT_DIR/htmlcov"
else
    warn "pytest-cov option not available"
fi

# ------------------------------------------------------------
# 9. CLI command surface
# ------------------------------------------------------------

say ""
say "### CLI COMMAND SURFACE ###"

COMMANDS=(
    doctor
    market
    analyze
    paper
    backtest
    research
    llm
    connector
    kill-switch
    ingest
    web
)

for cmd in "${COMMANDS[@]}"; do
    if python -m trader.cli "$cmd" --help >>"$LOG" 2>&1; then
        pass "CLI command available: $cmd"
    else
        fail "CLI command unavailable/help failed: $cmd"
    fi
done

# ------------------------------------------------------------
# 10. Mock market path
# ------------------------------------------------------------

say ""
say "### MOCK MARKET PATH ###"

run_shell_check \
    "mock BTC market" \
    "python -m trader.cli market BTC/USDT --source mock --interval 1m --limit 10"

run_shell_check \
    "mock BTC analyze paper" \
    "python -m trader.cli analyze BTC/USDT --source mock --mode paper"

# ------------------------------------------------------------
# 11. Real public Bitget market path
# ------------------------------------------------------------

say ""
say "### REAL PUBLIC BITGET PATH ###"

BITGET_HTTP="$(curl -L --connect-timeout 10 --max-time 20 -sS \
    'https://api.bitget.com/api/v2/spot/market/tickers?symbol=BTCUSDT' \
    -o "$REPORT_DIR/bitget_raw.json" \
    -w '%{http_code}' 2>/dev/null || true)"

echo "Bitget HTTP status: $BITGET_HTTP" | tee -a "$LOG"

if [ "$BITGET_HTTP" = "200" ]; then
    pass "Bitget public REST reachable"
else
    warn "Bitget public REST unavailable, HTTP=$BITGET_HTTP"
fi

run_shell_check \
    "Bitget BTC market" \
    "python -m trader.cli market BTC/USDT --source bitget --interval 1m --limit 10"

run_shell_check \
    "Bitget BTC analyze paper" \
    "python -m trader.cli analyze BTC/USDT --source bitget --mode paper"

# ------------------------------------------------------------
# 12. Validate Bitget output for real data
# ------------------------------------------------------------

say ""
say "### REAL-DATA SEMANTIC VALIDATION ###"

BITGET_ANALYZE="$REPORT_DIR/bitget_analyze.json"

if python -m trader.cli analyze BTC/USDT --source bitget --mode paper \
    >"$BITGET_ANALYZE" 2>"$REPORT_DIR/bitget_analyze.err"; then

    if grep -q '"instrument": "BTC/USDT"' "$BITGET_ANALYZE"; then
        pass "Bitget analysis contains BTC/USDT instrument"
    else
        warn "Bitget analysis instrument field not found"
    fi

    if grep -q '"rationale"' "$BITGET_ANALYZE"; then
        pass "Bitget analysis contains decision rationale"
    else
        fail "Bitget analysis missing rationale"
    fi

    if grep -q '"failure"' "$BITGET_ANALYZE"; then
        pass "Agent2 failure analysis present"
    else
        fail "Agent2 failure analysis missing"
    fi

    if grep -q '"final"' "$BITGET_ANALYZE"; then
        pass "Final decision present"
    else
        fail "Final decision missing"
    fi

    if grep -q '"execution_impossibility"' "$BITGET_ANALYZE"; then
        pass "F9 execution-impossibility analysis present"
    else
        fail "F9 execution-impossibility analysis missing"
    fi

else
    warn "Bitget semantic validation skipped because analyze failed"
fi

# ------------------------------------------------------------
# 13. All nine failure categories
# ------------------------------------------------------------

say ""
say "### AGENT2 FAILURE-COVERAGE CHECK ###"

python - "$BITGET_ANALYZE" >>"$LOG" 2>&1 <<'PY'
import json
import sys

path = sys.argv[1]

try:
    data = json.load(open(path))
except Exception as e:
    print("JSON parse failed:", e)
    raise SystemExit(1)

expected = {
    "wrong_prediction",
    "logical_inconsistency",
    "missing_data",
    "invalid_assumption",
    "risk_violation",
    "contradictory_evidence",
    "tool_failure",
    "model_uncertainty",
    "execution_impossibility",
}

actual = {
    x.get("category")
    for x in data.get("failure", {}).get("paths", [])
    if isinstance(x, dict)
}

missing = expected - actual
extra = actual - expected

print("Expected categories:", sorted(expected))
print("Actual categories  :", sorted(actual))
print("Missing            :", sorted(missing))
print("Extra              :", sorted(extra))

if missing:
    raise SystemExit(1)
PY

if [ $? -eq 0 ]; then
    pass "Agent2 exposes all 9 failure categories"
else
    fail "Agent2 failure-category coverage"
fi

# ------------------------------------------------------------
# 14. Paper trading
# ------------------------------------------------------------

say ""
say "### PAPER TRADING ###"

if python -m trader.cli paper --help >>"$LOG" 2>&1; then
    pass "paper command available"
else
    fail "paper command help"
fi

# Try default paper execution without assuming hidden options.
if python -m trader.cli paper BTC/USDT >>"$LOG" 2>&1; then
    pass "paper BTC/USDT execution"
else
    warn "paper BTC/USDT command requires different arguments or failed"
fi

# ------------------------------------------------------------
# 15. Backtest
# ------------------------------------------------------------

say ""
say "### BACKTEST ###"

if python -m trader.cli backtest --help >>"$LOG" 2>&1; then
    pass "backtest command available"
else
    fail "backtest command help"
fi

# ------------------------------------------------------------
# 16. Research
# ------------------------------------------------------------

say ""
say "### RESEARCH ###"

if python -m trader.cli research --help >>"$LOG" 2>&1; then
    pass "research command available"
else
    fail "research command help"
fi

# ------------------------------------------------------------
# 17. LLM
# ------------------------------------------------------------

say ""
say "### LLM SUBSYSTEM ###"

if python -m trader.cli llm --help >>"$LOG" 2>&1; then
    pass "LLM command surface available"
else
    fail "LLM command surface"
fi

# ------------------------------------------------------------
# 18. Connector
# ------------------------------------------------------------

say ""
say "### CONNECTOR SUBSYSTEM ###"

if python -m trader.cli connector --help >>"$LOG" 2>&1; then
    pass "connector command surface available"
else
    fail "connector command surface"
fi

# ------------------------------------------------------------
# 19. Kill switch
# ------------------------------------------------------------

say ""
say "### KILL SWITCH ###"

if python -m trader.cli kill-switch --help >>"$LOG" 2>&1; then
    pass "kill-switch command surface available"
else
    fail "kill-switch command surface"
fi

# ------------------------------------------------------------
# 20. Ingest
# ------------------------------------------------------------

say ""
say "### INGEST ###"

if python -m trader.cli ingest --help >>"$LOG" 2>&1; then
    pass "ingest command surface available"
else
    fail "ingest command surface"
fi

# ------------------------------------------------------------
# 21. Web application
# ------------------------------------------------------------

say ""
say "### WEB APPLICATION ###"

WEB_LOG="$REPORT_DIR/web.log"

python -m trader.cli web \
    --host 127.0.0.1 \
    --port 18787 \
    --symbol BTC/USDT \
    >"$WEB_LOG" 2>&1 &

WEB_PID=$!

sleep 5

if kill -0 "$WEB_PID" 2>/dev/null; then
    pass "web server process started"
else
    fail "web server failed to start"
fi

WEB_HTTP="$(curl -sS \
    --connect-timeout 5 \
    --max-time 10 \
    -o "$REPORT_DIR/web_response.html" \
    -w '%{http_code}' \
    http://127.0.0.1:18787/ 2>/dev/null || true)"

echo "Web HTTP status: $WEB_HTTP" | tee -a "$LOG"

if [ "$WEB_HTTP" = "200" ]; then
    pass "web dashboard HTTP 200"
else
    warn "web dashboard did not return HTTP 200: $WEB_HTTP"
fi

kill "$WEB_PID" 2>/dev/null || true
wait "$WEB_PID" 2>/dev/null || true

# ------------------------------------------------------------
# 22. Security / live execution audit
# ------------------------------------------------------------

say ""
say "### SAFETY / LIVE-EXECUTION AUDIT ###"

if grep -RniE \
    'place-order|create_order|submit_order|market_order|limit_order' \
    trader \
    >"$REPORT_DIR/order_execution_matches.txt" 2>/dev/null; then

    warn "Potential order-execution references found; inspect order_execution_matches.txt"
else
    pass "No obvious broker order API references found"
fi

if grep -RniE \
    'TEXTRADER_DECISION_ONLY|decision-only|broker submission disabled' \
    trader \
    >"$REPORT_DIR/decision_only_matches.txt" 2>/dev/null; then

    pass "Decision-only safety interlock references found"
else
    fail "Decision-only safety interlock references not found"
fi

if grep -RniE \
    'api[_-]?key|secret|private[_-]?key|password|token' \
    trader \
    --exclude='*.pyc' \
    >"$REPORT_DIR/secret_reference_scan.txt" 2>/dev/null; then

    warn "Secret-like identifiers found in source; inspect secret_reference_scan.txt"
else
    pass "No obvious hard-coded secret identifiers found"
fi

# ------------------------------------------------------------
# 23. Git / release hygiene
# ------------------------------------------------------------

say ""
say "### RELEASE HYGIENE ###"

if [ -d ".git" ]; then
    if git status --porcelain >"$REPORT_DIR/git_status.txt" 2>/dev/null; then
        if [ -s "$REPORT_DIR/git_status.txt" ]; then
            warn "Working tree has changes"
        else
            pass "Git working tree clean"
        fi
    fi
else
    warn "Not a git checkout"
fi

if find . -type f \( -name '*.pyc' -o -name '*.pyo' \) \
    -not -path './.venv/*' | grep -q .; then
    warn "Compiled Python artifacts exist"
else
    pass "No stray Python bytecode artifacts"
fi

# ------------------------------------------------------------
# 24. Project size
# ------------------------------------------------------------

say ""
say "### PRODUCT SIZE ###"

CORE_SIZE="$(du -sh trader 2>/dev/null | awk '{print $1}')"
TOTAL_SOURCE_SIZE="$(du -sh --exclude=.venv --exclude=release_audit_* . 2>/dev/null | awk '{print $1}')"

say "Core trader/ size: $CORE_SIZE"
say "Total source tree excluding .venv/audit: $TOTAL_SOURCE_SIZE"

# ------------------------------------------------------------
# 25. Generate summary
# ------------------------------------------------------------

END="$(date '+%Y-%m-%d %H:%M:%S')"

{
    echo "============================================================"
    echo "TEXTRADER X 4.0.2 — RELEASE AUDIT SUMMARY"
    echo "============================================================"
    echo
    echo "Project:"
    echo "$PROJECT"
    echo
    echo "Started:"
    echo "$START"
    echo
    echo "Finished:"
    echo "$END"
    echo
    echo "------------------------------------------------------------"
    echo "RESULTS"
    echo "------------------------------------------------------------"
    echo "PASS : $PASS"
    echo "WARN : $WARN"
    echo "FAIL : $FAIL"
    echo
    echo "------------------------------------------------------------"
    echo "INTERPRETATION"
    echo "------------------------------------------------------------"

    if [ "$FAIL" -eq 0 ]; then
        echo "AUTOMATED AUDIT STATUS: PASS"
    else
        echo "AUTOMATED AUDIT STATUS: FAIL"
    fi

    if [ "$WARN" -eq 0 ]; then
        echo "WARNINGS: NONE"
    else
        echo "WARNINGS: $WARN"
    fi

    echo
    echo "IMPORTANT:"
    echo "A passing automated audit does NOT prove profitability,"
    echo "absence of all software defects, or safety for unrestricted"
    echo "real-money trading."
    echo
    echo "Before any real-money test, inspect:"
    echo "  - bitget_analyze.json"
    echo "  - secret_reference_scan.txt"
    echo "  - order_execution_matches.txt"
    echo "  - decision_only_matches.txt"
    echo "  - web.log"
    echo "  - audit.log"
    echo
    echo "Full report directory:"
    echo "$REPORT_DIR"
    echo "============================================================"
} | tee "$SUMMARY"

say ""
say "============================================================"
say "AUDIT FINISHED"
say "============================================================"
say "PASS=$PASS  WARN=$WARN  FAIL=$FAIL"
say "Summary: $SUMMARY"
say "Log:     $LOG"
say "============================================================"

exit 0
