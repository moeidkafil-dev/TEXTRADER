"""
Orchestrator — the heart of the textrader runtime.

Implements the full state machine (chapter 04) and enforces invariants I1–I5
(chapter 04 SYSTEM_MODEL.md). Runs one cycle end-to-end:

  IDLE → READING → CONTEXTING → A1 → A2 → A3
       → (BUY|SELL) → AWAIT_VETO → RISK_CHECK → GUARD → EXECUTING → IDLE
       → WAIT → WAITING/IDLE ; RE-EVAL → REEVAL → READING
       → any state --KillSwitch--> HALTED

Per OI-03 the Risk Engine is invoked TWICE: once pre-Decision-Engine (rules
that don't require an order — trading sessions + kill switch) and once
post-Decision-Validator (all 11 rules with the ExecutionOrder). The orchestrator
also runs the audit append (I4) on every decision and observability emission
on every component transition.

The orchestrator is the ONLY component that can move state. All services are
stateless (modulo memory + DB).
"""
from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from trader.adapters.broker import get_broker, BrokerAdapter
from trader.adapters.llm import LLMAdapter
from trader.core.config import RiskConfig, TraderConfig
from trader.core.schemas import (
    AuditRecord, Context, DataBundle, ExecutionOrder, ExecutionResult,
    FinalDecision, FailureReport, InitialDecision, ObservabilityEvent,
    OrderStatus, RiskResult, VetoEvent, VetoResponse, Action, Side,
)
from trader.core.state_machine import State, StateMachine, Transition
from trader.core.util import sha256_of, short_id, utcnow
from trader.memory.manager import MemoryManager
from trader.memory.db_manager import DBManager
from trader.memory.stores import MemoryStore, MemoryType
from trader.services.agent1 import Agent1
from trader.services.agent2 import Agent2
from trader.services.agent3 import Agent3
from trader.services.context_service import ContextMaker, ContextSender
from trader.services.data_reader import DataReader, get_default_source
from trader.services.decision_engine import DecisionEngine
from trader.services.decision_validator import DecisionValidator
from trader.services.execution_guard import ExecutionGuard
from trader.services.final_tools import FinalTools
from trader.services.kill_switch import KillSwitch
from trader.services.message_service import (
    EmailSender, MessageSendManager, MessageSystem, TelegramSender,
)
from trader.services.observability import Observability
from trader.services.risk_engine import RiskEngine
from trader.storage import repo
from trader.storage.connection import get_db, reset_default_db
from trader.storage.schema import init_schema


@dataclass
class CycleResult:
    cycle_id: str
    initial: Optional[InitialDecision] = None
    failure: Optional[FailureReport] = None
    final: Optional[FinalDecision] = None
    order: Optional[ExecutionOrder] = None
    veto: Optional[VetoEvent] = None
    risk: Optional[RiskResult] = None
    guard_passed: bool = False
    execution: Optional[ExecutionResult] = None
    final_state: str = State.IDLE.value
    reeval_count: int = 0
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "cycle_id": self.cycle_id,
            "initial": self.initial.to_dict() if self.initial else None,
            "failure": self.failure.to_dict() if self.failure else None,
            "final": self.final.to_dict() if self.final else None,
            "order": self.order.to_dict() if self.order else None,
            "veto": self.veto.to_dict() if self.veto else None,
            "risk": self.risk.to_dict() if self.risk else None,
            "guard_passed": self.guard_passed,
            "execution": self.execution.to_dict() if self.execution else None,
            "final_state": self.final_state,
            "reeval_count": self.reeval_count,
            "errors": self.errors,
        }


