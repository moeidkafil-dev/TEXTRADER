"""Backward-compatible public API for the supervisory agent.

The trading engine remains implemented by :mod:`trader.engine.orchestrator`.
This facade preserves the historical ``SuperAgent`` control API without
duplicating trading logic.
"""
from __future__ import annotations

from pathlib import Path

from .core.config import load_risk_config, load_trader_config
from .engine.orchestrator import Orchestrator
from .services.super_agent import TradeThesis, synthesize


class SuperAgent:
    """Compatibility facade for the public supervisory/control API."""

    def __init__(self, db_path: str | None = None, config_path: str | None = None,
                 risk_path: str | None = None):
        trader_config = load_trader_config(Path(config_path) if config_path else None)
        risk_config = load_risk_config(Path(risk_path) if risk_path else None)
        self.orchestrator = Orchestrator(
            risk_config,
            trader_config,
            db_path=db_path,
        )

    @property
    def kill_switch(self):
        return self.orchestrator.kill_switch

    def activate_kill_switch(self, reason: str = "manual") -> None:
        self.orchestrator.activate_kill_switch(reason)

    def deactivate_kill_switch(self, reason: str = "manual_resume") -> None:
        self.orchestrator.resume_from_halted(reason)

    def kill_switch_active(self) -> bool:
        return bool(self.orchestrator.kill_switch.is_active)

    def run_cycle(self, *args, **kwargs):
        return self.orchestrator.run_cycle(*args, **kwargs)


__all__ = ["SuperAgent", "TradeThesis", "synthesize"]
