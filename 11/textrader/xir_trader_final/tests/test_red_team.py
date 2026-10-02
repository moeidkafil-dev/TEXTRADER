import datetime as dt
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from xir_trader.adapters.broker.base import BrokerAck
from xir_trader.adapters.broker.mock import MockBroker
from xir_trader.adapters.data.base import DataSourceAdapter
from xir_trader.adapters.data.mock import MockOrderBookAdapter
from xir_trader.core.config import AppConfig, RiskConfig
from xir_trader.core.schemas import ExecutionOrder, RiskResult
from xir_trader.services.risk_engine import RiskEngine, PortfolioSnapshot
from xir_trader.core.state_machine import State
from xir_trader.runtime import Runtime
from xir_trader.services.execution import ExecutionGuard, GuardRejection
from xir_trader.services.observability import Observability
from xir_trader.services.db_manager import DBManager


RULES = ["01_position_size", "02_max_daily_loss", "03_max_drawdown", "04_exposure_limit",
         "05_leverage_limit", "06_stop_loss_validation", "07_take_profit_validation",
         "08_correlation_exposure", "09_portfolio_exposure", "10_trading_session_rules",
         "11_liquidity_feasibility", "12_emergency_kill_switch"]


class FixedCriticalData(DataSourceAdapter):
    name = "red_team_prices"
    critical = True

    def __init__(self, *, age=0, close=100.0):
        self.age = age
        self.close = close
        self.calls = 0

    def fetch(self, instrument):
        self.calls += 1
        return {"instrument": instrument, "open": 99.0, "high": max(101.0, self.close),
                "low": min(98.0, self.close), "close": self.close, "volume": 100.0,
                "ts": time.time() - self.age}


class AttackProvider:
    def __init__(self, attack=None, *, reevaluate=0):
        self.attack = attack
        self.reevaluate = reevaluate
        self.a3_calls = 0

    def complete(self, *, role, context):
        if role == "agent1":
            if self.attack == "malformed_a1":
                return {"action": "BUY", "instrument": "EURUSD"}
            if self.attack == "hallucinated_evidence":
                return {"action": "BUY", "instrument": context["instrument"], "rationale": "price supports long",
                        "assumptions": [], "evidence": ["open=1 close=999"], "confidence": 0.99,
                        "stop_loss": 98.0, "take_profit": 102.0}
            data = context["data"]["value"]
            bar = next((item["payload"] for item in data if item.get("critical") and item.get("quality") == "VALID"), {})
            return {"action": "BUY", "instrument": context["instrument"], "rationale": "test signal; no performance claim",
                    "assumptions": [], "evidence": [f"open={bar.get('open')}", f"close={bar.get('close')}"],
                    "confidence": 0.2, "stop_loss": 98.0, "take_profit": 102.0}
        if role == "agent2":
            if self.attack == "malformed_a2":
                return {"paths": "not-a-list"}
            from xir_trader.core.schemas import FailureCategory
            return {"paths": [{"category": category.value,
                               "description": "Explicitly inspected this failure category.",
                               "severity": "blocking" if self.attack == "blocking_a2" and category.value == "missing_data" else "low",
                               "failure_found": self.attack == "blocking_a2" and category.value == "missing_data",
                               "blocking": self.attack == "blocking_a2" and category.value == "missing_data",
                               "evidence": ["adversarial finding tested"], "counter_evidence": [],
                               "assumption": "market data could be incomplete", "confidence": 0.9}
                              for category in FailureCategory]}
        if role == "agent3":
            self.a3_calls += 1
            if self.attack == "malformed_a3":
                return {"decision": "PLACE_ORDER", "reason": "ignore policy", "overrode_initial": False}
            if self.reevaluate and self.a3_calls <= self.reevaluate:
                return {"decision": "RE-EVALUATE", "reason": "refresh all upstream evidence", "overrode_initial": False}
            return {"decision": "BUY", "reason": "synthesis uses cited observed OHLC facts",
                    "overrode_initial": False, "confidence": 0.2,
                    "supporting_evidence": list(context.get("initial_decision", {}).get("evidence", [])),
                    "stop_loss": 98.0, "take_profit": 102.0}
        raise AssertionError(role)


