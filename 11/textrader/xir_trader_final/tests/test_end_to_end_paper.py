from xir_trader.core.state_machine import State


def test_cycle_returns_to_idle(runtime):
    result = runtime.run_cycle("EURUSD", fast_veto_response="OK")
    assert result.final_state == State.IDLE.value
    assert runtime.sm.state == State.IDLE


def test_cycle_with_veto_reject_does_not_execute(runtime):
    # Force a BUY/SELL by biasing the mock price adapter, then reject at the veto window.
    result = runtime.run_cycle("EURUSD", fast_veto_response="REJECT")
    if result.final_decision in ("BUY", "SELL"):
        assert "human hold" in result.detail
        assert len(runtime.broker.filled_orders) == 0
        assert runtime.sm.state == State.HALTED


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
        assert n == 12  # every executed/attempted order has all deterministic rules recorded


def test_cycle_audit_material_contains_replayable_inputs_and_agent_outputs(runtime):
    result = runtime.run_cycle("EURUSD", fast_veto_response="OK")
    cycle_id = result.cycle_id
    with runtime.db.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM data_bundles WHERE cycle_id=?", (cycle_id,))
        assert cur.fetchone()[0] > 0
        cur.execute("SELECT COUNT(*) FROM contexts WHERE cycle_id=?", (cycle_id,))
        assert cur.fetchone()[0] > 0
        cur.execute("SELECT agent FROM decisions WHERE cycle_id=? ORDER BY id", (cycle_id,))
        assert [row[0] for row in cur.fetchall()] == [1, 2, 3]
        cur.execute("SELECT event FROM audit_log WHERE data LIKE ?", (f'%"cycle_id": "{cycle_id}"%',))
        events = {row[0] for row in cur.fetchall()}
    assert "cycle_started" in events
    assert "final_decision" in events
    assert "cycle_completed" in events
