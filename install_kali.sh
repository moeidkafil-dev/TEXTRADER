#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN="${PYTHON_BIN:-python3}"

"$PYTHON_BIN" --version
"$PYTHON_BIN" -m venv .venv
source .venv/bin/activate

python -m pip install --upgrade pip
python -m pip install -e ".[dev,live]"

printf '\nTEXTRADER X 3.2.0 installed successfully.\n'
printf 'Activate with:\n  source .venv/bin/activate\n'
printf 'Then run:\n'
printf '  textrader doctor\n'
printf '  pytest -q\n'
printf '  textrader market BTC/USDT\n'
printf '  textrader analyze BTC/USDT --source binance\n'
printf '  textrader web\n'
