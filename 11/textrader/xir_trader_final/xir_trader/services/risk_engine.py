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
import hashlib
import hmac
import json
import math
import secrets
from dataclasses import dataclass

from ..core.config import RiskConfig
from ..core.schemas import ExecutionOrder, RiskResult, RiskRuleResult


@dataclass
class PortfolioSnapshot:
    equity: float
    daily_pnl: float
    drawdown: float | None          # fraction, e.g. 0.05 = 5%
    open_positions: dict            # instrument -> {size, correlation_group}
    total_exposure: float
    leverage: float | None
    correlated_exposure: float | None = None


def _in_trading_session(sessions: tuple, now: dt.datetime) -> bool:
    if now.tzinfo is None:
        now = now.replace(tzinfo=dt.timezone.utc)
    else:
        now = now.astimezone(dt.timezone.utc)
    hm = now.strftime("%H:%M")
    for window in sessions:
        start, end = window.split("-", 1)
        if (start <= hm <= end) if start <= end else (hm >= start or hm <= end):
            return True
    return False


class RiskEngine:
    def __init__(self, config: RiskConfig):
        self.config = config  # read-only reference; agents never get a mutable handle to this
        self._authorization_key = secrets.token_bytes(32)

    @staticmethod
    def _order_facts(order: ExecutionOrder) -> dict:
        return {name: getattr(order, name, None) for name in
                ("order_id", "idempotency_key", "cycle_id", "side", "instrument", "size", "sl", "tp")}

    def _authorize(self, order: ExecutionOrder, rules: list[dict]) -> RiskResult:
        """Seal a risk result to this engine instance, exact order, and full rule output."""
        facts = {"order": self._order_facts(order), "rules": rules}
        body = json.dumps(facts, sort_keys=True, separators=(",", ":"), default=str).encode()
        authorization = hmac.new(self._authorization_key, body, hashlib.sha256).hexdigest()
        return RiskResult(order_id=getattr(order, "order_id", "INVALID"), rules=rules,
                          authorization=authorization)

    def verify_authorization(self, order: ExecutionOrder, result: RiskResult | None) -> bool:
        """Reject fabricated, modified, incomplete, duplicated, or stale risk results."""
        expected = {
            "01_position_size", "02_max_daily_loss", "03_max_drawdown", "04_exposure_limit",
            "05_leverage_limit", "06_stop_loss_validation", "07_take_profit_validation",
            "08_correlation_exposure", "09_portfolio_exposure", "10_trading_session_rules",
            "11_liquidity_feasibility", "12_emergency_kill_switch",
        }
        if not isinstance(result, RiskResult) or result.order_id != getattr(order, "order_id", None):
            return False
        try:
            rules = [r if isinstance(r, dict) else r.__dict__ for r in result.rules]
            names = [r.get("rule") for r in rules]
            if len(names) != len(expected) or set(names) != expected:
                return False
            if not all(isinstance(r.get("passed"), bool) and isinstance(r.get("reason"), str) for r in rules):
                return False
            if not result.passed or not isinstance(result.authorization, str):
                return False
            facts = {"order": self._order_facts(order), "rules": rules}
            body = json.dumps(facts, sort_keys=True, separators=(",", ":"), default=str).encode()
            expected_authorization = hmac.new(self._authorization_key, body, hashlib.sha256).hexdigest()
            return hmac.compare_digest(result.authorization, expected_authorization)
        except (TypeError, ValueError, AttributeError):
            return False

    def check(self, order: ExecutionOrder, portfolio: PortfolioSnapshot,
              now: dt.datetime | None = None, execution_facts: dict | None = None) -> RiskResult:
        now = now or dt.datetime.now(dt.timezone.utc)
        rules: list[RiskRuleResult] = []

        def add(name: str, passed: bool, reason: str, observed=None, limit=None):
            rules.append(RiskRuleResult(rule=name, passed=bool(passed), reason=reason,
                                        observed=observed, limit=limit))

        def finite(value) -> bool:
            return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)

        try:
            order.validate()
            order_ok = True
        except Exception:
            order_ok = False
        order_size_value = getattr(order, "size", None)
        order_sl_value = getattr(order, "sl", None)
        order_tp_value = getattr(order, "tp", None)
        raw_equity = getattr(portfolio, "equity", None)
        raw_daily_pnl = getattr(portfolio, "daily_pnl", None)
        raw_drawdown = getattr(portfolio, "drawdown", None)
        raw_total_exposure = getattr(portfolio, "total_exposure", None)
        raw_leverage = getattr(portfolio, "leverage", None)
        raw_correlated_exposure = getattr(portfolio, "correlated_exposure", None)
        p_open_positions = getattr(portfolio, "open_positions", None)
        portfolio_values = (raw_equity, raw_daily_pnl, raw_drawdown, raw_total_exposure,
                            raw_leverage, raw_correlated_exposure)
        portfolio_ok = all(finite(value) for value in portfolio_values)
        portfolio_ok = portfolio_ok and isinstance(p_open_positions, dict)
        p_equity = float(raw_equity) if finite(raw_equity) else 0.0
        p_daily_pnl = float(raw_daily_pnl) if finite(raw_daily_pnl) else 0.0
        p_drawdown = float(raw_drawdown) if finite(raw_drawdown) else -1.0
        p_total_exposure = float(raw_total_exposure) if finite(raw_total_exposure) else -1.0
        p_leverage = float(raw_leverage) if finite(raw_leverage) else -1.0
        p_correlated_exposure = float(raw_correlated_exposure) if finite(raw_correlated_exposure) else -1.0
        order_size = float(order_size_value) if finite(order_size_value) else 0.0

        # 11. Emergency Kill Switch is checked FIRST (absolute priority, P-05) —
        # if active, every other rule is short-circuited to "fail".
        if self.config.kill_switch:
            add("12_emergency_kill_switch", False, "kill switch is active", True, False)
            for name in ["01_position_size", "02_max_daily_loss", "03_max_drawdown",
                         "04_exposure_limit", "05_leverage_limit", "06_stop_loss_validation",
                         "07_take_profit_validation", "08_correlation_exposure",
                          "09_portfolio_exposure", "10_trading_session_rules", "11_liquidity_feasibility"]:
                add(name, False, "skipped: kill switch active")
            return self._authorize(order, [r.__dict__ for r in rules])

        # 1. Position Size
        add("01_position_size", order_ok and order_size <= self.config.max_position_size,
            f"size={order_size_value} limit={self.config.max_position_size}", order_size_value, self.config.max_position_size)

        # 2. Max Daily Loss
        daily_limit = -abs(self.config.max_daily_loss)
        add("02_max_daily_loss", portfolio_ok and p_daily_pnl > daily_limit,
            f"daily_pnl={p_daily_pnl} must be greater than {daily_limit}", p_daily_pnl, daily_limit)

        # 3. Max Drawdown
        add("03_max_drawdown", portfolio_ok and 0 <= p_drawdown <= self.config.max_drawdown,
            f"drawdown={p_drawdown} limit={self.config.max_drawdown}", p_drawdown, self.config.max_drawdown)

        # 4. Exposure Limit
        prospective_exposure = p_total_exposure + order_size if portfolio_ok and order_ok else math.inf
        add("04_exposure_limit", portfolio_ok and order_ok and p_total_exposure >= 0 and prospective_exposure <= self.config.exposure_limit,
            f"prospective_exposure={prospective_exposure} limit={self.config.exposure_limit}", prospective_exposure, self.config.exposure_limit)

        # 5. Leverage Limit
        add("05_leverage_limit", portfolio_ok and p_equity > 0 and 0 <= p_leverage <= self.config.leverage_limit,
            f"leverage={p_leverage} limit={self.config.leverage_limit}", p_leverage, self.config.leverage_limit)

        # 6. Stop Loss Validation
        sl_ok = order_ok and ((not self.config.require_stop_loss) or (finite(order_sl_value) and order_sl_value > 0))
        add("06_stop_loss_validation", sl_ok, f"sl={order_sl_value} required={self.config.require_stop_loss}", order_sl_value, "positive" if self.config.require_stop_loss else None)

        # 7. Take Profit Validation
        tp_ok = order_ok and ((not self.config.require_take_profit) or (finite(order_tp_value) and order_tp_value > 0))
        add("07_take_profit_validation", tp_ok, f"tp={order_tp_value} required={self.config.require_take_profit}", order_tp_value, "positive" if self.config.require_take_profit else None)

        # 8. Correlation Exposure
        add("08_correlation_exposure", portfolio_ok and 0 <= p_correlated_exposure <= self.config.max_correlation,
            f"correlated_exposure={p_correlated_exposure} limit={self.config.max_correlation}", p_correlated_exposure, self.config.max_correlation)

        # 9. Portfolio Exposure
        add("09_portfolio_exposure", portfolio_ok and order_ok and p_total_exposure >= 0 and prospective_exposure <= self.config.max_portfolio_exposure,
            f"prospective_exposure={prospective_exposure} limit={self.config.max_portfolio_exposure}", prospective_exposure, self.config.max_portfolio_exposure)

        # 10. Trading Session Rules
        try:
            session_ok = _in_trading_session(self.config.trading_sessions, now)
            session_reason = f"time={now.isoformat()} sessions={self.config.trading_sessions}"
        except Exception as exc:
            session_ok = False
            session_reason = f"invalid session/time input: {type(exc).__name__}"
        add("10_trading_session_rules", session_ok, session_reason, now.isoformat() if isinstance(now, dt.datetime) else str(now), self.config.trading_sessions)

        # 11. Liquidity / execution feasibility. Threshold is owner-configured;
        # absent quotes fail closed when liquidity data is required.
        raw_bid = execution_facts.get("bid") if isinstance(execution_facts, dict) else None
        raw_ask = execution_facts.get("ask") if isinstance(execution_facts, dict) else None
        bid_size = execution_facts.get("bid_size") if isinstance(execution_facts, dict) else None
        ask_size = execution_facts.get("ask_size") if isinstance(execution_facts, dict) else None
        quote_valid = all(finite(v) and v > 0 for v in (raw_bid, raw_ask, bid_size, ask_size))
        bid = float(raw_bid) if finite(raw_bid) else 0.0
        ask = float(raw_ask) if finite(raw_ask) else 0.0
        quote_valid = quote_valid and ask >= bid
        spread = ask - bid if quote_valid else None
        liquidity_ok = (not self.config.require_liquidity_data or quote_valid)
        if self.config.max_spread is not None:
            liquidity_ok = liquidity_ok and quote_valid and spread is not None and spread <= self.config.max_spread
        add("11_liquidity_feasibility", liquidity_ok,
            f"quote_valid={quote_valid} spread={spread} max_spread={self.config.max_spread}",
            spread, self.config.max_spread)

        # 12. Emergency Kill Switch final enforcement check (P-05).
        add("12_emergency_kill_switch", not self.config.kill_switch, "kill switch inactive",
            self.config.kill_switch, False)

        return self._authorize(order, [r.__dict__ for r in rules])