class Orchestrator:
    """Wires all services and runs cycles."""

    def __init__(self, risk_config: RiskConfig, trader_config: TraderConfig,
                 *, observability: Optional[Observability] = None,
                 db_path: Optional[str] = None,
                 user_veto_hook=None,
                 llm_provider_name: str | None = None,
                 broker_name: str | None = None,
                 price_feed=None,
                 data_source=None):
        self.rc = risk_config
        self.tc = trader_config

        # DB
        # A single Orchestrator instance is a stateful state-machine owner.
        # Serialize cycles at this boundary so callers cannot race START_CYCLE
        # / transition mutations. RLock also permits bounded RE-EVALUATE
        # recursion inside the same cycle.
        self._cycle_lock = threading.RLock()
        if db_path:
            self._db_path = db_path
        else:
            self._db_path = self.tc.db_path
        # NOTE: we deliberately do NOT call reset_default_db() here.
        #
        # get_db(path) already returns a fresh connection whenever `path`
        # differs from whatever the process-wide default currently points
        # at (e.g. a new pytest tmp_path per test), and reuses the *same
        # still-open* connection when `path` matches. Unconditionally
        # force-closing the previous default on every Orchestrator
        # construction — as this used to do — broke any other live object
        # still holding that old connection the moment a second
        # Orchestrator was built against the same db_path (e.g.
        # ControlPlane._build() runs on every /api/analyze call in
        # trader/web/server.py, and test_kill_switch_persists_across_
        # orchestrator_instances constructs three Orchestrators against one
        # file). That earlier instance's self.db then pointed at a closed
        # sqlite3.Connection, so any later call on it — such as
        # resume_from_halted() — raised
        # "sqlite3.ProgrammingError: Cannot operate on a closed database."
        self.db = get_db(self._db_path)
        init_schema(self.db)

        # Observability
        self.obs = observability or Observability(db_getter=lambda: self.db,
                                                    level=self.tc.log_level)

        # Memory
        self.store = MemoryStore(repo)
        self.memory = MemoryManager(self.store, observability_sink=self._obs_sink, sleep_interval_seconds=self.tc.memory_manager_interval_seconds)
        self.db_manager = DBManager(repo, observability_sink=self._obs_sink)

        # State machine must exist before KillSwitch can invoke its callback.
        # This guarantees a config-time kill switch enters HALTED immediately.
        self.sm = StateMachine(state=State.IDLE)

        # Kill switch. Persist the safety state in SQLite so CLI invocations
        # and newly-created web control-plane orchestrators observe the same
        # active HALT. Configuration-level activation remains fail-closed.
        self.kill_switch = KillSwitch(self.obs, on_change=self._on_kill_switch_change)
        self._runtime_kill_switch_active = False
        persisted_ks = repo.get_runtime_control(self.db, "kill_switch_active", "0")
        persisted_reason = repo.get_runtime_control(self.db, "kill_switch_reason", "persisted") or "persisted"
        if self.rc.kill_switch or persisted_ks == "1":
            reason = "config_kill_switch_true" if self.rc.kill_switch else persisted_reason
            self.kill_switch.activate(reason)
            self._runtime_kill_switch_active = (not self.rc.kill_switch and persisted_ks == "1")

        # LLM adapter
        self.llm = LLMAdapter(provider_name=llm_provider_name or self.tc.llm_provider)

        # Data reader
        self.data_source = data_source or get_default_source(self.tc.instruments)
        self.data_reader = DataReader([self.data_source], observability=self.obs)

        # Context
        self.context_maker = ContextMaker(memory_manager=self.memory,
                                           observability=self.obs,
                                           user_config={"risk_appetite": "moderate"})
        self.context_sender = ContextSender(observability=self.obs)

        # Agents
        self.agent1 = Agent1(self.llm, self.memory, self.obs)
        self.agent2 = Agent2(self.llm, self.memory, self.obs)
        self.agent3 = Agent3(self.llm, self.memory, self.obs)

        # Message system
        email = EmailSender(self.obs)
        telegram = TelegramSender(self.obs, chat_whitelist=["textrader-owner"])
        send_manager = MessageSendManager(email, telegram, observability=self.obs,
                                          email_to="textrader@trader.local" if self.tc.enable_email else "",
                                          telegram_chat="textrader-owner" if self.tc.enable_telegram else "")
        self.message_system = MessageSystem(send_manager, observability=self.obs,
                                             veto_window_seconds=self.tc.veto_window_seconds,
                                             on_silence=self.tc.on_silence,
                                             user_veto_hook=user_veto_hook)

        # Decision / Risk / Guard / Broker / Final tools
        self.decision_engine = DecisionEngine(observability=self.obs,
                                                default_size=None,
                                                sl_pct=0.01,
                                                tp_pct=0.02,
                                                risk_config=self.rc,
                                                risk_fraction=0.005,
                                                max_exposure_fraction=min(0.10, self.rc.max_portfolio_exposure))
        self.validator = DecisionValidator(self.rc, observability=self.obs)
        self.risk_engine = RiskEngine(self.rc, observability=self.obs,
                                       kill_switch=self.kill_switch)
        self.broker = get_broker(broker_name or self.tc.broker,
                                  price_feed=price_feed)
        self.guard = ExecutionGuard(self.kill_switch, observability=self.obs)
        self.final_tools = FinalTools(self.broker, observability=self.obs,
                                      kill_switch=self.kill_switch)

        # Portfolio state
        self._init_portfolio_state()

    # -------- helpers --------
    def _obs_sink(self, component: str, data: dict) -> None:
        self.obs.emit(component, "info", trace_id=data.get("cycle_id", "mem"),
                       cycle_id=data.get("cycle_id", ""), data=data)

    def _on_kill_switch_change(self, active: bool, reason: str) -> None:
        if active:
            self.sm.force_halted()
            self._log_transition("(any)", "KILL_SWITCH", "HALTED")
        # deactivation handled explicitly via resume()

    def _init_portfolio_state(self) -> None:
        existing = repo.latest_portfolio_state(self.db)
        if not existing:
            repo.upsert_portfolio_state(self.db, equity=self.tc.initial_equity,
                                          peak_equity=self.tc.initial_equity,
                                          cash=self.tc.initial_equity,
                                          positions={},
                                          realized_pnl=0.0,
                                          unrealized_pnl=0.0,
                                          daily_loss=0.0)

    def _log_transition(self, from_state: str, transition: str, to_state: str,
                         cycle_id: Optional[str] = None) -> None:
        repo.log_state_transition(self.db, from_state, transition, to_state, cycle_id)
        self.obs.info("state_machine", trace_id=cycle_id or "sm",
                       data={"from": from_state, "via": transition, "to": to_state,
                              "cycle_id": cycle_id})

    def _audit(self, cycle_id: str, component: str, event: str, payload: dict) -> None:
        h = sha256_of(payload)
        rec = AuditRecord(cycle_id=cycle_id, component=component, event=event,
                          payload_hash=h)
        repo.insert_audit(self.db, rec)
        self.obs.info("audit", trace_id=cycle_id,
                       data={"component": component, "event": event, "hash": h})

    # -------- public API --------

    def _sync_runtime_kill_switch(self) -> None:
        """Reconcile this instance with the persistent runtime kill switch.

        The SQLite runtime control is the source of truth across live
        Orchestrator instances. This deliberately leaves configuration-level
        kill switches untouched: those remain fail-closed until configuration
        changes.
        """
        if self.rc.kill_switch:
            return
        active = repo.get_runtime_control(self.db, "kill_switch_active", "0") == "1"
        reason = repo.get_runtime_control(self.db, "kill_switch_reason", "persisted") or "persisted"
        if active and not self._runtime_kill_switch_active:
            self._runtime_kill_switch_active = True
            self.kill_switch.activate(reason)
        elif not active and self._runtime_kill_switch_active:
            self._runtime_kill_switch_active = False
            self.kill_switch.deactivate("runtime_sync")
            if self.sm.state == State.HALTED:
                self.sm.force_idle()

    def activate_kill_switch(self, reason: str = "manual") -> None:
        repo.set_runtime_control(self.db, "kill_switch_active", "1")
        repo.set_runtime_control(self.db, "kill_switch_reason", reason)
        self._runtime_kill_switch_active = True
        self.kill_switch.activate(reason)

    def resume_from_halted(self, reason: str = "manual_resume") -> None:
        self._sync_runtime_kill_switch()
        if self.sm.state != State.HALTED and not self.kill_switch.is_active:
            return
        if self.rc.kill_switch:
            return
        self.kill_switch.deactivate(reason)
        self._runtime_kill_switch_active = False
        repo.set_runtime_control(self.db, "kill_switch_active", "0")
        repo.set_runtime_control(self.db, "kill_switch_reason", "")
        self.sm.force_idle()
        self._log_transition("HALTED", "RESUME_FROM_HALTED", "IDLE")

    @property
    def state(self) -> str:
        return self.sm.state.value

    def is_halted(self) -> bool:
        self._sync_runtime_kill_switch()
        return self.sm.state == State.HALTED or self.kill_switch.is_active

    # -------- single cycle --------

    def run_cycle(self, *, cycle_id: Optional[str] = None,
                  reeval_count: int = 0,
                  user_veto_hook=None,
                  _start_from_reading: bool = False) -> CycleResult:
        # Serialize the entire stateful cycle. The engine owns one mutable
        # StateMachine, so concurrent callers must queue rather than race it.
        with self._cycle_lock:
            if self.is_halted():
                return CycleResult(cycle_id=cycle_id or short_id("cyc_"),
                                    final_state=State.HALTED.value,
                                    errors=["halted_at_start"])
            cid = cycle_id or short_id("cyc_")
            result = CycleResult(cycle_id=cid, reeval_count=reeval_count)
            # Open cycle record
            started_at = utcnow().isoformat()
            repo.insert_cycle(self.db, cid, started_at, "running", reeval_count)
            self._audit(cid, "orchestrator", "cycle_start", {"cycle_id": cid})

            try:
                self._run_cycle_inner(cid, result, user_veto_hook, start_from_reading=_start_from_reading)
                final_state_label = self.sm.state.value
                repo.update_cycle_status(self.db, cid, "completed" if final_state_label == "IDLE"
                                         else final_state_label.lower(),
                                         ended_at=utcnow().isoformat(),
                                         reeval_count=result.reeval_count)
                result.final_state = final_state_label
            except Exception as e:
                self.obs.error("orchestrator", trace_id=cid, data={"event": "cycle_exception", "error": str(e)})
                result.errors.append(str(e))
                repo.update_cycle_status(self.db, cid, "error", ended_at=utcnow().isoformat())
                result.final_state = self.sm.state.value
            self._audit(cid, "orchestrator", "cycle_end", {"cycle_id": cid, "state": result.final_state})
            return result

    def _run_cycle_inner(self, cid: str, result: CycleResult, user_veto_hook, *, start_from_reading: bool = False) -> None:
        # ---- IDLE → READING ----
        # Normal cycles begin in IDLE. A RE-EVALUATE branch has already moved
        # the state machine through REEVAL → READING before opening the new cycle.
        if not start_from_reading:
            self.sm.apply(Transition.START_CYCLE)
            self._log_transition("IDLE", "START_CYCLE", "READING", cid)
        elif self.sm.state != State.READING:
            raise RuntimeError(f"internal cycle start expected READING, got {self.sm.state.value}")

        # ---- READING ----
        bundles = self.data_reader.read(cid)
        for b in bundles:
            repo.insert_data_bundle(self.db, b, cid)
        self._audit(cid, "data_reader", "read", {"bundles": len(bundles)})

        self.sm.apply(Transition.DATA_READ)
        self._log_transition("READING", "DATA_READ", "CONTEXTING", cid)

        # ---- CONTEXTING ----
        prev = repo.list_decisions(self.db, cid)
        portfolio_state = repo.latest_portfolio_state(self.db) or {"equity": self.tc.initial_equity, "cash": self.tc.initial_equity, "positions": {}}
        ctx = self.context_maker.make(cid, bundles, previous_decisions=prev, market_state=portfolio_state)
        repo.insert_context(self.db, ctx)
        self._audit(cid, "context_maker", "make", {"context_id": ctx.context_id, "hash": ctx.hash})
        # Deliver to agent1 (REQ-DR-04)
        self.context_sender.deliver(ctx, self.agent1)
        self.sm.apply(Transition.CONTEXT_READY)
        self._log_transition("CONTEXTING", "CONTEXT_READY", "A1", cid)

        # ---- A1 ----
        initial = self.agent1.run(ctx)
        repo.insert_initial_decision(self.db, initial)
        self._audit(cid, "agent1", "initial", initial.to_dict())
        result.initial = initial
        # I5 — schema validation
        if not initial.action in Action.values():
            self.obs.warn("orchestrator", trace_id=cid, data={"event": "I5_initial_invalid"})
            # Downgrade to WAIT
            initial = InitialDecision(cycle_id=cid, action=Action.WAIT.value,
                                       instrument=initial.instrument, rationale="I5 fallback")
            self._audit(cid, "agent1", "I5_downgrade", initial.to_dict())
        self.sm.apply(Transition.A1_DONE)
        self._log_transition("A1", "A1_DONE", "A2", cid)

        # ---- A2 ----
        failure = self.agent2.run(ctx, initial)
        repo.insert_failure_report(self.db, failure)
        self._audit(cid, "agent2", "failure", failure.to_dict())
        result.failure = failure
        self.sm.apply(Transition.A2_DONE)
        self._log_transition("A2", "A2_DONE", "A3", cid)

        # ---- A3 ----
        final = self.agent3.run(ctx, initial, failure)
        repo.insert_final_decision(self.db, final)
        self._audit(cid, "agent3", "final", final.to_dict())
        result.final = final
        # I5 — FinalDecision ∈ {BUY,SELL,WAIT,RE-EVALUATE}
        if final.decision not in Action.final_values():
            self.obs.warn("orchestrator", trace_id=cid, data={"event": "I5_final_invalid"})
            final = FinalDecision(cycle_id=cid, decision=Action.WAIT.value,
                                   overrode_initial=True, reason="I5 fallback")
            self._audit(cid, "agent3", "I5_downgrade", final.to_dict())
            result.final = final

        # ---- branch on final.decision ----
        if final.decision == Action.RE_EVALUATE.value:
            # RE-EVAL → READING (with cap P-01)
            if result.reeval_count + 1 >= self.tc.max_reevaluate_cycles:
                self.obs.warn("orchestrator", trace_id=cid,
                                data={"event": "reeval_cap_reached",
                                       "count": result.reeval_count + 1})
                self.sm.apply(Transition.A3_WAIT)
                self._log_transition("A3", "A3_WAIT", "WAITING", cid)
                self.sm.apply(Transition.USER_NEW_COMMAND)
                self._log_transition("WAITING", "USER_NEW_COMMAND", "IDLE", cid)
                result.final_state = State.IDLE.value
                return
            self.sm.apply(Transition.A3_REEVAL)
            self._log_transition("A3", "A3_REEVAL", "REEVAL", cid)
            # Start a new cycle from READING. The cap protects against infinite recursion.
            new_cid = short_id("cyc_")
            self.sm.apply(Transition.START_CYCLE)
            self._log_transition("REEVAL", "START_CYCLE", "READING", new_cid)
            inner = self.run_cycle(cycle_id=new_cid,
                                     reeval_count=result.reeval_count + 1,
                                     user_veto_hook=user_veto_hook,
                                     _start_from_reading=True)
            # propagate inner state
            result.final_state = inner.final_state
            result.reeval_count = inner.reeval_count
            return

        if final.decision == Action.WAIT.value:
            # No order; go to WAITING then IDLE
            self.sm.apply(Transition.A3_WAIT)
            self._log_transition("A3", "A3_WAIT", "WAITING", cid)
            self.sm.apply(Transition.USER_NEW_COMMAND)
            self._log_transition("WAITING", "USER_NEW_COMMAND", "IDLE", cid)
            result.final_state = State.IDLE.value
            return

        # BUY / SELL → AWAIT_VETO
        self.sm.apply(Transition.A3_BUY_SELL)
        self._log_transition("A3", "A3_BUY_SELL", "AWAIT_VETO", cid)

        # Build the ExecutionOrder via Decision Engine
        order = self.decision_engine.to_order(final, ctx)
        if order is None:
            self.obs.error("orchestrator", trace_id=cid, data={"event": "no_order_built"})
            result.errors.append("no_order_built")
            self.sm.apply(Transition.A3_WAIT)
            self._log_transition("AWAIT_VETO", "A3_WAIT", "WAITING", cid)
            self.sm.apply(Transition.USER_NEW_COMMAND)
            self._log_transition("WAITING", "USER_NEW_COMMAND", "IDLE", cid)
            result.final_state = State.IDLE.value
            return
        repo.insert_order(self.db, order, status="draft")
        self._audit(cid, "decision_engine", "order_built", order.to_dict())
        result.order = order

        # Validate (Decision Validator)
        ok, reason = self.validator.validate(order, ctx)
        if not ok:
            self.obs.warn("orchestrator", trace_id=cid, data={"event": "validator_rejected", "reason": reason})
            repo.update_order_status(self.db, order.order_id, OrderStatus.REJECTED.value)
            self._audit(cid, "decision_validator", "rejected", {"reason": reason})
            self.sm.apply(Transition.RISK_REJECT)
            self._log_transition("AWAIT_VETO", "RISK_REJECT", "WAITING", cid)
            self.sm.apply(Transition.USER_NEW_COMMAND)
            self._log_transition("WAITING", "USER_NEW_COMMAND", "IDLE", cid)
            result.final_state = State.IDLE.value
            return
        repo.update_order_status(self.db, order.order_id, OrderStatus.VALIDATED.value)
        self._audit(cid, "decision_validator", "validated", {"order_id": order.order_id})

        # AWAIT_VETO — notify user + wait
        if self.tc.enable_user_veto:
            self.message_system._user_hook = user_veto_hook or self.message_system._user_hook
            veto = self.message_system.notify_and_wait(final, order)
        else:
            veto = VetoEvent(order_id=order.order_id,
                              notified_at=utcnow(),
                              response=VetoResponse.SILENCE.value,
                              responded_at=utcnow())
            repo.insert_veto_event(self.db, veto)
        result.veto = veto

        # branch on veto response
        if veto.response == VetoResponse.REJECT.value:
            # I3 — user reject ⇒ no execution
            self._audit(cid, "veto", "rejected", veto.to_dict())
            self.sm.apply(Transition.VETO_REJECT)
            self._log_transition("AWAIT_VETO", "VETO_REJECT", "WAITING", cid)
            self.sm.apply(Transition.USER_NEW_COMMAND)
            self._log_transition("WAITING", "USER_NEW_COMMAND", "IDLE", cid)
            result.final_state = State.IDLE.value
            return
        if veto.response == VetoResponse.WAIT.value:
            # Configured silence policy: no execution.
            self._audit(cid, "veto", "wait_on_silence", veto.to_dict())
            self.sm.apply(Transition.VETO_REJECT)
            self._log_transition("AWAIT_VETO", "VETO_REJECT", "WAITING", cid)
            self.sm.apply(Transition.USER_NEW_COMMAND)
            self._log_transition("WAITING", "USER_NEW_COMMAND", "IDLE", cid)
            result.final_state = State.IDLE.value
            return
        if veto.response == VetoResponse.STOP.value:
            # STOP ⇒ WAITING until next user command (chapter 08)
            self._audit(cid, "veto", "stop", veto.to_dict())
            self.sm.apply(Transition.VETO_STOP)
            self._log_transition("AWAIT_VETO", "VETO_STOP", "WAITING", cid)
            self.sm.apply(Transition.USER_NEW_COMMAND)
            self._log_transition("WAITING", "USER_NEW_COMMAND", "IDLE", cid)
            result.final_state = State.IDLE.value
            return
        # silence or OK ⇒ proceed
        t = Transition.VETO_SILENCE if veto.response == VetoResponse.SILENCE.value else Transition.VETO_OK
        self.sm.apply(t)
        self._log_transition("AWAIT_VETO", t.value, "RISK_CHECK", cid)

        # ---- RISK_CHECK (post-validator final check) ----
        ps = repo.latest_portfolio_state(self.db) or {
            "equity": self.tc.initial_equity, "peak_equity": self.tc.initial_equity,
            "cash": self.tc.initial_equity, "positions": {},
            "realized_pnl": 0.0, "unrealized_pnl": 0.0, "daily_loss": 0.0,
        }
        risk = self.risk_engine.final_check(order, portfolio=ps,
                                              equity=ps["equity"],
                                              peak_equity=ps["peak_equity"],
                                              daily_loss=ps.get("daily_loss", 0.0),
                                              positions_exposure=sum(
                                                  (v.get("notional", 0) / max(ps["equity"], 1e-9))
                                                  for v in ps.get("positions", {}).values()
                                              ),
                                              correlations=None)
        repo.insert_risk_result(self.db, risk)
        self._audit(cid, "risk_engine", "final_check", risk.to_dict())
        result.risk = risk
        if not risk.passed:
            repo.update_order_status(self.db, order.order_id, OrderStatus.REJECTED.value)
            self.sm.apply(Transition.RISK_REJECT)
            self._log_transition("RISK_CHECK", "RISK_REJECT", "WAITING", cid)
            self.sm.apply(Transition.USER_NEW_COMMAND)
            self._log_transition("WAITING", "USER_NEW_COMMAND", "IDLE", cid)
            result.final_state = State.IDLE.value
            return
        repo.update_order_status(self.db, order.order_id, OrderStatus.RISK_PASS.value)
        # Move from RISK_CHECK to GUARD
        self.sm.apply(Transition.RISK_PASS)
        self._log_transition("RISK_CHECK", "RISK_PASS", "GUARD", cid)

        # ---- GUARD ----
        self._sync_runtime_kill_switch()
        if self.is_halted():
            repo.update_order_status(self.db, order.order_id, OrderStatus.REJECTED.value)
            self.sm.force_halted()
            result.errors.append("halted_before_guard")
            result.final_state = State.HALTED.value
            return
        allowed, why = self.guard.allow(order, risk, veto)
        result.guard_passed = allowed
        if not allowed:
            self.obs.warn("orchestrator", trace_id=cid, data={"event": "guard_rejected", "reason": why})
            self._audit(cid, "execution_guard", "rejected", {"reason": why})
            repo.update_order_status(self.db, order.order_id, OrderStatus.REJECTED.value)
            self.sm.apply(Transition.GUARD_REJECT)
            self._log_transition("GUARD", "GUARD_REJECT", "WAITING", cid)
            self.sm.apply(Transition.USER_NEW_COMMAND)
            self._log_transition("WAITING", "USER_NEW_COMMAND", "IDLE", cid)
            result.final_state = State.IDLE.value
            return
        repo.update_order_status(self.db, order.order_id, OrderStatus.GUARD_PASS.value)
        self._audit(cid, "execution_guard", "allow", {"order_id": order.order_id})
        self.sm.apply(Transition.GUARD_PASS)
        self._log_transition("GUARD", "GUARD_PASS", "EXECUTING", cid)

        # ---- EXECUTING ----
        # Reconcile once more immediately before the final execution call so a
        # kill switch raised by another live instance cannot remain stale in
        # this process. FinalTools also performs its local fail-closed check.
        self._sync_runtime_kill_switch()
        if self.is_halted():
            repo.update_order_status(self.db, order.order_id, OrderStatus.REJECTED.value)
            self.sm.force_halted()
            result.execution = ExecutionResult(
                order_id=order.order_id,
                status=OrderStatus.REJECTED.value,
                broker_ack="kill_switch active (HALTED)",
            )
            result.errors.append("halted_before_execution")
            self._audit(cid, "final_tools", "blocked", result.execution.to_dict())
            result.final_state = State.HALTED.value
            return
        if order.side == Side.BUY.value:
            exec_result = self.final_tools.buy_system(order)
        else:
            exec_result = self.final_tools.sell_system(order)
        repo.update_order_status(self.db, order.order_id, exec_result.status)
        self._audit(cid, "final_tools", "execute", exec_result.to_dict())
        result.execution = exec_result

        # Update portfolio state for a fill
        if exec_result.status == OrderStatus.FILLED.value:
            self._apply_fill(order, exec_result, ps)
        self.sm.apply(Transition.EXEC_DONE)
        self._log_transition("EXECUTING", "EXEC_DONE", "IDLE", cid)
        result.final_state = State.IDLE.value

    def _apply_fill(self, order: ExecutionOrder, exec_result: ExecutionResult, ps: dict) -> None:
        """Update portfolio_state after a fill (paper mode)."""
        price = exec_result.fill_price or 100.0
        size = exec_result.fill_size or order.size
        notional = price * size
        positions = dict(ps.get("positions", {}))
        pos = positions.get(order.instrument, {"size": 0, "notional": 0, "avg_price": 0})
        if order.side == Side.BUY.value:
            new_size = pos["size"] + size
            new_notional = pos["notional"] + notional
            avg = new_notional / new_size if new_size > 0 else 0
            positions[order.instrument] = {"size": new_size, "notional": new_notional,
                                            "avg_price": avg}
        else:
            new_size = pos["size"] - size
            new_notional = pos["notional"] - notional
            if abs(new_size) < 1e-9:
                positions.pop(order.instrument, None)
            else:
                positions[order.instrument] = {"size": new_size, "notional": new_notional,
                                                "avg_price": pos.get("avg_price", 0)}
        cash = ps.get("cash", self.tc.initial_equity)
        if order.side == Side.BUY.value:
            cash -= notional
        else:
            cash += notional
        equity = cash + sum(p["notional"] for p in positions.values())
        peak = max(ps.get("peak_equity", equity), equity)
        # crude daily_loss: equity - initial_equity (negative ⇒ loss)
        daily_loss = max(0.0, (ps.get("peak_equity", self.tc.initial_equity) - equity)
                         / max(ps.get("peak_equity", 1e-9), 1e-9))
        repo.upsert_portfolio_state(self.db, equity=equity, peak_equity=peak,
                                      cash=cash, positions=positions,
                                      realized_pnl=ps.get("realized_pnl", 0.0),
                                      unrealized_pnl=ps.get("unrealized_pnl", 0.0),
                                      daily_loss=daily_loss)
        # Also persist a memory experience record
        try:
            self.memory.write("16",  # Experience Memory
                                {"order_id": order.order_id, "side": order.side,
                                 "instrument": order.instrument, "size": size,
                                 "price": price, "cycle_id": order.cycle_id},
                                agent_id="orchestrator",
                                meta={"kind": "fill"})
        except Exception:
            pass
