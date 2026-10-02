"""
Mock broker — simulates fills with no real money and no network calls.
This is the ONLY broker adapter the CLI wires up by default (paper mode).
A real venue adapter is a separate, explicit choice by the operator.
"""
from __future__ import annotations

from .base import BrokerAdapter, BrokerAck


class MockBroker(BrokerAdapter):
    name = "mock_broker"
    is_live = False

    def __init__(self):
        self._seen_idempotency_keys: set[str] = set()
        self.filled_orders: list = []

    def submit_order(self, order) -> BrokerAck:
        if order.idempotency_key in self._seen_idempotency_keys:
            return BrokerAck(order.order_id, order.idempotency_key, "duplicate",
                              "idempotency key already submitted (P-04)")
        self._seen_idempotency_keys.add(order.idempotency_key)
        self.filled_orders.append(order)
        return BrokerAck(order.order_id, order.idempotency_key, "filled", "paper fill (simulated)")
