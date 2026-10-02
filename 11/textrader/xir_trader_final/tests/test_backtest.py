import pytest

from xir_trader.services.backtest import (
    BacktestConfig,
    HistoricalBar,
    run_backtest,
    walk_forward_splits,
)


def bars(count=10):
    return [HistoricalBar(float(i), 100 + i, 102 + i, 99 + i, 101 + i, 1000) for i in range(count)]


def test_backtest_withholds_current_and_future_bars_from_signal():
    seen = []

    def signal(history):
        seen.append(len(history))
        return "WAIT"

    result = run_backtest(bars(5), signal)
    assert seen == [0, 1, 2, 3, 4]
    assert result["bars"] == 5
    assert result["trades"] == 0
    assert "not evidence" in result["performance_claim"]


def test_backtest_reports_costs_and_trade_statistics_without_profit_claim():
    result = run_backtest(
        bars(6), lambda history: "BUY" if len(history) == 1 else "WAIT",
        BacktestConfig(fee_bps=2, slippage_bps=1, spread_bps=2), synthetic=True,
    )
    assert result["synthetic"] is True
    assert result["fees_slippage_spread_cost"] > 0
    assert result["turnover"] > 0
    assert result["trades"] == 1
    assert result["win_rate"] == 1.0
    assert "not evidence" in result["performance_claim"]


def test_backtest_rejects_nonmonotonic_timestamps_and_invalid_bars():
    with pytest.raises(ValueError, match="increasing timestamps"):
        run_backtest([bars(2)[1], bars(2)[0]], lambda history: "WAIT")
    invalid = HistoricalBar(1, 100, float("nan"), 99, 100, 10)
    with pytest.raises(ValueError, match="finite"):
        run_backtest([invalid], lambda history: "WAIT")


def test_walk_forward_has_nonoverlapping_development_validation_and_test_periods():
    split = walk_forward_splits(bars(10), train_fraction=0.6, validation_fraction=0.2)
    assert [len(split[key]) for key in ("development", "validation", "unseen_test")] == [6, 2, 2]
    assert split["development"][-1].timestamp < split["validation"][0].timestamp
    assert split["validation"][-1].timestamp < split["unseen_test"][0].timestamp
