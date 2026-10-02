"""
Configuration loader for the runtime.

- `config/risk.yaml`  — 11 risk rules + kill_switch
- `config/trader.yaml` — runtime mode, sources, veto window, memory manager interval

The risk config is the ONLY place where numeric risk thresholds live. Agents
have no read access to broker credentials and no write access to risk config
(chapter 09 SECURITY_MODEL).
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import yaml  # type: ignore
except ImportError:  # pragma: no cover
    yaml = None


# Default paths
CONFIG_DIR = Path(os.environ.get("TRADER_CONFIG_DIR", "config"))
RISK_CONFIG_PATH = CONFIG_DIR / "risk.yaml"
TRADER_CONFIG_PATH = CONFIG_DIR / "trader.yaml"


@dataclass
class RiskConfig:
    max_position_size: float = 1_000.0          # units
    max_daily_loss: float = 0.02                # fraction of equity (2%)
    max_drawdown: float = 0.10                  # fraction of peak equity (10%)
    exposure_limit: float = 0.50                # max fraction of equity at risk
    leverage_limit: float = 1.0                 # 1x = no leverage
    require_stop_loss: bool = True
    require_take_profit: bool = True
    max_correlation: float = 0.85               # pairwise correlation cap
    max_portfolio_exposure: float = 0.75        # total exposure as fraction of equity
    trading_sessions: list[str] = field(default_factory=lambda: ["00:00-23:59"])  # 24h default
    kill_switch: bool = False                   # if True at load ⇒ HALTED on start

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "RiskConfig":
        known = {f for f in cls.__dataclass_fields__}  # type: ignore[arg-type]
        clean = {k: v for k, v in d.items() if k in known}
        return cls(**clean)

    def to_dict(self) -> dict[str, Any]:
        return {
            "max_position_size": self.max_position_size,
            "max_daily_loss": self.max_daily_loss,
            "max_drawdown": self.max_drawdown,
            "exposure_limit": self.exposure_limit,
            "leverage_limit": self.leverage_limit,
            "require_stop_loss": self.require_stop_loss,
            "require_take_profit": self.require_take_profit,
            "max_correlation": self.max_correlation,
            "max_portfolio_exposure": self.max_portfolio_exposure,
            "trading_sessions": self.trading_sessions,
            "kill_switch": self.kill_switch,
        }


@dataclass
class TraderConfig:
    mode: str = "paper"               # backtest | paper | live
    veto_window_seconds: int = 120    # 2-minute veto window (chapter 08)
    on_silence: str = "execute"       # execute | wait  (P-02; default = ORIGINAL)
    max_reevaluate_cycles: int = 3    # P-01: cap on RE-EVAL loops
    memory_manager_interval_seconds: int = 7200  # 2-hour sleep mode (REQ-MEM-04)
    llm_provider: str = "mock"        # mock | openai | anthropic | ollama | ...
    broker: str = "mock"              # mock | alpaca | binance | ...
    initial_equity: float = 100_000.0
    data_sources: list[str] = field(default_factory=lambda: ["mock://ohlcv"])
    instruments: list[str] = field(default_factory=lambda: ["XIR/USDT"])
    enable_user_veto: bool = True
    enable_email: bool = False
    enable_telegram: bool = False
    db_path: str = "data/trader.db"
    log_level: str = "info"

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "TraderConfig":
        known = {f for f in cls.__dataclass_fields__}  # type: ignore[arg-type]
        clean = {k: v for k, v in d.items() if k in known}
        return cls(**clean)


def validate_runtime_config(config: TraderConfig) -> None:
    """Fail closed on unsafe runtime configuration."""
    if config.mode not in {"backtest", "paper", "live"}:
        raise ValueError(f"Unsupported runtime mode: {config.mode!r}")
    if config.on_silence not in {"execute", "wait"}:
        raise ValueError(f"on_silence must be 'execute' or 'wait', got {config.on_silence!r}")
    if config.max_reevaluate_cycles < 0:
        raise ValueError("max_reevaluate_cycles must be >= 0")
    if config.mode == "live":
        ack = os.environ.get("TRADER_LIVE_ACK", "")
        if ack != "I_UNDERSTAND_LIVE_TRADING":
            raise RuntimeError(
                "Live mode is fail-closed. Set TRADER_LIVE_ACK=I_UNDERSTAND_LIVE_TRADING "
                "only after completing the required live-trading approval/waiver."
            )


def load_yaml(path: Path) -> dict[str, Any]:
    if yaml is None:
        raise RuntimeError("PyYAML not installed; install with: pip install pyyaml")
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data


def load_risk_config(path: Path | None = None) -> RiskConfig:
    p = path or RISK_CONFIG_PATH
    if p.is_absolute():
        data = load_yaml(p)
    else:
        # search in cwd, then in package dir
        candidates = [p, Path(__file__).resolve().parents[2] / p,
                      Path(__file__).resolve().parents[2] / "config" / p.name]
        data = {}
        for c in candidates:
            if c.exists():
                data = load_yaml(c)
                break
    return RiskConfig.from_dict(data.get("risk", data) if data else {})


def save_trader_config(config: TraderConfig, path: Path | None = None) -> Path:
    """Persist the current TraderConfig to trader.yaml so CLI/panel changes
    (e.g. switching LLM provider) survive restarts."""
    if yaml is None:
        raise RuntimeError("PyYAML not installed; install with: pip install pyyaml")
    p = path or TRADER_CONFIG_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    payload = {"trader": {f: getattr(config, f) for f in config.__dataclass_fields__}}  # type: ignore[attr-defined]
    with open(p, "w", encoding="utf-8") as f:
        yaml.safe_dump(payload, f, allow_unicode=True, sort_keys=False)
    return p


def load_trader_config(path: Path | None = None) -> TraderConfig:
    p = path or TRADER_CONFIG_PATH
    if p.is_absolute():
        data = load_yaml(p)
    else:
        candidates = [p, Path(__file__).resolve().parents[2] / p,
                      Path(__file__).resolve().parents[2] / "config" / p.name]
        data = {}
        for c in candidates:
            if c.exists():
                data = load_yaml(c)
                break
    config = TraderConfig.from_dict(data.get("trader", data) if data else {})
    validate_runtime_config(config)
    return config
