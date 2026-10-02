"""
Runtime orchestrator — wires every service to the state machine in
core/state_machine.py and drives one full decision cycle end to end:

IDLE -> READING -> CONTEXTING -> A1 -> A2 -> A3
  -> (BUY/SELL) -> AWAIT_VETO -> RISK_CHECK -> GUARD -> EXECUTING -> IDLE
  -> (WAIT)     -> WAITING/IDLE
  -> (RE-EVALUATE) -> REEVAL -> READING   (capped by RiskConfig.max_reevaluate_cycles, P-01)
  -> KillSwitch (any state) -> HALTED

Invariant enforcement lives here, at the orchestration layer, so it can
never be "forgotten" by an individual service:
  I1: ExecutionGuard.submit() is only ever called after RiskResult.passed is True,
      and only after the state machine has legally reached GUARD.
  I2: if kill switch is active, the cycle stops before READING even begins.
  I3: AWAIT_VETO outcome "wait" (REJECT/STOP) skips RISK_CHECK/GUARD entirely.
  I4: Agent3 already writes every FinalDecision to the audit log (agents.py).
  I5: Handled inside each agent (invalid schema -> WAIT), see agents.py.
"""
from __future__ import annotations

import datetime as dt
import threading
import uuid
from dataclasses import dataclass

from .core.config import AppConfig, RiskConfig
from .core.schemas import ExecutionOrder
from .core.state_machine import StateMachine, State
from .core.policy import blocking_failure_reasons
from .services.db_manager import DBManager
from .services.observability import Observability, new_trace_id
from .services.data_reader import DataReader
from .services.context_service import ContextMaker, ContextSender
from .services.agents import Agent1, Agent2, Agent3
from .services.llm_provider import LLMProvider, RuleBasedProvider
from .services.risk_engine import RiskEngine, PortfolioSnapshot
from .services.execution import ExecutionGuard, FinalTools, GuardRejection
from .services.messaging import VetoSystem, ConsoleChannel
from .services.memory_manager import MemoryManager
from .adapters.data.base import DataSourceAdapter
from .adapters.data.mock import (
    MockPriceAdapter, MockOrderBookAdapter, MockNewsAdapter, MockPortfolioAdapter,
)
from .adapters.broker.base import BrokerAdapter
from .adapters.broker.mock import MockBroker


@dataclass
class CycleResult:
    cycle_id: str
    final_state: str
    final_decision: str | None
    order_id: str | None = None
    detail: str = ""


