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


def test_web_dependencies_are_declared_in_pyproject():
    from pathlib import Path
    text = Path("pyproject.toml").read_text()
    assert '"fastapi>=0.115,<1.0"' in text
    assert '"uvicorn[standard]>=0.30,<1.0"' in text
    assert '"httpx>=0.27,<1.0"' in text