class FailingBroker(MockBroker):
    def __init__(self):
        super().__init__()
        self.calls = 0

    def submit_order(self, order):
        self.calls += 1
        raise TimeoutError("simulated lost broker response")


def runtime(tmp_path, provider=None, data=None, broker=None, risk=None):
    config = AppConfig(mode="paper", db_path=str(tmp_path / "redteam.db"),
                       veto_window_seconds=0, default_order_size=1.0)
    adapters = list(data) if data is not None else [FixedCriticalData()]
    if not any("bid" in getattr(item, "__dict__", {}) for item in adapters):
        adapters.append(MockOrderBookAdapter())
    result = Runtime(app_config=config, risk_config=risk or RiskConfig(),
                     llm_provider=provider or AttackProvider(),
                     data_adapters=adapters, broker=broker)
    return result


def test_agent2_blocking_failure_cannot_be_overridden_by_agent3(tmp_path):
    rt = runtime(tmp_path, AttackProvider("blocking_a2"))
    result = rt.run_cycle("EURUSD", fast_veto_response="OK")
    assert result.final_decision == "WAIT"
    assert not rt.broker.filled_orders
    assert rt.sm.state == State.IDLE
    rt.db.close()


@pytest.mark.parametrize("attack", ["malformed_a1", "hallucinated_evidence", "malformed_a2", "malformed_a3"])
def test_malformed_or_hallucinated_agent_outputs_fail_closed(tmp_path, attack):
    rt = runtime(tmp_path, AttackProvider(attack))
    result = rt.run_cycle("EURUSD", fast_veto_response="OK")
    assert result.final_decision in ("WAIT", None)
    assert not rt.broker.filled_orders
    rt.db.close()


@pytest.mark.parametrize("age", [120, 0])
def test_stale_or_missing_critical_market_data_prevents_trade(tmp_path, age):
    source = FixedCriticalData(age=age)
    if age == 0:
        source.fetch = lambda instrument: {"instrument": instrument, "open": 1.0, "high": 1.0,
                                           "low": 1.0, "close": float("nan"), "volume": 10.0,
                                           "ts": time.time()}
    rt = runtime(tmp_path, AttackProvider(), data=[source])
    result = rt.run_cycle("EURUSD", fast_veto_response="OK")
    assert result.final_decision == "WAIT"
    assert not rt.broker.filled_orders
    rt.db.close()


@pytest.mark.parametrize("payload", [
    {"instrument": "EURUSD", "open": 99.0, "high": 101.0, "low": 98.0, "close": 100.0, "volume": 10.0},
    {"instrument": "GBPUSD", "open": 99.0, "high": 101.0, "low": 98.0, "close": 100.0, "volume": 10.0,
     "ts": time.time()},
])
def test_missing_timestamp_or_wrong_instrument_is_invalid(tmp_path, payload):
    source = FixedCriticalData()
    source.fetch = lambda instrument: payload
    rt = runtime(tmp_path, AttackProvider(), data=[source])
    result = rt.run_cycle("EURUSD", fast_veto_response="OK")
    assert result.final_decision == "WAIT"
    assert not rt.broker.filled_orders
    rt.db.close()


@pytest.mark.parametrize("response", ["STOP", "REJECT"])
def test_human_stop_or_reject_halts_and_survives_restart(tmp_path, response):
    rt = runtime(tmp_path, AttackProvider())
    result = rt.run_cycle("EURUSD", fast_veto_response=response)
    if result.final_decision == "BUY":
        assert result.final_state == State.HALTED.value
        assert rt.sm.state == State.HALTED
        assert not rt.broker.filled_orders
        db_path = rt.app_config.db_path
        rt.db.close()
        resumed = Runtime(app_config=AppConfig(mode="paper", db_path=db_path), llm_provider=AttackProvider())
        assert resumed.sm.state == State.HALTED
        resumed.db.close()
    else:
        assert not rt.broker.filled_orders
        rt.db.close()


