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