class Runtime:
    def __init__(self, app_config: AppConfig | None = None, risk_config: RiskConfig | None = None,
                 data_adapters: list[DataSourceAdapter] | None = None,
                 broker: BrokerAdapter | None = None,
                 llm_provider: LLMProvider | None = None,
                 portfolio_adapter: MockPortfolioAdapter | None = None):
        self.app_config = app_config or AppConfig()
        self.app_config.validate_for_mode()
        self.risk_config = risk_config or RiskConfig()

        self.db = DBManager(self.app_config.db_path)
        self.obs = Observability(self.db, component="runtime")
        self._safety_lock = threading.RLock()
        self._cycle_lock = threading.Lock()
        persisted_state = self.db.get_system_state()
        try:
            initial_state = State(persisted_state)
        except ValueError:
            initial_state = State.HALTED
        if initial_state not in (State.IDLE, State.HALTED):
            initial_state = State.HALTED  # interrupted/corrupted in-flight state must recover explicitly
        self.sm = StateMachine(on_transition=self._on_transition, initial_state=initial_state)
        if persisted_state not in (State.IDLE.value, State.HALTED.value):
            self.db.set_system_state(State.HALTED.value)
            self.db.append_audit("startup_fail_closed", {"persisted_state": persisted_state})

        self.portfolio_adapter = portfolio_adapter or MockPortfolioAdapter()
        self.data_adapters = data_adapters or [
            MockPriceAdapter(), MockOrderBookAdapter(), MockNewsAdapter(), self.portfolio_adapter,
        ]
        self.data_reader = DataReader(self.data_adapters, self.db, Observability(self.db, "data_reader"),
                                      max_age_seconds=self.app_config.market_data_max_age_seconds)
        self.context_maker = ContextMaker(self.db, Observability(self.db, "context_maker"))
        self.context_sender = ContextSender(Observability(self.db, "context_sender"))

        provider = llm_provider or RuleBasedProvider()
        self.agent1 = Agent1(provider, self.db, Observability(self.db, "agent1"))
        self.agent2 = Agent2(provider, self.db, Observability(self.db, "agent2"))
        self.agent3 = Agent3(provider, self.db, Observability(self.db, "agent3"))

        self.risk_engine = RiskEngine(self.risk_config)

        # Broker selection is the ONE place "live" could matter. Reference build never
        # auto-selects a live broker: caller must pass one explicitly, and even then
        # AppConfig.validate_for_mode() already refused to construct in mode="live"
        # unless live_confirmed=True was set by an operator flag.
        self.broker = broker or MockBroker()
        if self.app_config.mode == "live" and not getattr(self.broker, "is_live", False):
            raise RuntimeError("mode=live but no live BrokerAdapter was supplied (refusing mock fills as live).")
        if self.app_config.mode != "live" and getattr(self.broker, "is_live", False):
            raise RuntimeError("A live BrokerAdapter was supplied but mode != 'live'. Refusing to proceed.")

        self.guard = ExecutionGuard(self.broker, self.db, Observability(self.db, "execution_guard"),
                                    risk_engine=self.risk_engine,
                                    safety_lock=self._safety_lock,
                                    allow_veto_silence=self.app_config.on_silence == "execute")
        self.final_tools = FinalTools(self.guard, Observability(self.db, "final_tools"))

        self.veto = VetoSystem([ConsoleChannel()], self.db, Observability(self.db, "veto"),
                                window_seconds=self.app_config.veto_window_seconds,
                                on_silence=self.app_config.on_silence)

        self.memory_manager = MemoryManager(self.db, Observability(self.db, "memory_manager"),
                                             sleep_interval_seconds=self.app_config.memory_manager_interval_seconds)

    def _on_transition(self, prev: State, new: State, reason: str = "") -> None:
        self.db.set_system_state(new.value)
        prev_value = getattr(prev, "value", str(prev))
        self.obs.info("state", from_state=prev_value, to_state=new.value, reason=reason)
        self.obs.audit("state_transition", from_state=prev_value, to_state=new.value,
                       state=new.value, reason=reason)

    # ---- Kill switch: any state -> HALTED, absolute priority (P-05) ----
    def activate_kill_switch(self, reason: str) -> None:
        with self._safety_lock:
            self.sm.kill_switch(reason)
            self.obs.error("kill_switch", msg="KILL_SWITCH_ACTIVATED", reason=reason)

    def recover_from_halt(self, operator_confirmed: bool) -> None:
        with self._safety_lock:
            self.sm.recover_from_halt(operator_confirmed)
            self.db.append_audit("operator_recovered_from_halt", {"confirmed": True})

    # ---- one full decision cycle ----
    def run_cycle(self, instrument: str, fast_veto_response: str | None = None,
                  request_id: str | None = None) -> CycleResult:
        if not isinstance(instrument, str) or not instrument.strip():
            return CycleResult(request_id or str(uuid.uuid4()), State.IDLE.value, "WAIT", detail="invalid instrument")
        if not self._cycle_lock.acquire(blocking=False):
            return CycleResult(request_id or str(uuid.uuid4()), getattr(self.sm.state, "value", "UNKNOWN"), "WAIT",
                               detail="another decision cycle is active")
        try:
            return self._run_cycle(instrument, fast_veto_response, request_id)
        finally:
            self._cycle_lock.release()

    def _run_cycle(self, instrument: str, fast_veto_response: str | None,
                   request_id: str | None) -> CycleResult:
        trace_id = new_trace_id()
        cycle_id = request_id or str(uuid.uuid4())
        try:
            uuid.UUID(cycle_id)
        except (ValueError, TypeError, AttributeError):
            return CycleResult(cycle_id, getattr(self.sm.state, "value", "UNKNOWN"), "WAIT", detail="request_id must be a UUID")

        # I2: HALTED => zero orders. Refuse to even start a cycle.
        if self.sm.state == State.HALTED:
            self.obs.warn(trace_id, msg="cycle_refused_halted", cycle_id=cycle_id)
            return CycleResult(cycle_id, getattr(self.sm.state, "value", "UNKNOWN"), None,
                               detail="runtime is HALTED (kill switch)")
        if self.sm.state != State.IDLE:
            self.activate_kill_switch("unknown or non-idle state at cycle entry")
            return CycleResult(cycle_id, State.HALTED.value, "WAIT", detail="runtime state is not IDLE")

        prior_status = self.db.get_cycle_status(cycle_id)
        if prior_status is not None:
            self.obs.warn(trace_id, msg="duplicate_cycle_request_refused", cycle_id=cycle_id, status=prior_status)
            return CycleResult(cycle_id, State.IDLE.value, "WAIT",
                               detail=f"duplicate cycle identifier refused: {prior_status}")

        if self.risk_config.kill_switch:
            self.activate_kill_switch("RiskConfig.kill_switch is set")
            return CycleResult(cycle_id, State.HALTED.value, None, detail="kill switch set in RiskConfig")

        if not self.db.claim_cycle(cycle_id):
            self.obs.warn(trace_id, msg="duplicate_cycle_claim_refused", cycle_id=cycle_id)
            return CycleResult(cycle_id, getattr(self.sm.state, "value", "UNKNOWN"), "WAIT",
                               detail="duplicate cycle identifier was concurrently claimed")
        self.obs.audit("cycle_started", cycle_id=cycle_id, instrument=instrument, state=self.sm.state.value)
        if self.memory_manager.due():
            self.memory_manager.run_cycle(trace_id)

        try:
            result = self._reeval_loop(instrument, cycle_id, trace_id, fast_veto_response)
            self.obs.audit("cycle_completed", cycle_id=cycle_id, final_state=result.final_state,
                           decision=result.final_decision, order_id=result.order_id, result=result.detail)
            return result
        except Exception as exc:
            self.obs.error(trace_id, msg="cycle_failed_closed", cycle_id=cycle_id, error_type=type(exc).__name__)
            self.db.append_audit("cycle_failed_closed", {"cycle_id": cycle_id, "error_type": type(exc).__name__})
            try:
                self.db.set_cycle_status(cycle_id, "halted_error")
            finally:
                self.activate_kill_switch(f"unhandled cycle error: {type(exc).__name__}")
            return CycleResult(cycle_id, State.HALTED.value, "WAIT", detail=f"cycle failed closed: {type(exc).__name__}")

    def _reeval_loop(self, instrument: str, cycle_id: str, trace_id: str,
                      fast_veto_response: str | None) -> CycleResult:
        self.sm.go(State.READING)
        bundles = self.data_reader.read_all(instrument, cycle_id, trace_id)

        self.sm.go(State.CONTEXTING)
        previous_decisions = self.db.recent_decisions(limit=20)
        market_state = next((b.payload for b in bundles if b.critical and b.quality == "VALID"), {})
        user_config = {"mode": self.app_config.mode, "instrument": instrument}
        ctx = self.context_maker.make(
            cycle_id, bundles, self.memory_manager.snapshot_for_context(),
            previous_decisions, market_state, user_config, trace_id,
        )
        ctx = self.context_sender.send(ctx, deliver_fn=lambda c: c, trace_id=trace_id)

        self.sm.go(State.A1)
        initial = self.agent1.run(cycle_id, instrument, ctx.sections, trace_id)

        self.sm.go(State.A2)
        failure_report = self.agent2.run(cycle_id, initial, ctx.sections, trace_id)

        self.sm.go(State.A3)
        final = self.agent3.run(cycle_id, initial, failure_report, ctx.sections, trace_id)

        policy_blocks = blocking_failure_reasons(failure_report, ctx.sections)
        if not initial.validated:
            policy_blocks.append("Agent 1 output failed local schema/data validation")
        policy_blocks = list(dict.fromkeys(policy_blocks))
        if policy_blocks and final.decision in ("BUY", "SELL"):
            final.decision = "WAIT"
            final.overrode_initial = True
            final.reason = "runtime deterministic policy forced WAIT: " + "; ".join(policy_blocks)
            final.blocking_issues = policy_blocks
            self.db.save_decision(cycle_id, 3, "DeterministicPolicyOverride", final.__dict__)
            self.obs.audit("deterministic_policy_block", cycle_id=cycle_id, issues=policy_blocks)

        if final.decision == "RE-EVALUATE":
            count = self.db.increment_reeval(cycle_id)
            if count > self.risk_config.max_reevaluate_cycles:  # P-01
                self.obs.warn(trace_id, msg="max_reevaluate_cycles_exceeded -> forcing WAIT", count=count)
                self.sm.go(State.WAITING)
                self.sm.go(State.IDLE)
                self.db.set_cycle_status(cycle_id, "wait_reeval_cap")
                return CycleResult(cycle_id, State.IDLE.value, "WAIT", detail="max_reevaluate_cycles exceeded")
            self.sm.go(State.REEVAL)
            return self._reeval_loop(instrument, cycle_id, trace_id, fast_veto_response)

        if final.decision == "WAIT":
            self.sm.go(State.WAITING)
            self.sm.go(State.IDLE)
            self.final_tools.skip("agent3 decided WAIT", trace_id)
            self.db.set_cycle_status(cycle_id, "wait")
            return CycleResult(cycle_id, State.IDLE.value, "WAIT")

        # BUY or SELL
        price = market_state.get("close") if isinstance(market_state, dict) else None
        sl, tp = final.stop_loss, final.take_profit
        protective_levels_valid = (
            isinstance(price, (int, float)) and sl > 0 and tp > 0
            and ((final.decision == "BUY" and sl < price < tp)
                 or (final.decision == "SELL" and tp < price < sl))
        )
        if self.risk_config.require_stop_loss or self.risk_config.require_take_profit:
            if not protective_levels_valid:
                self.obs.audit("protective_levels_missing_or_invalid", cycle_id=cycle_id,
                               decision=final.decision, price=price, stop_loss=sl, take_profit=tp)
                self.sm.go(State.WAITING)
                self.sm.go(State.IDLE)
                self.db.set_cycle_status(cycle_id, "wait_protective_levels")
                return CycleResult(cycle_id, State.IDLE.value, "WAIT",
                                   detail="valid strategy-provided stop loss and take profit are required")
        self.sm.go(State.AWAIT_VETO)
        # Sizing is a policy decision independent of the Risk Engine's limits: we ask for
        # `default_order_size` and let RiskEngine.check() decide whether it's allowed
        # (rule 01_position_size). Clamping the request to the limit before checking it
        # would make that rule unable to ever reject anything — a real bug caught in
        # testing and deliberately avoided here.
        order = ExecutionOrder(
            side=final.decision, instrument=instrument, size=self.app_config.default_order_size,
            # No stop/take levels are fabricated. If configured as mandatory,
            # deterministic RiskEngine rejects until the strategy supplies them.
            sl=sl,
            tp=tp,
            cycle_id=cycle_id,
        )
        try:
            order.validate()
        except Exception as e:
            self.obs.warn(trace_id, msg="order_schema_invalid_forcing_wait", error=str(e))
            self.sm.go(State.WAITING)
            self.sm.go(State.IDLE)
            self.db.set_cycle_status(cycle_id, "wait_invalid_order")
            return CycleResult(cycle_id, State.IDLE.value, "WAIT", detail=f"invalid order: {e}")

        outcome = self.veto.run_veto_window(
            order.order_id,
            f"proposed {order.side} {order.instrument} size={order.size} (cycle {cycle_id})",
            trace_id, fast_response=fast_veto_response,
        )
        if outcome in ("wait", "reject", "stop"):
            # I3: user rejection/stop => no execution.
            self.sm.go(State.WAITING)
            if outcome in ("reject", "stop"):
                self.activate_kill_switch(f"human veto response: {outcome.upper()}")
                self.db.set_cycle_status(cycle_id, "human_hold")
            else:
                self.sm.go(State.IDLE)
                self.db.set_cycle_status(cycle_id, "waiting_after_veto")
            return CycleResult(cycle_id, State.HALTED.value if self.sm.state == State.HALTED else State.IDLE.value,
                                final.decision, order.order_id,
                                detail="human hold; explicit authorized recovery required" if outcome in ("reject", "stop")
                                else "veto window ended without approval")

        self.sm.go(State.RISK_CHECK)
        portfolio = PortfolioSnapshot(
            equity=self.portfolio_adapter.equity,
            daily_pnl=self.portfolio_adapter.daily_pnl,
            drawdown=((self.portfolio_adapter.peak_equity - self.portfolio_adapter.equity)
                      / self.portfolio_adapter.peak_equity) if self.portfolio_adapter.peak_equity else None,
            open_positions=self.portfolio_adapter.open_positions,
            total_exposure=sum(p.get("size", 0) for p in self.portfolio_adapter.open_positions.values()),
            leverage=getattr(self.portfolio_adapter, "leverage", None),
            correlated_exposure=getattr(self.portfolio_adapter, "correlated_exposure", None),
        )
        execution_facts = next((b.payload for b in bundles if b.quality == "VALID"
                                and isinstance(b.payload, dict) and "bid" in b.payload and "ask" in b.payload), None)
        risk_result = self.risk_engine.check(order, portfolio, now=dt.datetime.now(dt.timezone.utc),
                                             execution_facts=execution_facts)
        self.db.save_risk_results(order.order_id, risk_result.rules)
        self.db.append_audit("risk_result", {"cycle_id": cycle_id, "order_id": order.order_id,
                           "allowed": risk_result.passed, "failed_rules": [r for r in risk_result.rules if not r["passed"]]})

        if not risk_result.passed:
            self.obs.warn(trace_id, msg="risk_check_failed", order_id=order.order_id,
                           failure=risk_result.first_failure())
            self.sm.go(State.WAITING)
            self.sm.go(State.IDLE)
            self.db.set_cycle_status(cycle_id, "risk_rejected")
            return CycleResult(cycle_id, State.IDLE.value, final.decision, order.order_id,
                                detail=f"risk check failed: {risk_result.first_failure()}")

        # I1: only NOW, with risk_result.passed == True and state legally at GUARD, do we execute.
        self.sm.go(State.GUARD)
        self.sm.go(State.EXECUTING)
        try:
            if order.side == "BUY":
                ack = self.final_tools.buy_system(order, risk_result=risk_result,
                                                  system_state=self.sm.state.value,
                                                  human_stop=False, trace_id=trace_id)
            else:
                ack = self.final_tools.sell_system(order, risk_result=risk_result,
                                                   system_state=self.sm.state.value,
                                                   human_stop=False, trace_id=trace_id)
        except GuardRejection as e:
            self.sm.go(State.IDLE)
            self.db.set_cycle_status(cycle_id, "guard_rejected")
            return CycleResult(cycle_id, State.IDLE.value, final.decision, order.order_id, detail=str(e))

        self.sm.go(State.IDLE)
        status = "executed" if ack.status == "filled" else "broker_rejected"
        self.db.set_cycle_status(cycle_id, status)
        self.obs.audit("execution_result", cycle_id=cycle_id, order_id=order.order_id,
                       decision=final.decision, status=ack.status, detail=ack.detail)
        return CycleResult(cycle_id, State.IDLE.value, final.decision if ack.status == "filled" else "WAIT",
                           order.order_id, detail=ack.status)
