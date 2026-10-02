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
import math
from dataclasses import dataclass

try:
    import yaml  # PyYAML
except ImportError:  # pragma: no cover
    yaml = None


_SECRET_KEY_PATTERN = re.compile(
    r"(?i)(api[_-]?key|broker[_-]?key|access[_-]?token|refresh[_-]?token|^key$|^token$|^secret$|^password$|^credential$)"
)
_SECRET_TEXT_PATTERN = re.compile(
    r"(?i)(api[_ -]?(?:key|secret)|access[_ -]?token|password|authorization)\s*[:=]\s*([^\s,;]+)"
)


def redact_secrets(obj):
    """Recursively redact anything that looks like a credential before it is logged
    or persisted (SECURITY_MODEL.md: 'نشت API key بروکر' control)."""
    if isinstance(obj, str):
        return _SECRET_TEXT_PATTERN.sub(lambda m: f"{m.group(1)}=***REDACTED***", obj)
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
    require_liquidity_data: bool = True
    max_spread: float | None = None

    def __post_init__(self):
        finite_nonnegative = ("max_position_size", "max_daily_loss", "exposure_limit",
                              "leverage_limit", "max_portfolio_exposure")
        for name in finite_nonnegative:
            value = getattr(self, name)
            if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value) or value < 0:
                raise ValueError(f"{name} must be a finite non-negative number")
        if self.max_spread is not None and (not isinstance(self.max_spread, (int, float)) or isinstance(self.max_spread, bool) or not math.isfinite(self.max_spread) or self.max_spread < 0):
            raise ValueError("max_spread must be None or a finite non-negative number")
        for name in ("max_drawdown", "max_correlation"):
            value = getattr(self, name)
            if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value) or not 0 <= value <= 1:
                raise ValueError(f"{name} must be finite and in [0, 1]")
        if not isinstance(self.max_reevaluate_cycles, int) or isinstance(self.max_reevaluate_cycles, bool) or self.max_reevaluate_cycles < 0:
            raise ValueError("max_reevaluate_cycles must be a non-negative integer")
        if not isinstance(self.trading_sessions, tuple) or not self.trading_sessions:
            raise ValueError("trading_sessions must contain at least one UTC window")
        for flag in ("require_stop_loss", "require_take_profit", "kill_switch", "require_liquidity_data"):
            if not isinstance(getattr(self, flag), bool):
                raise ValueError(f"{flag} must be a boolean")
        for window in self.trading_sessions:
            if not isinstance(window, str) or not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d-(?:[01]\d|2[0-3]):[0-5]\d", window):
                raise ValueError(f"invalid UTC trading session: {window!r}")

    @staticmethod
    def from_yaml(path: str) -> "RiskConfig":
        if yaml is None:
            raise RuntimeError("PyYAML not installed — `pip install pyyaml`")
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        if not isinstance(data, dict):
            raise ValueError("risk configuration must be a mapping")
        unknown = set(data) - set(RiskConfig.__dataclass_fields__)
        if unknown:
            raise ValueError(f"unknown risk configuration keys: {sorted(unknown)}")
        allowed = dict(data)
        if "trading_sessions" in allowed:
            allowed["trading_sessions"] = tuple(allowed["trading_sessions"])
        return RiskConfig(**allowed)


@dataclass
class AppConfig:
    """Non-financial runtime configuration."""
    mode: str = "paper"                 # backtest | paper | live  (ENGINEERING_SPEC.md)
    veto_window_seconds: int = 120      # EXECUTION_MODEL.md: 2-minute veto window
    on_silence: str = "wait"            # fail closed unless configured otherwise
    memory_manager_interval_seconds: int = 7200  # every 2 hours (AGENT_AND_MEMORY_MODEL.md)
    db_path: str = "xir_trader.db"
    default_order_size: float = 100.0  # nominal position-sizing policy input, independent of
                                        # RiskConfig.max_position_size so the Risk Engine's
                                        # Position Size rule can actually reject an oversized order
    broker_api_key_env: str = "XIR_BROKER_API_KEY"
    broker_api_secret_env: str = "XIR_BROKER_API_SECRET"
    telegram_bot_token_env: str = "XIR_TELEGRAM_BOT_TOKEN"
    live_confirmed: bool = False        # must be explicitly set by the operator, never by an agent
    market_data_max_age_seconds: int = 60

    def __post_init__(self):
        if self.mode not in ("backtest", "paper", "live"):
            raise ValueError(f"Unknown mode: {self.mode}")
        if not isinstance(self.veto_window_seconds, int) or isinstance(self.veto_window_seconds, bool) or self.veto_window_seconds < 0:
            raise ValueError("veto_window_seconds must be a non-negative integer")
        if self.on_silence not in ("execute", "wait"):
            raise ValueError("on_silence must be 'execute' or 'wait'")
        if not isinstance(self.memory_manager_interval_seconds, int) or isinstance(self.memory_manager_interval_seconds, bool) or self.memory_manager_interval_seconds < 0:
            raise ValueError("memory_manager_interval_seconds must be non-negative")
        if not isinstance(self.default_order_size, (int, float)) or isinstance(self.default_order_size, bool) or not math.isfinite(self.default_order_size) or self.default_order_size <= 0:
            raise ValueError("default_order_size must be finite and positive")
        if not isinstance(self.market_data_max_age_seconds, int) or isinstance(self.market_data_max_age_seconds, bool) or self.market_data_max_age_seconds <= 0:
            raise ValueError("market_data_max_age_seconds must be a positive integer")
        if not isinstance(self.live_confirmed, bool):
            raise ValueError("live_confirmed must be a boolean")
        if not isinstance(self.db_path, str) or not self.db_path:
            raise ValueError("db_path must be a non-empty path")

    def broker_credentials(self) -> dict:
        """Read broker secrets from env only — never from a config file (SECURITY_MODEL.md)."""
        return {
            "api_key": os.environ.get(self.broker_api_key_env),
            "api_secret": os.environ.get(self.broker_api_secret_env),
        }

    def validate_for_mode(self) -> None:
        if self.mode not in ("backtest", "paper", "live"):
            raise ValueError(f"Unknown mode: {self.mode}")
        if self.mode == "live":
            raise RuntimeError(
                "LIVE mode is disabled in this reference release: no reviewed live broker adapter is included."
            )
