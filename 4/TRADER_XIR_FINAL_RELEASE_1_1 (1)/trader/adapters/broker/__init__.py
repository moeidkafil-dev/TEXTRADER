"""Broker adapters — chapter 03 C16."""
from trader.adapters.broker.base import BrokerAdapter, BrokerError, OrderRequest, BrokerAck
from trader.adapters.broker.mock import MockBroker

__all__ = ["BrokerAdapter", "BrokerError", "OrderRequest", "BrokerAck", "MockBroker", "get_broker"]


def get_broker(name: str, **kwargs) -> BrokerAdapter:
    if name == "mock":
        return MockBroker(**kwargs)
    raise KeyError(f"Unknown broker: {name!r}")
