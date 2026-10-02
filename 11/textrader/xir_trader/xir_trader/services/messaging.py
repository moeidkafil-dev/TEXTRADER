"""
Message / Veto system — EXECUTION_MODEL.md:
  "پیام برای کاربر (Email + Telegram)؛ ۲ دقیقه: سکوت/OK ⇒ اجرا؛
   رد ⇒ عدم اجرا؛ stop/توقف ⇒ WAITING تا فرمان بعدی."

Channel adapters are stubs (console by default); wire real Telegram/Email
adapters behind the same NotificationChannel interface. Any inbound
"command" is authenticated against a whitelist (SECURITY_MODEL.md: "جعل
پیام کاربر" control) before being trusted.
"""
from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass

from ..core.schemas import VetoResponse
from .db_manager import DBManager
from .observability import Observability


class NotificationChannel(ABC):
    @abstractmethod
    def notify(self, message: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def poll_response(self, timeout_seconds: float) -> str | None:
        """Return 'OK' | 'REJECT' | 'STOP' | None (nothing received = silence)."""
        raise NotImplementedError


class ConsoleChannel(NotificationChannel):
    """Default dev/paper channel: prints the veto prompt; treats absence of
    stdin input within the window as silence (matches default on_silence=execute)."""
    def notify(self, message: str) -> None:
        print(f"\n[VETO WINDOW] {message}\n(reply OK / REJECT / STOP — silence = {{on_silence}})\n")

    def poll_response(self, timeout_seconds: float) -> str | None:
        # Non-interactive by default (no blocking stdin read in automated runs).
        # A real deployment wires TelegramChannel / EmailChannel here instead.
        return None


class AuthenticationError(RuntimeError):
    pass


@dataclass
class UserWhitelist:
    telegram_ids: tuple = ()
    email_addresses: tuple = ()

    def authenticate(self, sender: str, via: str) -> bool:
        if via == "telegram":
            return sender in self.telegram_ids
        if via == "email":
            return sender in self.email_addresses
        return False


class VetoSystem:
    def __init__(self, channels: list[NotificationChannel], db: DBManager, obs: Observability,
                 window_seconds: int = 120, on_silence: str = "execute"):
        self.channels = channels
        self.db = db
        self.obs = obs
        self.window_seconds = window_seconds
        self.on_silence = on_silence  # "execute" | "wait"  (P-02)

    def run_veto_window(self, order_id: str, message: str, trace_id: str,
                         clock=time.monotonic, sleep=time.sleep, fast_response: str | None = None) -> str:
        """Returns VetoResponse value. `fast_response` lets callers (tests, or a real
        channel that already has an answer) skip the sleep for deterministic testing."""
        notified_at = time.time()
        for ch in self.channels:
            ch.notify(message)
        self.obs.info(trace_id, msg="veto_window_opened", order_id=order_id, window_seconds=self.window_seconds)

        response = fast_response
        if response is None:
            start = clock()
            while clock() - start < self.window_seconds:
                for ch in self.channels:
                    r = ch.poll_response(timeout_seconds=1.0)
                    if r:
                        response = r
                        break
                if response:
                    break
                sleep(0.01)  # reference impl: short tick; real deployment would use an event/webhook

        if response is None:
            response = VetoResponse.SILENCE.value

        self.db.save_veto_event(order_id, notified_at, response)
        self.obs.info(trace_id, msg="veto_window_closed", order_id=order_id, response=response)
        self.obs.audit("veto_response", order_id=order_id, response=response)

        if response == VetoResponse.SILENCE.value:
            outcome = "execute" if self.on_silence == "execute" else "wait"
        elif response == VetoResponse.OK.value:
            outcome = "execute"
        else:  # REJECT or STOP
            outcome = "wait"
        return outcome
