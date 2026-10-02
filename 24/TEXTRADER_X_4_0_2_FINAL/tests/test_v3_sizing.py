from trader.services.position_sizer import size_position
from trader.services.super_agent import synthesize
from trader.core.schemas import InitialDecision, FailureReport, Context, ContextSection, FailurePath


def test_position_sizing_respects_risk_budget():
    s = size_position(equity=100_000, price=100, stop_price=99,
                      risk_fraction=0.005, max_exposure_fraction=0.10,
                      max_position_size=10_000, fee_fraction=0, slippage_fraction=0)
    assert s.quantity > 0
    assert s.risk_amount <= 500.000001
    assert s.notional <= 10_000.000001


def test_super_agent_blocks_confidence_on_blocking_failure():
    ctx = Context(cycle_id="c", sections=(ContextSection("market_data", "test", "1", {
        "bundles": [{"payload": {"instrument": "BTC/USDT", "ohlcv": {"open": 100, "high": 102, "low": 99, "close": 101}}}]
    }),))
    initial = InitialDecision("c", "BUY", "BTC/USDT", "momentum")
    report = FailureReport("c", (FailurePath("missing_data", "feed unavailable", "blocking"),))
    thesis = synthesize(initial, report, ctx)
    assert thesis.confidence == 0.0