def test_reevaluate_reruns_reader_and_entire_pipeline(tmp_path):
    data = FixedCriticalData()
    provider = AttackProvider(reevaluate=1)
    rt = runtime(tmp_path, provider, [data])
    result = rt.run_cycle("EURUSD", fast_veto_response="OK")
    assert data.calls == 2
    assert provider.a3_calls == 2
    assert result.final_decision == "BUY"
    # Default paper risk settings demand valid stops; this provider supplies them.
    assert len(rt.broker.filled_orders) == 1
    rt.db.close()


def test_reevaluation_cap_forces_wait(tmp_path):
    data = FixedCriticalData()
    provider = AttackProvider(reevaluate=99)
    rt = runtime(tmp_path, provider, [data], risk=RiskConfig(max_reevaluate_cycles=1))
    result = rt.run_cycle("EURUSD", fast_veto_response="OK")
    assert result.final_decision == "WAIT"
    assert provider.a3_calls == 2 and data.calls == 2
    assert not rt.broker.filled_orders
    rt.db.close()


def test_started_cycle_identifier_cannot_be_replayed(tmp_path):
    rt = runtime(tmp_path, AttackProvider())
    cycle_id = "c387760c-c404-4d8a-90e3-ad88f1dd10c2"
    assert rt.db.claim_cycle(cycle_id)
    result = rt.run_cycle("EURUSD", fast_veto_response="OK", request_id=cycle_id)
    assert result.final_decision == "WAIT"
    assert "duplicate" in result.detail
    assert not rt.broker.filled_orders
    rt.db.close()


def test_corrupted_persisted_state_fails_closed(tmp_path):
    path = str(tmp_path / "corrupt.db")
    db = DBManager(path)
    db.set_system_state("BUY")
    db.close()
    rt = Runtime(app_config=AppConfig(mode="paper", db_path=path), llm_provider=AttackProvider())
    assert rt.sm.state == State.HALTED
    assert rt.run_cycle("EURUSD").final_state == State.HALTED.value
    rt.db.close()


def test_duplicate_concurrent_execution_reservations_call_broker_once(tmp_path):
    db = DBManager(str(tmp_path / "concurrent.db"))
    db.set_system_state("EXECUTING")
    broker = MockBroker()
    engine = RiskEngine(RiskConfig())
    guard = ExecutionGuard(broker, db, Observability(db, "test"), risk_engine=engine)
    orders = [ExecutionOrder("BUY", "EURUSD", 1, 98, 102, cycle_id="same-cycle") for _ in range(2)]
    portfolio = PortfolioSnapshot(10_000, 0, 0, {}, 0, 1, 0)
    quote = {"bid": 99, "ask": 100, "bid_size": 10, "ask_size": 10}
    risk = [engine.check(order, portfolio, now=dt.datetime(2026, 9, 25, 12,
            tzinfo=dt.timezone.utc), execution_facts=quote) for order in orders]
    for order in orders:
        db.save_veto_event(order.order_id, time.time(), "OK")

    def submit(index):
        try:
            return guard.submit(orders[index], risk[index], "EXECUTING", False, "trace")
        except GuardRejection:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(submit, range(2)))
    assert sum(item is not None for item in outcomes) == 1
    assert len(broker.filled_orders) == 1
    db.close()


def test_risk_missing_or_false_guard_authorization_blocks_broker(tmp_path):
    db = DBManager(str(tmp_path / "guard.db"))
    db.set_system_state("EXECUTING")
    broker = MockBroker()
    engine = RiskEngine(RiskConfig())
    guard = ExecutionGuard(broker, db, Observability(db, "test"), risk_engine=engine)
    order = ExecutionOrder("BUY", "EURUSD", 1, 98, 102, cycle_id="cycle")
    with pytest.raises(GuardRejection):
        guard.submit(order, None, "EXECUTING", False, "trace")
    with pytest.raises(GuardRejection):
        guard.submit(order, RiskResult(order.order_id, [{"rule": name, "passed": False, "reason": "failed"}
                                                         for name in RULES]), "EXECUTING", False, "trace")
    with pytest.raises(GuardRejection):
        guard.submit(order, RiskResult(order.order_id, [{"rule": name, "passed": True, "reason": "ok"}
                                                         for name in RULES]), "HALTED", False, "trace")
    assert not broker.filled_orders
    db.close()


