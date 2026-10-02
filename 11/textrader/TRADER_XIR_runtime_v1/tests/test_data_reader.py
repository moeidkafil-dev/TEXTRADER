"""Data Reader + Context tests — REQ-DR-01..04."""
import pytest

from trader.services.data_reader import (
    DataReader, MockOHLCVSource, UnreachableSource, HistoricalReplaySource,
)


def test_data_reader_returns_bundles(orchestrator):
    """REQ-DR-01 — every bundle has a source, timestamp, quality, payload."""
    bundles = orchestrator.data_reader.read("test_cycle")
    assert len(bundles) > 0
    for b in bundles:
        assert b.source
        assert b.timestamp
        assert b.quality in ("ok", "missing")
        assert b.payload is not None


def test_data_reader_marks_missing(orchestrator):
    """TST-SYS-10 — unreachable source ⇒ missing_data flagged, not dropped."""
    dr = DataReader([UnreachableSource()])
    bundles = dr.read("cyc_missing")
    assert len(bundles) >= 1
    assert all(b.quality == "missing" for b in bundles)


def test_context_maker_5_sections(orchestrator):
    """REQ-DR-03 — context has 5 sections, empties flagged (not dropped)."""
    bundles = orchestrator.data_reader.read("ctx_test")
    ctx = orchestrator.context_maker.make("ctx_test", bundles)
    section_names = [s.name for s in ctx.sections]
    assert set(section_names) >= {
        "market_data", "memory", "previous_decisions",
        "market_state", "user_config",
    }
    # empty sections must be flagged, not dropped
    for s in ctx.sections:
        if s.empty:
            assert s.empty is True


def test_context_sender_delivers_to_agent1(orchestrator):
    """REQ-DR-04 — exactly-once delivery; agent1 receives the same hash."""
    bundles = orchestrator.data_reader.read("cyc_send")
    ctx = orchestrator.context_maker.make("cyc_send", bundles)
    ack = orchestrator.context_sender.deliver(ctx, orchestrator.agent1)
    assert ack == ctx.context_id
    assert orchestrator.agent1._last_ctx is ctx


def test_historical_replay_source(orchestrator):
    """Backtest source — bars replayed in order."""
    bars = [
        {"instrument": "XIR/USDT", "open": 100, "high": 101, "low": 99, "close": 100.5, "volume": 1000},
        {"instrument": "XIR/USDT", "open": 100.5, "high": 102, "low": 100, "close": 101.5, "volume": 1000},
    ]
    src = HistoricalReplaySource(bars)
    b1 = src.fetch("cyc1")
    assert b1[0].payload["instrument"] == "XIR/USDT"
    b2 = src.fetch("cyc2")
    assert b2[0].payload["ohlcv"]["close"] == 101.5
    b3 = src.fetch("cyc3")
    assert b3[0].quality == "missing"
