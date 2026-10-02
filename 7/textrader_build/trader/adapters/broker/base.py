"""
Broker adapter base — chapter 08 EXECUTION_MODEL.

The adapter is pluggable (P-06): no broker is hard-coded into the runtime.
The default implementation is `MockBroker`, which simulates fills and never
touches real funds. Live adapters (Alpaca, Binance, ...) must subclass
`BrokerAdapter` and implement `submit` + `cancel`.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Protocol


@dataclass
class OrderRequest:
    order_id: str
    idempotency_key: str
    side: str           # BUY | SELL
    instrument: str
    size: float
    sl: float = 0.0
    tp: float = 0.0
    ts: datetime | None = None


@dataclass
class BrokerAck:
    ok: bool
    broker_order_id: str = ""
    fill_price: Optional[float] = None
    fill_size: Optional[float] = None
    status: str = ""    # "filled" | "submitted" | "rejected"
    reason: str = ""


class BrokerError(Exception):
    pass


class BrokerAdapter(Protocol):
    name: str

    def submit(self, order: OrderRequest) -> BrokerAck: ...

    def cancel(self, broker_order_id: str) -> bool: ...

    def ping(self) -> bool: ...
