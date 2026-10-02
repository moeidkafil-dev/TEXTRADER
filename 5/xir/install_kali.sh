#!/usr/bin/env bash
set -euo pipefail
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
printf '\nTRADER/XIR installed. Activate with:\n  source .venv/bin/activate\nThen run:\n  xir doctor\n  xir market BTC/USDT\n  xir web\n'
