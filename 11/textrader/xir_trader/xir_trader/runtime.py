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
import uuid
from dataclasses import dataclass

from .core.config import AppConfig, RiskConfig
from .core.schemas import ExecutionOrder, InitialDecision
from .core.state_machine import StateMachine, State, IllegalTransition
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

        self.sm = StateMachine(on_transition=self._on_transition)

        self.portfolio_adapter = portfolio_adapter or MockPortfolioAdapter()
        self.data_adapters = data_adapters or [
            MockPriceAdapter(), MockOrderBookAdapter(), MockNewsAdapter(), self.portfolio_adapter,
        ]
        self.data_reader = DataReader(self.data_adapters, self.db, Observability(self.db, "data_reader"))
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

        self.guard = ExecutionGuard(self.broker, self.db, Observability(self.db, "execution_guard"))
        self.final_tools = FinalTools(self.guard, Observability(self.db, "final_tools"))

        self.veto = VetoSystem([ConsoleChannel()], self.db, Observability(self.db, "veto"),
                                window_seconds=self.app_config.veto_window_seconds,
                                on_silence=self.app_config.on_silence)

        self.memory_manager = MemoryManager(self.db, Observability(self.db, "memory_manager"),
                                             sleep_interval_seconds=self.app_config.memory_manager_interval_seconds)

    def _on_transition(self, prev: State, new: State, reason: str = "") -> None:
        self.obs.info("state", from_state=prev.value, to_state=new.value, reason=reason)
        self.obs.audit("state_transition", from_state=prev.value, to_state=new.value, reason=reason)

    # ---- Kill switch: any state -> HALTED, absolute priority (P-05) ----
    def activate_kill_switch(self, reason: str) -> None:
        self.sm.kill_switch(reason)
        self.obs.error("kill_switch", msg="KILL_SWITCH_ACTIVATED", reason=reason)

    def recover_from_halt(self, operator_confirmed: bool) -> None:
        self.sm.recover_from_halt(operator_confirmed)

    # ---- one full decision cycle ----
    def run_cycle(self, instrument: str, fast_veto_response: str | None = None) -> CycleResult:
        trace_id = new_trace_id()
        cycle_id = str(uuid.uuid4())

        # I2: HALTED => zero orders. Refuse to even start a cycle.
        if self.sm.state == State.HALTED:
            self.obs.warn(trace_id, msg="cycle_refused_halted", cycle_id=cycle_id)
            return CycleResult(cycle_id, State.HALTED.value, None, detail="runtime is HALTED (kill switch)")

        if self.risk_config.kill_switch:
            self.activate_kill_switch("RiskConfig.kill_switch is set")
            return CycleResult(cycle_id, State.HALTED.value, None, detail="kill switch set in RiskConfig")

        self.db.create_cycle(cycle_id)
        if self.memory_manager.due():
            self.memory_manager.run_cycle(trace_id)

        return self._reeval_loop(instrument, cycle_id, trace_id, fast_veto_response)

    def _reeval_loop(self, instrument: str, cycle_id: str, trace_id: str,
                      fast_veto_response: str | None) -> CycleResult:
        self.sm.go(State.READING)
        bundles = self.data_reader.read_all(instrument, cycle_id, trace_id)

        self.sm.go(State.CONTEXTING)
        previous_decisions = []  # reference impl: keep it simple; DB has full history if needed
        market_state = next((b.payload for b in bundles if b.source == "mock_price_ohlcv"), {})
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
        self.sm.go(State.AWAIT_VETO)
        # Sizing is a policy decision independent of the Risk Engine's limits: we ask for
        # `default_order_size` and let RiskEngine.check() decide whether it's allowed
        # (rule 01_position_size). Clamping the request to the limit before checking it
        # would make that rule unable to ever reject anything — a real bug caught in
        # testing and deliberately avoided here.
        order = ExecutionOrder(
            side=final.decision, instrument=instrument, size=self.app_config.default_order_size,
            sl=1.0 if self.risk_config.require_stop_loss else 0.0,
            tp=1.0 if self.risk_config.require_take_profit else 0.0,
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
        if outcome == "wait":
            # I3: user rejection/stop => no execution.
            self.sm.go(State.WAITING)
            self.sm.go(State.IDLE)
            self.db.set_cycle_status(cycle_id, "waiting_after_veto")
            return CycleResult(cycle_id, State.IDLE.value, final.decision, order.order_id,
                                detail="vetoed by user (REJECT/STOP)")

        self.sm.go(State.RISK_CHECK)
        portfolio = PortfolioSnapshot(
            equity=self.portfolio_adapter.equity,
            daily_pnl=self.portfolio_adapter.daily_pnl,
            drawdown=max(0.0, (self.portfolio_adapter.peak_equity - self.portfolio_adapter.equity)
                         / self.portfolio_adapter.peak_equity) if self.portfolio_adapter.peak_equity else 0.0,
            open_positions=self.portfolio_adapter.open_positions,
            total_exposure=sum(p.get("size", 0) for p in self.portfolio_adapter.open_positions.values()),
            leverage=1.0,
        )
        risk_result = self.risk_engine.check(order, portfolio, now=dt.datetime.utcnow())
        self.db.save_risk_results(order.order_id, risk_result.rules)

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
                ack = self.final_tools.buy_system(order, risk_passed=True, trace_id=trace_id)
            else:
                ack = self.final_tools.sell_system(order, risk_passed=True, trace_id=trace_id)
        except GuardRejection as e:
            self.sm.go(State.IDLE)
            self.db.set_cycle_status(cycle_id, "guard_rejected")
            return CycleResult(cycle_id, State.IDLE.value, final.decision, order.order_id, detail=str(e))

        self.sm.go(State.IDLE)
        self.db.set_cycle_status(cycle_id, "executed")
        return CycleResult(cycle_id, State.IDLE.value, final.decision, order.order_id, detail=ack.status)
