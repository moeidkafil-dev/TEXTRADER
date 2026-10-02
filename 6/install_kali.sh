#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN="${PYTHON_BIN:-python3}"

"$PYTHON_BIN" --version
"$PYTHON_BIN" -m venv .venv
source .venv/bin/activate

python -m pip install --upgrade pip
python -m pip install -e ".[dev]"

printf '\nTRADER/XIR 2.0.1 installed successfully.\n'
printf 'Activate with:\n  source .venv/bin/activate\n'
printf 'Then run:\n'
printf '  xir doctor\n'
printf '  pytest -q\n'
printf '  xir market BTC/USDT\n'
printf '  xir analyze BTC/USDT --source binance\n'
printf '  xir web\n'
