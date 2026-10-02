"""
RiskConfig + AppConfig.

Security model (09_SECURITY/SECURITY_MODEL.md):
  - Agents never get a reference to RiskConfig with write access.
  - Broker credentials come only from environment variables, never from
    files that get logged, and are never written into memory_items /
    audit_log / observability_events (redact_secrets below is used
    everywhere those tables are written).
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Optional

try:
    import yaml  # PyYAML
except ImportError:  # pragma: no cover
    yaml = None


_SECRET_KEY_PATTERN = re.compile(r"(key|token|secret|password|credential)", re.IGNORECASE)


def redact_secrets(obj):
    """Recursively redact anything that looks like a credential before it is logged
    or persisted (SECURITY_MODEL.md: 'نشت API key بروکر' control)."""
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if _SECRET_KEY_PATTERN.search(str(k)):
                out[k] = "***REDACTED***"
            else:
                out[k] = redact_secrets(v)
        return out
    if isinstance(obj, (list, tuple)):
        return [redact_secrets(v) for v in obj]
    return obj


@dataclass(frozen=True)
class RiskConfig:
    """07_RISK_ENGINE/RISK_ENGINE.md — RiskConfig parameters (owner-set values, OI-07)."""
    max_position_size: float = 1000.0
    max_daily_loss: float = 200.0
    max_drawdown: float = 0.10          # fraction of equity
    exposure_limit: float = 5000.0
    leverage_limit: float = 5.0
    require_stop_loss: bool = True
    require_take_profit: bool = True
    max_correlation: float = 0.8
    max_portfolio_exposure: float = 10000.0
    trading_sessions: tuple = ("00:00-23:59",)  # UTC windows; default = always open
    kill_switch: bool = False           # manual / external activation flag
    max_reevaluate_cycles: int = 3      # P-01: cap on RE-EVALUATE loop

    @staticmethod
    def from_yaml(path: str) -> "RiskConfig":
        if yaml is None:
            raise RuntimeError("PyYAML not installed — `pip install pyyaml`")
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        allowed = {k: v for k, v in data.items() if k in RiskConfig.__dataclass_fields__}
        if "trading_sessions" in allowed:
            allowed["trading_sessions"] = tuple(allowed["trading_sessions"])
        return RiskConfig(**allowed)


@dataclass
class AppConfig:
    """Non-financial runtime configuration."""
    mode: str = "paper"                 # backtest | paper | live  (ENGINEERING_SPEC.md)
    veto_window_seconds: int = 120      # EXECUTION_MODEL.md: 2-minute veto window
    on_silence: str = "execute"         # execute | wait  (P-02; default = execute per original design)
    memory_manager_interval_seconds: int = 7200  # every 2 hours (AGENT_AND_MEMORY_MODEL.md)
    db_path: str = "xir_trader.db"
    default_order_size: float = 100.0  # nominal position-sizing policy input, independent of
                                        # RiskConfig.max_position_size so the Risk Engine's
                                        # Position Size rule can actually reject an oversized order
    broker_api_key_env: str = "XIR_BROKER_API_KEY"
    broker_api_secret_env: str = "XIR_BROKER_API_SECRET"
    telegram_bot_token_env: str = "XIR_TELEGRAM_BOT_TOKEN"
    live_confirmed: bool = False        # must be explicitly set by the operator, never by an agent

    def broker_credentials(self) -> dict:
        """Read broker secrets from env only — never from a config file (SECURITY_MODEL.md)."""
        return {
            "api_key": os.environ.get(self.broker_api_key_env),
            "api_secret": os.environ.get(self.broker_api_secret_env),
        }

    def validate_for_mode(self) -> None:
        if self.mode not in ("backtest", "paper", "live"):
            raise ValueError(f"Unknown mode: {self.mode}")
        if self.mode == "live" and not self.live_confirmed:
            raise RuntimeError(
                "LIVE mode requires AppConfig.live_confirmed=True, set only by an operator "
                "via an explicit CLI flag, per SUPER_PROMPT.md §3 "
                "('اجرای live بدون پرچم صریح و بدون آزمون paper' is prohibited)."
            )
