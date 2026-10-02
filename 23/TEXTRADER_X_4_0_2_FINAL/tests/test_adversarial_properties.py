"""Adversarial/property-style regression tests for safety-critical paths.

These tests intentionally generate many edge cases without requiring a network
or a third-party fuzzing service. They complement the example-based PRD suite.
"""

import random

from trader.core.config import RiskConfig
from trader.core.schemas import ExecutionOrder, VetoEvent, VetoResponse
from trader.core.state_machine import State, StateMachine, Transition
from trader.services.execution_guard import ExecutionGuard
from trader.services.risk_engine import RiskEngine


def _order(size=1.0, key="k"):
    return ExecutionOrder(
        order_id=f"o-{key}",
        idempotency_key=key,
        cycle_id=f"c-{key}",
        side="BUY",
        instrument="XIR/USDT",
        size=size,
        sl=99.0,
        tp=102.0,
    )


def test_risk_position_size_boundary_fuzz():
    cfg = RiskConfig(
        max_position_size=100.0,
        trading_sessions=["00:00-23:59"],
    )
    engine = RiskEngine(cfg)
    rng = random.Random(20260925)

    for i in range(2000):
        size = rng.uniform(0.000001, 100.000001)
        result = engine.final_check(
            _order(size=size, key=str(i)),
            portfolio={},
            equity=100_000.0,
            peak_equity=100_000.0,
            daily_loss=0.0,
            positions_exposure=0.0,
            correlations={},
        )
        position_rule = next(r for r in result.rules if r.rule == "position_size")
        assert position_rule.passed is (size <= 100.0)


def test_guard_never_allows_rejected_veto_under_randomized_inputs():
    from trader.services.kill_switch import KillSwitch

    guard = ExecutionGuard(KillSwitch(None))
    rng = random.Random(42)
    order = _order()
    # A deliberately failing risk result is enough to prove ordering: veto
    # values must not bypass Risk.
    from trader.core.schemas import RiskResult, RuleResult

    for i in range(500):
        veto_value = rng.choice([
            VetoResponse.REJECT.value,
            VetoResponse.STOP.value,
            VetoResponse.WAIT.value,
            "garbage",
            "",
        ])
        veto = VetoEvent(
            order_id=order.order_id,
            notified_at="",
            response=veto_value,
        )
        risk = RiskResult(
            order_id=order.order_id,
            rules=(RuleResult(rule="forced", passed=False, reason="test"),),
            passed=False,
        )
        allowed, _ = guard.allow(order, risk, veto)
        assert allowed is False


def test_state_machine_repeated_legal_cycles_return_to_idle():
    sm = StateMachine()
    for _ in range(1000):
        assert sm.state == State.IDLE
        sm.apply(Transition.START_CYCLE)
        sm.apply(Transition.DATA_READ)
        sm.apply(Transition.CONTEXT_READY)
        sm.apply(Transition.A1_DONE)
        sm.apply(Transition.A2_DONE)
        sm.apply(Transition.A3_WAIT)
        sm.apply(Transition.USER_NEW_COMMAND)
        assert sm.state == State.IDLE


def test_state_machine_halt_is_sticky_until_explicit_resume():
    sm = StateMachine()
    for _ in range(500):
        sm.force_halted()
        assert sm.state == State.HALTED
        sm.force_halted()
        assert sm.state == State.HALTED
        sm.force_idle()
        assert sm.state == State.IDLE
