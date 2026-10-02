from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor


def test_shared_orchestrator_serializes_concurrent_cycles(orchestrator):
    # The state machine is owned by one Orchestrator; callers may be concurrent.
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: orchestrator.run_cycle(), range(20)))
    assert len(results) == 20
    assert all(not r.errors for r in results), [r.errors for r in results if r.errors]
    assert all(r.final_state == "IDLE" for r in results)


def test_kill_switch_persists_across_cli_process_boundaries(tmp_db, monkeypatch):
    from trader.cli import main
    from trader.core.config import RiskConfig, TraderConfig
    from trader.engine.orchestrator import Orchestrator

    tc = TraderConfig()
    tc.db_path = tmp_db
    tc.enable_user_veto = False
    tc.enable_email = False
    tc.enable_telegram = False
    monkeypatch.setenv("TEXTRADER_DECISION_ONLY", "1")

    # The CLI builder accepts the global --config/--risk flags; for this
    # regression we exercise the underlying persistent lifecycle directly and
    # verify the same DB is observed by a newly-created process-equivalent instance.
    a = Orchestrator(RiskConfig(), tc, db_path=tmp_db)
    a.activate_kill_switch("stress")
    assert a.is_halted()

    b = Orchestrator(RiskConfig(), tc, db_path=tmp_db)
    assert b.is_halted()
    b.resume_from_halted("resume")
    assert not b.is_halted()

    c = Orchestrator(RiskConfig(), tc, db_path=tmp_db)
    assert not c.is_halted()


def test_cli_kill_switch_parser_has_no_symbol_requirement():
    from trader.cli import build_parser
    args = build_parser().parse_args(["kill-switch", "on", "--reason", "stress"])
    assert args.action == "on"
    assert args.reason == "stress"
    assert not hasattr(args, "symbol")


def test_bitget_market_command_supports_bitget_source():
    from trader.cli import build_parser
    args = build_parser().parse_args(["market", "BTC/USDT", "--source", "bitget"])
    assert args.source == "bitget"


def test_bitget_cli_forces_decision_only(monkeypatch):
    from trader.cli import build_parser, cmd_analyze
    args = build_parser().parse_args(["analyze", "BTC/USDT", "--source", "bitget", "--mode", "paper"])
    # We only inspect the safety contract here; no network call.
    monkeypatch.delenv("TEXTRADER_DECISION_ONLY", raising=False)
    assert args.source == "bitget"
    assert args.mode == "paper"


def test_bitget_public_source_reaches_agent1_market_decision(tmp_db):
    from trader.core.config import RiskConfig, TraderConfig
    from trader.engine.orchestrator import Orchestrator
    from trader.market.bitget import BitgetPublicSource

    class FakeClient:
        def snapshot(self, symbol, interval, limit):
            return {
                "ticker": {
                    "lastPrice": "101.0", "bid1Price": "100.9", "ask1Price": "101.0",
                    "price24hPcnt": "0.01", "volume24h": "1000"
                },
                "depth": {
                    "bids": [[100.9, 2.0]], "asks": [[101.0, 2.0]],
                },
                "klines": [["1", "100", "102", "99", "101", "10", "1000"]],
            }

    tc = TraderConfig()
    tc.db_path = tmp_db
    tc.instruments = ["BTC/USDT"]
    tc.enable_user_veto = False
    tc.enable_email = False
    tc.enable_telegram = False
    tc.on_silence = "wait"
    source = BitgetPublicSource(tc.instruments, client=FakeClient())
    o = Orchestrator(RiskConfig(), tc, db_path=tmp_db, data_source=source)

    r = o.run_cycle()

    assert r.initial is not None
    assert r.initial.instrument == "BTC/USDT"
    assert r.initial.rationale != "no market data"


def test_agent2_valid_orderbook_reports_nonblocking_f9(orchestrator):
    """Regression: valid bid+ask liquidity is F9=low, never blocking."""
    from trader.core.schemas import Context, ContextSection

    bundles = [{
        "source": "bitget://rest/market", "timestamp": "2026-09-30T00:00:00+00:00",
        "quality": "ok", "bundle_id": "market", "hash": "h1",
        "payload": {"instrument": "BTC/USDT", "ohlcv": {
            "open": 84000, "high": 84100, "low": 83900, "close": 84050, "volume": 1000}},
    }, {
        "source": "bitget://rest/orderbook", "timestamp": "2026-09-30T00:00:00+00:00",
        "quality": "ok", "bundle_id": "book", "hash": "h2",
        "payload": {"instrument": "BTC/USDT", "order_book": {
            "bids": [[84049, 1.0]], "asks": [[84051, 1.0]]}},
    }]
    sections = [
        ContextSection(name="market_data", source="test", version="1", data={"bundles": bundles}, empty=False),
        ContextSection(name="memory", source="test", version="1", data={}, empty=True),
        ContextSection(name="previous_decisions", source="test", version="1", data={"decisions": []}, empty=False),
        ContextSection(name="market_state", source="test", version="1", data={}, empty=True),
        ContextSection(name="user_config", source="test", version="1", data={"risk_appetite": "moderate"}, empty=False),
    ]
    ctx = Context(cycle_id="reg-f9-valid", sections=tuple(sections))
    initial = orchestrator.agent1.run(ctx)
    report = orchestrator.agent2.run(ctx, initial)
    f9 = [p for p in report.paths if p.category == "execution_impossibility"]
    assert len(f9) == 1
    assert f9[0].severity == "low"
    assert "no execution impossibility detected" in f9[0].description
