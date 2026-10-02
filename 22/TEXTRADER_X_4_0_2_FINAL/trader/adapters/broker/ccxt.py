"""Optional CCXT execution adapter.

Disabled unless the operator explicitly selects a live broker and provides
credentials through environment variables. Never logs credentials.
"""
from __future__ import annotations

import os
from trader.adapters.broker.base import BrokerAck, BrokerError, OrderRequest


class CCXTBroker:
    name = "ccxt"

    def __init__(self, exchange_name: str | None = None):
        try:
            import ccxt  # type: ignore
        except ImportError as e:
            raise RuntimeError("Live execution requires optional dependency: pip install -e '.[live]'") from e
        self._ccxt = ccxt
        self.exchange_name = (exchange_name or os.getenv("XIR_EXCHANGE", "binance")).lower()
        cls = getattr(ccxt, self.exchange_name, None)
        if cls is None:
            raise ValueError(f"Unsupported CCXT exchange: {self.exchange_name}")
        key = os.getenv("XIR_API_KEY", "")
        secret = os.getenv("XIR_API_SECRET", "")
        if not key or not secret:
            raise RuntimeError("Live broker requires XIR_API_KEY and XIR_API_SECRET")
        self.exchange = cls({"apiKey": key, "secret": secret, "enableRateLimit": True})
        if os.getenv("XIR_TESTNET", "0") == "1" and hasattr(self.exchange, "set_sandbox_mode"):
            self.exchange.set_sandbox_mode(True)

    def ping(self) -> bool:
        self.exchange.load_markets()
        return True

    def submit(self, order: OrderRequest) -> BrokerAck:
        try:
            symbol = order.instrument.replace("/", "/")
            side = order.side.lower()
            result = self.exchange.create_order(symbol, "market", side, order.size)
            return BrokerAck(ok=True, broker_order_id=str(result.get("id", "")),
                             fill_price=result.get("average") or result.get("price"),
                             fill_size=result.get("filled") or order.size,
                             status="filled" if result.get("status") == "closed" else "submitted",
                             reason="ccxt order accepted")
        except Exception as e:
            return BrokerAck(ok=False, status="rejected", reason=f"ccxt error: {e}")

    def cancel(self, broker_order_id: str) -> bool:
        try:
            self.exchange.cancel_order(broker_order_id)
            return True
        except Exception:
            return False
