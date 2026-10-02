import datetime as dt

from xir_trader.core.config import RiskConfig
from xir_trader.core.schemas import ExecutionOrder
from xir_trader.services.risk_engine import RiskEngine, PortfolioSnapshot


def _order(**kw):
    defaults = dict(side="BUY", instrument="EURUSD", size=50.0, sl=1.0, tp=1.0, cycle_id="c1")
    defaults.update(kw)
    return ExecutionOrder(**defaults)


def _portfolio(**kw):
    defaults = dict(equity=10000, daily_pnl=0.0, drawdown=0.0, open_positions={},
                     total_exposure=0.0, leverage=1.0, correlated_exposure=0.0)
    defaults.update(kw)
    return PortfolioSnapshot(**defaults)


def test_all_12_rules_present_in_order():
    engine = RiskEngine(RiskConfig())
    result = engine.check(_order(), _portfolio(), execution_facts={"bid": 99.9, "ask": 100.1,
                                                                   "bid_size": 10, "ask_size": 10})
    names = [r["rule"] for r in result.rules]
    assert names == [
        "01_position_size", "02_max_daily_loss", "03_max_drawdown", "04_exposure_limit",
        "05_leverage_limit", "06_stop_loss_validation", "07_take_profit_validation",
        "08_correlation_exposure", "09_portfolio_exposure", "10_trading_session_rules",
        "11_liquidity_feasibility", "12_emergency_kill_switch",
    ]


def test_pass_within_all_limits():
    engine = RiskEngine(RiskConfig())
    result = engine.check(_order(), _portfolio(), now=dt.datetime(2026, 1, 1, 12, 0),
                          execution_facts={"bid": 99.9, "ask": 100.1, "bid_size": 10, "ask_size": 10})
    assert result.passed


def test_position_size_rejected():
    cfg = RiskConfig(max_position_size=10.0)
    engine = RiskEngine(cfg)
    result = engine.check(_order(size=50.0), _portfolio(), execution_facts={"bid": 99.9, "ask": 100.1,
                                                                            "bid_size": 10, "ask_size": 10})
    assert not result.passed
    assert result.rules[0]["rule"] == "01_position_size"
    assert not result.rules[0]["passed"]


def test_missing_stop_loss_rejected_when_required():
    cfg = RiskConfig(require_stop_loss=True)
    engine = RiskEngine(cfg)
    result = engine.check(_order(sl=0.0), _portfolio(), execution_facts={"bid": 99.9, "ask": 100.1,
                                                                          "bid_size": 10, "ask_size": 10})
    assert not result.passed


def test_kill_switch_rejects_everything_and_is_first():
    cfg = RiskConfig(kill_switch=True)
    engine = RiskEngine(cfg)
    result = engine.check(_order(), _portfolio())
    assert not result.passed
    assert result.rules[0]["rule"] == "12_emergency_kill_switch"
    assert not result.rules[0]["passed"]
    # every other rule short-circuits to failed too
    assert all(not r["passed"] for r in result.rules)


def test_max_daily_loss_rejected():
    cfg = RiskConfig(max_daily_loss=100.0)
    engine = RiskEngine(cfg)
    result = engine.check(_order(), _portfolio(daily_pnl=-150.0), execution_facts={"bid": 99.9, "ask": 100.1,
                                                                                  "bid_size": 10, "ask_size": 10})
    assert not result.passed


def test_trading_session_rejects_outside_window():
    cfg = RiskConfig(trading_sessions=("09:00-17:00",))
    engine = RiskEngine(cfg)
    result = engine.check(_order(), _portfolio(), now=dt.datetime(2026, 1, 1, 3, 0))
    assert not result.passed


def test_nan_infinite_and_missing_correlation_or_liquidity_fail_closed():
    import math
    engine = RiskEngine(RiskConfig())
    result = engine.check(_order(size=math.nan), _portfolio(correlated_exposure=None), execution_facts=None)
    assert not result.passed
    failed = {row["rule"] for row in result.rules if not row["passed"]}
    assert {"01_position_size", "08_correlation_exposure", "11_liquidity_feasibility"} <= failed


def test_maximum_spread_is_configurable_and_machine_readable():
    engine = RiskEngine(RiskConfig(max_spread=0.01))
    result = engine.check(_order(), _portfolio(), execution_facts={"bid": 99.0, "ask": 101.0,
                                                                   "bid_size": 1, "ask_size": 1})
    rule = next(row for row in result.rules if row["rule"] == "11_liquidity_feasibility")
    assert not rule["passed"]
    assert rule["observed"] == 2.0 and rule["limit"] == 0.01
