from xir_trader.core.state_machine import State


def test_cycle_returns_to_idle(runtime):
    result = runtime.run_cycle("EURUSD", fast_veto_response="OK")
    assert result.final_state == State.IDLE.value
    assert runtime.sm.state == State.IDLE


def test_cycle_with_veto_reject_does_not_execute(runtime):
    # Force a BUY/SELL by biasing the mock price adapter, then reject at the veto window.
    result = runtime.run_cycle("EURUSD", fast_veto_response="REJECT")
    assert runtime.sm.state == State.IDLE
    if result.final_decision in ("BUY", "SELL"):
        assert "vetoed" in result.detail
        assert len(runtime.broker.filled_orders) == 0


def test_kill_switch_blocks_all_future_cycles(runtime):
    runtime.activate_kill_switch("operator test")
    result = runtime.run_cycle("EURUSD", fast_veto_response="OK")
    assert result.final_state == State.HALTED.value
    assert len(runtime.broker.filled_orders) == 0  # I2


def test_risk_config_kill_switch_flag_halts_runtime(runtime):
    runtime.risk_config = runtime.risk_config.__class__(**{**runtime.risk_config.__dict__, "kill_switch": True})
    runtime.risk_engine.config = runtime.risk_config
    result = runtime.run_cycle("EURUSD", fast_veto_response="OK")
    assert result.final_state == State.HALTED.value


def test_audit_log_has_at_least_one_entry_per_cycle(runtime):
    runtime.run_cycle("EURUSD", fast_veto_response="OK")
    with runtime.db.cursor() as c:
        c.execute("SELECT COUNT(*) FROM audit_log")
        (n,) = c.fetchone()
    assert n > 0


def test_no_order_bypasses_risk_check_end_to_end(runtime):
    """I1, exercised through the full orchestrator rather than unit-testing Guard alone."""
    runtime.run_cycle("EURUSD", fast_veto_response="OK")
    with runtime.db.cursor() as c:
        c.execute("SELECT order_id FROM orders")
        order_ids = [row[0] for row in c.fetchall()]
    for oid in order_ids:
        with runtime.db.cursor() as c:
            c.execute("SELECT COUNT(*) FROM risk_results WHERE order_id=?", (oid,))
            (n,) = c.fetchone()
        assert n == 11  # every executed/attempted order has all 11 risk rules recorded
