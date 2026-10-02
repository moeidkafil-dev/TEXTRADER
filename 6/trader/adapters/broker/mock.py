"""
Mock broker — paper-mode trading simulator.

Simulates order fills against the supplied price tick. Slippage is small and
deterministic (0.05% adverse). No real funds, no network calls. Used for all
paper-mode and backtest runs.
"""
from __future__ import annotations

import math
import random
from datetime import datetime
from typing import Optional

from trader.adapters.broker.base import BrokerAdapter, BrokerAck, OrderRequest


class MockBroker:
    name = "mock"

    def __init__(self, *, slippage_bps: float = 5.0, seed: int = 7,
                 price_feed: Optional[callable] = None):
        self.slippage = slippage_bps / 10_000.0
        self._rng = random.Random(seed)
        self._price_feed = price_feed  # callable: () -> dict[instrument -> price]
        self._open: dict[str, OrderRequest] = {}

    def ping(self) -> bool:
        return True

    def submit(self, order: OrderRequest) -> BrokerAck:
        if order.size <= 0:
            return BrokerAck(ok=False, status="rejected", reason="size<=0")
        # idempotency: a second submit with same key returns the same ack
        for existing in self._open.values():
            if existing.idempotency_key == order.idempotency_key:
                return BrokerAck(ok=True, broker_order_id=existing.order_id,
                                  status="submitted",
                                  reason="idempotent re-submit ignored")
        price = self._quote(order.instrument)
        if price is None or math.isnan(price) or price <= 0:
            return BrokerAck(ok=False, status="rejected", reason="no_price")
        slip = self.slippage * (1 if order.side == "BUY" else -1)
        fill_price = round(price * (1 + slip), 6)
        fill_size = order.size
        self._open[order.order_id] = order
        return BrokerAck(
            ok=True,
            broker_order_id=order.order_id,
            fill_price=fill_price,
            fill_size=fill_size,
            status="filled",
            reason="mock fill",
        )

    def cancel(self, broker_order_id: str) -> bool:
        return self._open.pop(broker_order_id, None) is not None

    def _quote(self, instrument: str) -> Optional[float]:
        if self._price_feed is not None:
            book = self._price_feed()
            return book.get(instrument)
        # deterministic synthetic price for tests
        return 100.0 + (self._rng.random() * 5.0)