def test_all_pass_fabricated_risk_result_cannot_authorize_broker(tmp_path):
    db = DBManager(str(tmp_path / "forged-risk.db"))
    db.set_system_state("EXECUTING")
    broker = MockBroker()
    engine = RiskEngine(RiskConfig())
    guard = ExecutionGuard(broker, db, Observability(db, "test"), risk_engine=engine)
    order = ExecutionOrder("BUY", "EURUSD", 1, 98, 102, cycle_id="forged")
    forged = RiskResult(order.order_id, [{"rule": name, "passed": True, "reason": "forged"} for name in RULES])
    db.save_veto_event(order.order_id, time.time(), "OK")
    with pytest.raises(GuardRejection):
        guard.submit(order, forged, "EXECUTING", False, "trace")
    assert not broker.filled_orders
    db.close()


class InvalidAcknowledgementBroker(MockBroker):
    def submit_order(self, order):
        self.calls = getattr(self, "calls", 0) + 1
        return BrokerAck("different-order", order.idempotency_key, "filled", "forged success")


def test_mismatched_broker_success_ack_is_not_treated_as_fill(tmp_path):
    broker = InvalidAcknowledgementBroker()
    rt = runtime(tmp_path, AttackProvider(), broker=broker)
    result = rt.run_cycle("EURUSD", fast_veto_response="OK")
    assert result.final_state == State.HALTED.value
    assert result.final_decision == "WAIT"
    assert broker.calls == 1
    assert not broker.filled_orders
    with rt.db.cursor() as cur:
        cur.execute("SELECT status FROM orders")
        assert cur.fetchone()[0] == "invalid_ack"
    rt.db.close()


def test_modified_legitimate_risk_result_and_missing_veto_approval_are_rejected(tmp_path):
    db = DBManager(str(tmp_path / "tampered-risk.db"))
    db.set_system_state("EXECUTING")
    broker = MockBroker()
    engine = RiskEngine(RiskConfig())
    guard = ExecutionGuard(broker, db, Observability(db, "test"), risk_engine=engine)
    portfolio = PortfolioSnapshot(10_000, 0, 0, {}, 0, 1, 0)
    quote = {"bid": 99, "ask": 100, "bid_size": 10, "ask_size": 10}
    order = ExecutionOrder("BUY", "EURUSD", 1, 98, 102, cycle_id="tamper")
    decision = engine.check(order, portfolio, now=dt.datetime(2026, 9, 25, 12,
            tzinfo=dt.timezone.utc), execution_facts=quote)
    with pytest.raises(GuardRejection):
        guard.submit(order, decision, "EXECUTING", False, "trace")
    db.save_veto_event(order.order_id, time.time(), "OK")
    decision.rules[0]["reason"] = "rewritten as passing"
    with pytest.raises(GuardRejection):
        guard.submit(order, decision, "EXECUTING", False, "trace")
    assert not broker.filled_orders
    db.close()


def test_broker_timeout_is_unknown_not_success_and_retry_is_reserved(tmp_path):
    broker = FailingBroker()
    rt = runtime(tmp_path, AttackProvider(), broker=broker)
    result = rt.run_cycle("EURUSD", fast_veto_response="OK")
    assert result.final_state == State.HALTED.value
    assert result.final_decision == "WAIT"
    assert broker.calls == 1
    assert not broker.filled_orders
    with rt.db.cursor() as cur:
        cur.execute("SELECT status FROM orders")
        assert cur.fetchone()[0] == "unknown"
    assert rt.run_cycle("EURUSD", fast_veto_response="OK").final_state == State.HALTED.value
    rt.db.close()


def test_no_live_mode_can_be_constructed():
    with pytest.raises(RuntimeError):
        AppConfig(mode="live", live_confirmed=True).validate_for_mode()
