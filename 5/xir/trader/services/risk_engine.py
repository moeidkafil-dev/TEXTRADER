"""
Risk Engine — chapter 07 (n14) / REQ-RSK-01..REQ-RSK-12.

11 deterministic rules in graph order:
  1. Position Size          (n14::n10)
  2. Max Daily Loss         (n14::n11)
  3. Max Drawdown           (n14::n12)
  4. Exposure Limit         (n14::n13)
  5. Leverage Limit         (n14::n14)
  6. Stop Loss Validation   (n14::n15)
  7. Take Profit Validation (n14::n16)
  8. Correlation Exposure   (n14::n17)
  9. Portfolio Exposure     (n14::n18)
 10. Trading Session Rules  (n14::n19)
 11. Emergency Kill Switch   (n14::n20)  — absolute priority (P-05)

Two phases per the graph (OI-03):
  - Phase A: Agent 3 → Risk Engine (rules 1..11) — pre-Decision-Engine.
    In this runtime, Agent 3 doesn't issue orders directly; Phase A is
    exercised at orchestrator level BEFORE Decision Engine builds the order
    by passing the FinalDecision through `pre_check()` — but the formal
    numeric checks need an ExecutionOrder, so Phase A is effectively a
    no-op signal here.
  - Phase B (the formal one): Decision Engine → Decision Validator →
    Risk Engine (final_check) → Execution Guard → Broker → Final Tools.
    `final_check(order, portfolio_state)` runs all 11 rules and returns
    a RiskResult. Reject ⇒ orchestrator goes to WAITING.

All rules are deterministic numeric checks (REQ-P-03); no LLM is consulted.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from trader.core.schemas import (
    ExecutionOrder, RiskResult, RuleResult,
)
from trader.core.config import RiskConfig
from trader.core.util import in_session


class RiskEngine:
    def __init__(self, config: RiskConfig, observability=None,
                 kill_switch=None):
        self.cfg = config
        self._obs = observability
        self._kill = kill_switch

    # Phase A: Agent3 → Risk Engine (rules 1..11)
    def pre_check(self, decision_action: str) -> RiskResult:
        """Run rules that don't need an order (e.g., kill switch, session).
        Returns a RiskResult with .passed=False ⇒ orchestrator downgrades
        FinalDecision to WAIT before building an ExecutionOrder."""
        rules: list[RuleResult] = []
        # Rule 10: trading session
        ok_session = in_session(self.cfg.trading_sessions, datetime.now(timezone.utc))
        rules.append(RuleResult(rule="trading_sessions", passed=ok_session,
                                 reason="" if ok_session else "outside trading session"))
        # Rule 11: kill switch (absolute priority)
        ks_active = bool(self._kill and self._kill.is_active)
        rules.append(RuleResult(rule="kill_switch", passed=not ks_active,
                                 reason="kill_switch active" if ks_active else ""))
        passed = all(r.passed for r in rules)
        if self._obs:
            self._obs.info("risk_engine.pre_check", trace_id="pre",
                            data={"passed": passed, "rules": [r.rule for r in rules]})
        return RiskResult(order_id="pre", rules=tuple(rules), passed=passed)

    # Phase B: post-Validator final check
    def final_check(self, order: ExecutionOrder,
                    portfolio: dict,
                    equity: float = 100_000.0,
                    peak_equity: float = 100_000.0,
                    daily_loss: float = 0.0,
                    positions_exposure: float = 0.0,
                    correlations: Optional[dict[str, float]] = None) -> RiskResult:
        rules: list[RuleResult] = []
        notional = order.size * 100.0  # synthetic: 1 unit = 100 notional (paper)
        # Kill switch first — absolute priority
        if self._kill and self._kill.is_active:
            rules.append(RuleResult(rule="kill_switch", passed=False,
                                      reason="kill_switch active (absolute priority)"))
            self._log_final(order, rules, False)
            return RiskResult(order_id=order.order_id, rules=tuple(rules), passed=False)
        # 1. Position Size
        ok = order.size <= self.cfg.max_position_size
        rules.append(RuleResult(rule="position_size", passed=ok,
                                  reason="" if ok else
                                  f"size {order.size} > max {self.cfg.max_position_size}"))
        # 2. Max Daily Loss
        ok = daily_loss <= self.cfg.max_daily_loss
        rules.append(RuleResult(rule="max_daily_loss", passed=ok,
                                  reason="" if ok else
                                  f"daily_loss {daily_loss:.4f} > max {self.cfg.max_daily_loss}"))
        # 3. Max Drawdown
        dd = (peak_equity - equity) / max(peak_equity, 1e-9)
        ok = dd <= self.cfg.max_drawdown
        rules.append(RuleResult(rule="max_drawdown", passed=ok,
                                  reason="" if ok else
                                  f"drawdown {dd:.4f} > max {self.cfg.max_drawdown}"))
        # 4. Exposure Limit (single order)
        order_exposure = notional / max(equity, 1e-9)
        ok = order_exposure <= self.cfg.exposure_limit
        rules.append(RuleResult(rule="exposure_limit", passed=ok,
                                  reason="" if ok else
                                  f"order exposure {order_exposure:.4f} > max {self.cfg.exposure_limit}"))
        # 5. Leverage Limit (assume no margin here; notional/equity <= leverage_limit)
        lev = notional / max(equity, 1e-9)
        ok = lev <= self.cfg.leverage_limit
        rules.append(RuleResult(rule="leverage_limit", passed=ok,
                                  reason="" if ok else
                                  f"leverage {lev:.4f} > max {self.cfg.leverage_limit}"))
        # 6. Stop Loss Validation
        ok = (not self.cfg.require_stop_loss) or order.sl > 0
        rules.append(RuleResult(rule="stop_loss_validation", passed=ok,
                                  reason="" if ok else "stop loss required"))
        # 7. Take Profit Validation
        ok = (not self.cfg.require_take_profit) or order.tp > 0
        rules.append(RuleResult(rule="take_profit_validation", passed=ok,
                                  reason="" if ok else "take profit required"))
        # 8. Correlation Exposure (max pairwise correlation)
        max_corr = 0.0
        if correlations:
            max_corr = max(correlations.values()) if correlations else 0.0
        ok = max_corr <= self.cfg.max_correlation
        rules.append(RuleResult(rule="correlation_exposure", passed=ok,
                                  reason="" if ok else
                                  f"max correlation {max_corr:.4f} > {self.cfg.max_correlation}"))
        # 9. Portfolio Exposure
        new_total = positions_exposure + order_exposure
        ok = new_total <= self.cfg.max_portfolio_exposure
        rules.append(RuleResult(rule="portfolio_exposure", passed=ok,
                                  reason="" if ok else
                                  f"new total exposure {new_total:.4f} > {self.cfg.max_portfolio_exposure}"))
        # 10. Trading Session Rules
        ok_session = in_session(self.cfg.trading_sessions, datetime.now(timezone.utc))
        rules.append(RuleResult(rule="trading_sessions", passed=ok_session,
                                  reason="" if ok_session else "outside trading session"))
        # 11. Emergency Kill Switch (already checked at top; include in result for completeness)
        rules.append(RuleResult(rule="kill_switch", passed=True, reason=""))

        passed = all(r.passed for r in rules)
        self._log_final(order, rules, passed)
        return RiskResult(order_id=order.order_id, rules=tuple(rules), passed=passed)

    def _log_final(self, order: ExecutionOrder, rules: list[RuleResult], passed: bool) -> None:
        if not self._obs:
            return
        self._obs.info("risk_engine.final_check", trace_id=order.cycle_id,
                        data={"event": "final_check", "order_id": order.order_id,
                               "passed": passed,
                               "rejected": [r.rule for r in rules if not r.passed]})

    @staticmethod
    def rule_names() -> list[str]:
        return [
            "position_size", "max_daily_loss", "max_drawdown", "exposure_limit",
            "leverage_limit", "stop_loss_validation", "take_profit_validation",
            "correlation_exposure", "portfolio_exposure", "trading_sessions",
            "kill_switch",
        ]
