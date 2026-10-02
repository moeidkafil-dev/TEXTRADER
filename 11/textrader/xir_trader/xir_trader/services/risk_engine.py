"""
Risk Engine — 07_RISK_ENGINE/RISK_ENGINE.md.

Ordered rules (graph order, fixed — values tunable per OI-07):
  1. Position Size
  2. Max Daily Loss
  3. Max Drawdown
  4. Exposure Limit
  5. Leverage Limit
  6. Stop Loss Validation
  7. Take Profit Validation
  8. Correlation Exposure
  9. Portfolio Exposure
  10. Trading Session Rules
  11. Emergency Kill Switch

P-03: all 11 rules are deterministic (no LLM in the critical path).
P-05: Kill Switch has absolute priority and is checked first AND last —
      first so a halted system never even evaluates an order, last so
      nothing downstream can architecturally bypass it.
Per OI-03, this class is invoked twice around Decision Engine/Validator:
  Agent3 -> RiskEngine (rules) -> DecisionEngine -> DecisionValidator
          -> RiskEngine (final check) -> ExecutionGuard -> Broker -> FinalTools
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from ..core.config import RiskConfig
from ..core.schemas import ExecutionOrder, RiskResult, RiskRuleResult


@dataclass
class PortfolioSnapshot:
    equity: float
    daily_pnl: float
    drawdown: float                 # fraction, e.g. 0.05 = 5%
    open_positions: dict            # instrument -> {size, correlation_group}
    total_exposure: float
    leverage: float
    correlated_exposure: float = 0.0


def _in_trading_session(sessions: tuple, now: dt.datetime) -> bool:
    hm = now.strftime("%H:%M")
    for window in sessions:
        start, end = window.split("-")
        if start <= hm <= end:
            return True
    return False


class RiskEngine:
    def __init__(self, config: RiskConfig):
        self.config = config  # read-only reference; agents never get a mutable handle to this

    def check(self, order: ExecutionOrder, portfolio: PortfolioSnapshot,
              now: dt.datetime | None = None) -> RiskResult:
        now = now or dt.datetime.utcnow()
        rules: list[RiskRuleResult] = []

        def add(name: str, passed: bool, reason: str):
            rules.append(RiskRuleResult(rule=name, passed=passed, reason=reason))

        # 11. Emergency Kill Switch is checked FIRST (absolute priority, P-05) —
        # if active, every other rule is short-circuited to "fail".
        if self.config.kill_switch:
            add("11_emergency_kill_switch", False, "kill switch is active")
            for name in ["01_position_size", "02_max_daily_loss", "03_max_drawdown",
                         "04_exposure_limit", "05_leverage_limit", "06_stop_loss_validation",
                         "07_take_profit_validation", "08_correlation_exposure",
                         "09_portfolio_exposure", "10_trading_session_rules"]:
                add(name, False, "skipped: kill switch active")
            return RiskResult(order_id=order.order_id, rules=[r.__dict__ for r in rules])

        # 1. Position Size
        add("01_position_size", order.size <= self.config.max_position_size,
            f"size={order.size} limit={self.config.max_position_size}")

        # 2. Max Daily Loss
        add("02_max_daily_loss", portfolio.daily_pnl > -abs(self.config.max_daily_loss),
            f"daily_pnl={portfolio.daily_pnl} limit={-abs(self.config.max_daily_loss)}")

        # 3. Max Drawdown
        add("03_max_drawdown", portfolio.drawdown <= self.config.max_drawdown,
            f"drawdown={portfolio.drawdown} limit={self.config.max_drawdown}")

        # 4. Exposure Limit
        prospective_exposure = portfolio.total_exposure + order.size
        add("04_exposure_limit", prospective_exposure <= self.config.exposure_limit,
            f"prospective_exposure={prospective_exposure} limit={self.config.exposure_limit}")

        # 5. Leverage Limit
        add("05_leverage_limit", portfolio.leverage <= self.config.leverage_limit,
            f"leverage={portfolio.leverage} limit={self.config.leverage_limit}")

        # 6. Stop Loss Validation
        sl_ok = (not self.config.require_stop_loss) or order.sl > 0
        add("06_stop_loss_validation", sl_ok, f"sl={order.sl} required={self.config.require_stop_loss}")

        # 7. Take Profit Validation
        tp_ok = (not self.config.require_take_profit) or order.tp > 0
        add("07_take_profit_validation", tp_ok, f"tp={order.tp} required={self.config.require_take_profit}")

        # 8. Correlation Exposure
        add("08_correlation_exposure", portfolio.correlated_exposure <= self.config.max_correlation,
            f"correlated_exposure={portfolio.correlated_exposure} limit={self.config.max_correlation}")

        # 9. Portfolio Exposure
        add("09_portfolio_exposure", prospective_exposure <= self.config.max_portfolio_exposure,
            f"prospective_exposure={prospective_exposure} limit={self.config.max_portfolio_exposure}")

        # 10. Trading Session Rules
        session_ok = _in_trading_session(self.config.trading_sessions, now)
        add("10_trading_session_rules", session_ok, f"time={now.strftime('%H:%M')} sessions={self.config.trading_sessions}")

        # 11. Emergency Kill Switch — checked again at the end (belt-and-braces; P-05).
        add("11_emergency_kill_switch", not self.config.kill_switch, "kill switch inactive")

        return RiskResult(order_id=order.order_id, rules=[r.__dict__ for r in rules])
