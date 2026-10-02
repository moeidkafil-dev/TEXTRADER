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


class BrokerAdapter(ABC):
    name: str = "base"
    is_live: bool = False  # real venue adapters MUST set this True

    @abstractmethod
    def submit_order(self, order) -> BrokerAck:
        raise NotImplementedError
