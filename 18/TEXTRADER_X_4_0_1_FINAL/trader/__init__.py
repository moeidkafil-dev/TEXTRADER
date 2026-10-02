"""
TRADER (XIR) — Reference Python runtime.

Project: TRADER / textrader — Brand: XIR (اکسیر)
Owner/Inventor: Moeid Kafilonas
Date: 2026-09-22 (1405/06/31)
Source of truth: textrader.graphml (SHA-256: 4eed88d72144592d)

This package implements the chain-of-agents autonomous trading runtime described in
the TRADER_XIR engineering dossier. See README.md for the full component map and
the per-module docstrings for the formal contract of each piece.
"""

__version__ = "4.0.1"
__project__ = "TRADER (XIR)"
__owner__ = "Moeid Kafilonas"

# Public re-exports — the orchestrator is the main entrypoint.
from trader.engine.orchestrator import Orchestrator  # noqa: E402,F401
from trader.core.state_machine import State, Transition  # noqa: E402,F401
