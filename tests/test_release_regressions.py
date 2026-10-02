import pytest

from trader.core.config import RiskConfig, TraderConfig, validate_runtime_config
from trader.engine.orchestrator import Orchestrator
from trader.core.state_machine import State


def test_kill_switch_config_starts_halted(tmp_path):
    orch = Orchestrator(
        RiskConfig(kill_switch=True),
        TraderConfig(mode="paper", db_path=str(tmp_path / "ks.db")),
    )
    assert orch.is_halted()
    assert orch.sm.state == State.HALTED


def test_on_silence_wait_never_executes(tmp_path):
    tc = TraderConfig(mode="paper", on_silence="wait", db_path=str(tmp_path / "wait.db"))
    orch = Orchestrator(RiskConfig(), tc, user_veto_hook=lambda order: "SILENCE")
    result = orch.run_cycle()
    assert result.execution is None
    assert result.veto is not None
    assert result.veto.response == "WAIT"


def test_live_mode_is_fail_closed(monkeypatch):
    monkeypatch.delenv("TRADER_LIVE_ACK", raising=False)
    with pytest.raises(RuntimeError):
        validate_runtime_config(TraderConfig(mode="live"))


def test_invalid_runtime_config_rejected():
    with pytest.raises(ValueError):
        validate_runtime_config(TraderConfig(mode="paper", on_silence="maybe"))


def test_kill_switch_activating_after_guard_blocks_final_execution(tmp_path):
    from trader.core.schemas import ExecutionResult, OrderStatus
    tc = TraderConfig(mode="paper", db_path=str(tmp_path / "race.db"), enable_user_veto=False)
    orch = Orchestrator(RiskConfig(), tc, db_path=tc.db_path)
    original = orch.final_tools._broker.submit
    calls = {"n": 0}
    def submit(req):
        calls["n"] += 1
        return original(req)
    orch.final_tools._broker.submit = submit
    # Simulate a kill switch arriving after Guard approval but before FinalTools.
    orig_buy = orch.final_tools.buy_system
    def kill_then_buy(order):
        orch.activate_kill_switch("race-regression")
        return orig_buy(order)
    orch.final_tools.buy_system = kill_then_buy
    r = orch.run_cycle(cycle_id="kill-race")
    assert calls["n"] == 0
    assert r.execution is not None
    assert r.execution.status == OrderStatus.REJECTED.value
    assert "kill_switch" in r.execution.broker_ack


def test_orchestrator_serializes_concurrent_cycles(tmp_path):
    from concurrent.futures import ThreadPoolExecutor

    tc = TraderConfig(mode="paper", db_path=str(tmp_path / "concurrency.db"), enable_user_veto=False)
    orch = Orchestrator(RiskConfig(), tc, db_path=tc.db_path)

    def run(i):
        return orch.run_cycle(cycle_id=f"concurrent-{i}")

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(run, range(32)))

    assert len(results) == 32
    assert all(not r.errors for r in results)
    assert all(r.final_state == State.IDLE.value for r in results)


def test_kill_switch_persists_across_orchestrator_instances(tmp_path):
    db = str(tmp_path / "persistent-kill.db")
    tc = TraderConfig(mode="paper", db_path=db)

    first = Orchestrator(RiskConfig(), tc, db_path=db)
    first.activate_kill_switch("cli-test")

    second = Orchestrator(RiskConfig(), tc, db_path=db)
    assert second.is_halted()
    assert second.kill_switch.reason == "cli-test"
    assert second.run_cycle().errors == ["halted_at_start"]

    second.resume_from_halted("cli-test-resume")
    third = Orchestrator(RiskConfig(), tc, db_path=db)
    assert not third.is_halted()
    assert third.run_cycle().final_state == State.IDLE.value



def test_kill_switch_state_reconciles_between_live_orchestrators(tmp_path):
    db = str(tmp_path / "multi-instance-kill.db")
    tc = TraderConfig(mode="paper", db_path=db, enable_user_veto=False)

    first = Orchestrator(RiskConfig(), tc, db_path=db)
    second = Orchestrator(RiskConfig(), tc, db_path=db)

    first.activate_kill_switch("remote-stop")
    assert second.is_halted()
    assert second.kill_switch.reason == "remote-stop"
    assert second.run_cycle().errors == ["halted_at_start"]

    first.resume_from_halted("remote-resume")
    assert not second.is_halted()
    result = second.run_cycle()
    assert result.final_state == State.IDLE.value
    assert not result.errors


def test_kill_switch_activation_by_second_instance_blocks_first(tmp_path):
    db = str(tmp_path / "reverse-multi-instance-kill.db")
    tc = TraderConfig(mode="paper", db_path=db, enable_user_veto=False)

    first = Orchestrator(RiskConfig(), tc, db_path=db)
    second = Orchestrator(RiskConfig(), tc, db_path=db)

    second.activate_kill_switch("remote-stop")
    assert first.is_halted()
    assert first.run_cycle().errors == ["halted_at_start"]

def test_version_is_consistent():
    import tomllib
    from trader import __version__
    from trader.cli import build_parser
    from trader.web.server import create_app

    with open("pyproject.toml", "rb") as f:
        project_version = tomllib.load(f)["project"]["version"]

    assert __version__ == project_version == "4.0.2"
    assert create_app().version == project_version
    parser = build_parser()
    version_actions = [a for a in parser._actions if type(a).__name__ == "_VersionAction"]
    assert version_actions
    assert "4.0.2" in version_actions[0].version
