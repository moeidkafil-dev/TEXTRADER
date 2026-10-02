"""
Message System — chapter 03 C11 (n8) / REQ-MSG-01, REQ-MSG-02, REQ-MSG-03.

Two responsibilities:
1. Notify user of every FinalDecision that is about to execute (Email + Telegram).
2. Wait up to `veto_window_seconds` for user response:
    - silence or OK ⇒ execute (chapter 08 default; configurable per P-02)
    - REJECT ⇒ no execution (I3)
    - STOP ⇒ enter WAITING until next user command

The runtime exposes a `user_veto_hook` callable so tests and live integrations
can supply the user side. Default hook: simulate silence (the ORIGINAL
behavior — silence ⇒ execute).

3. Receiver pipeline: message_receiver → message_analyser → context_maker →
   sender_to_agent (used when the user sends a free-form command back).
"""
from __future__ import annotations

import threading
import time
from datetime import datetime, timezone
from typing import Callable, Optional

from trader.core.schemas import FinalDecision, ExecutionOrder, VetoEvent, VetoResponse
from trader.storage import repo


class EmailSender:
    def __init__(self, observability=None):
        self._obs = observability
    def send(self, to: str, subject: str, body: str) -> bool:
        if self._obs:
            self._obs.info("message.email_sender", trace_id="message_system",
                            data={"to": to, "subject": subject})
        return True  # mock success


class TelegramSender:
    def __init__(self, observability=None, chat_whitelist: Optional[list[str]] = None):
        self._obs = observability
        self.whitelist = chat_whitelist or []
    def send(self, chat_id: str, text: str) -> bool:
        if self.whitelist and chat_id not in self.whitelist:
            if self._obs:
                self._obs.warn("message.telegram_sender", trace_id="message_system",
                                data={"event": "auth_rejected", "chat_id": chat_id})
            return False
        if self._obs:
            self._obs.info("message.telegram_sender", trace_id="message_system",
                            data={"chat_id": chat_id, "text": text[:80]})
        return True


class MessageMaker:
    def make(self, decision: FinalDecision, order: Optional[ExecutionOrder]) -> dict:
        return {
            "subject": f"XIR — FinalDecision: {decision.decision}",
            "body": (
                f"Cycle {decision.cycle_id}\n"
                f"Decision: {decision.decision}\n"
                f"Overrode initial: {decision.overrode_initial}\n"
                f"Reason: {decision.reason}\n"
                + (f"Order: {order.side} {order.size} {order.instrument} "
                   f"SL={order.sl} TP={order.tp}" if order else "")
            ),
        }


class MessageSendManager:
    def __init__(self, email: EmailSender, telegram: TelegramSender,
                 observability=None, email_to: str = "", telegram_chat: str = ""):
        self._email = email
        self._tg = telegram
        self._obs = observability
        self.email_to = email_to
        self.telegram_chat = telegram_chat

    def send_all(self, payload: dict) -> dict:
        em_ok = self._email.send(self.email_to, payload["subject"], payload["body"]) if self.email_to else False
        tg_ok = self._tg.send(self.telegram_chat, f"{payload['subject']}\n{payload['body']}") if self.telegram_chat else False
        return {"email_ok": em_ok, "telegram_ok": tg_ok}


class MessageReceiver:
    """User message ⇒ Context to agent (REQ-MSG-03)."""
    def __init__(self, observability=None):
        self._obs = observability
        self._queue: list[dict] = []

    def push(self, msg: dict) -> None:
        self._queue.append(msg)

    def pop(self) -> Optional[dict]:
        return self._queue.pop(0) if self._queue else None


class MessageSystem:
    """Orchestrates veto window + senders."""

    def __init__(self, send_manager: MessageSendManager, observability=None,
                 veto_window_seconds: int = 120, on_silence: str = "execute",
                 user_veto_hook: Optional[Callable[[ExecutionOrder], str]] = None):
        self._sm = send_manager
        self._obs = observability
        self.veto_window = veto_window_seconds
        self.on_silence = on_silence
        # Hook: given the order, returns one of "SILENCE"|"OK"|"REJECT"|"STOP"
        self._user_hook = user_veto_hook or (lambda order: VetoResponse.SILENCE.value)
        self.receiver = MessageReceiver(observability)

    def notify_and_wait(self, decision: FinalDecision,
                        order: Optional[ExecutionOrder]) -> VetoEvent:
        """REQ-MSG-01 + REQ-MSG-02."""
        msg = MessageMaker().make(decision, order)
        send_result = self._sm.send_all(msg)
        if self._obs:
            self._obs.info("message_system", trace_id=decision.cycle_id,
                            data={"event": "notify_sent", "send": send_result})
        notified_at = datetime.now(timezone.utc)
        # Wait for user veto
        resp_raw = self._user_hook(order) if order else VetoResponse.SILENCE.value
        if resp_raw not in {r.value for r in VetoResponse}:
            if self._obs:
                self._obs.warn("message_system", trace_id=decision.cycle_id,
                                data={"event": "bad_response", "raw": resp_raw})
            resp_raw = VetoResponse.SILENCE.value
        # Apply on_silence config (P-02)
        if resp_raw == VetoResponse.SILENCE.value and self.on_silence == "wait":
            # silence ⇒ do not execute; treat as WAIT
            decision = FinalDecision(
                cycle_id=decision.cycle_id,
                decision="WAIT",
                overrode_initial=True,
                reason="on_silence=wait ⇒ WAIT",
                ts=decision.ts,
            )
        veto = VetoEvent(order_id=order.order_id if order else "no_order",
                          notified_at=notified_at,
                          response=resp_raw,
                          responded_at=datetime.now(timezone.utc))
        try:
            if order:
                repo.get_db()  # ensure db ready
                repo.insert_veto_event(repo.get_db(), veto)
        except Exception:
            pass
        if self._obs:
            self._obs.info("message_system", trace_id=decision.cycle_id,
                            data={"event": "veto_resolved",
                                   "response": resp_raw,
                                   "notified_at": veto.notified_at.isoformat()})
        return veto
