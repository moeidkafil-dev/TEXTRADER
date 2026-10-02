"""
Broker adapter interface — one adapter per venue (P-06: "Adapter مجزا
برای هر بازار"). A real venue adapter implements this and reads its
credentials only from environment variables (SECURITY_MODEL.md).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class BrokerAck:
    order_id: str
    idempotency_key: str
    status: str          # "filled" | "rejected" | "duplicate"
    detail: str = ""


class Broker(ABC):
    name: str = "base"
    is_live: bool = False  # real venue adapters MUST set this True

    @abstractmethod
    def submit_order(self, order) -> BrokerAck:
        raise NotImplementedError


class ExecutionAdapter(ABC):
    """Normalized execution boundary used by the protective execution guard."""

    @abstractmethod
    def execute(self, order) -> BrokerAck:
        raise NotImplementedError


class BrokerAdapter(Broker, ExecutionAdapter):
    """Broker contract with a normalized execution method for adapter portability."""

    def execute(self, order) -> BrokerAck:
        return self.submit_order(order)
