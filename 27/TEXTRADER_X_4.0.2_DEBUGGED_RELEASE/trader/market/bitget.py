"""Public Bitget market-data adapter.

READ-ONLY by design: this module exposes only public GET market-data endpoints.
It never accepts credentials and never calls a trading/order endpoint.
"""
from __future__ import annotations

import json
import os
import ssl
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any

from trader.core.schemas import DataBundle
from trader.core.util import sha256_of
from trader.services.data_reader import DataSource


_INTERVAL_MS = {
    "1m": 60_000,
    "3m": 180_000,
    "5m": 300_000,
    "15m": 900_000,
    "30m": 1_800_000,
    "1H": 3_600_000,
    "4H": 14_400_000,
    "6H": 21_600_000,
    "12H": 43_200_000,
    "1D": 86_400_000,
}


class BitgetMarketClient:
    """Read-only client for Bitget UTA public spot market-data endpoints."""

    def __init__(self, base_url: str | None = None, timeout: float = 10.0):
        self.base_url = (base_url or os.getenv("BITGET_BASE_URL") or "https://api.bitget.com").rstrip("/")
        self.timeout = timeout

    def _get(self, path: str, params: dict[str, Any]) -> Any:
        query = urllib.parse.urlencode(params)
        req = urllib.request.Request(
            f"{self.base_url}{path}?{query}",
            headers={"User-Agent": "TEXTRADER-X/4.0.2", "Accept": "application/json"},
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=self.timeout, context=ssl.create_default_context()) as r:
            payload = json.loads(r.read().decode("utf-8"))
        if not isinstance(payload, dict) or payload.get("code") != "00000":
            code = payload.get("code") if isinstance(payload, dict) else None
            msg = payload.get("msg") if isinstance(payload, dict) else "invalid response"
            raise ValueError(f"Bitget API error code={code!r}: {msg}")
        return payload

    @staticmethod
    def symbol(symbol: str) -> str:
        return symbol.replace("/", "").replace("-", "").upper()

    def ticker(self, symbol: str) -> dict[str, Any]:
        data = self._get("/api/v3/market/tickers", {
            "category": "SPOT", "symbol": self.symbol(symbol)
        }).get("data")
        if not isinstance(data, list) or not data:
            raise ValueError(f"no ticker returned for {symbol}")
        return data[0]

    def depth(self, symbol: str, limit: int = 20) -> dict[str, Any]:
        data = self._get("/api/v3/market/orderbook", {
            "category": "SPOT", "symbol": self.symbol(symbol), "limit": min(max(int(limit), 1), 1000)
        }).get("data")
        if not isinstance(data, dict):
            raise ValueError(f"no order book returned for {symbol}")
        return data

    def klines(self, symbol: str, interval: str = "1m", limit: int = 100) -> list[list[Any]]:
        if interval not in _INTERVAL_MS:
            raise ValueError(f"unsupported Bitget interval {interval!r}")
        data = self._get("/api/v3/market/candles", {
            "category": "SPOT", "symbol": self.symbol(symbol),
            "interval": interval, "limit": min(max(int(limit), 1), 1000)
        }).get("data")
        if not isinstance(data, list):
            raise ValueError(f"no candles returned for {symbol}")
        return data

    def snapshot(self, symbol: str, interval: str = "1m", limit: int = 100) -> dict[str, Any]:
        ticker = self.ticker(symbol)
        depth = self.depth(symbol, 20)
        raw = self.klines(symbol, interval, min(1000, limit + 2))
        interval_ms = _INTERVAL_MS[interval]
        now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)

        closed: list[list[Any]] = []
        for k in raw:
            if len(k) < 7:
                continue
            try:
                start_ms = int(k[0])
                if start_ms + interval_ms <= now_ms:
                    closed.append(k)
            except (TypeError, ValueError):
                continue
        closed.sort(key=lambda k: int(k[0]))
        closed = closed[-limit:]
        if not closed:
            raise ValueError(f"no closed klines returned for {symbol}")

        asks = depth.get("a")
        bids = depth.get("b")
        if not isinstance(asks, list) or not isinstance(bids, list) or not asks or not bids:
            raise ValueError(f"empty order book returned for {symbol}")

        return {"ticker": ticker, "depth": {"asks": asks, "bids": bids, "ts": depth.get("ts")}, "klines": closed}


class BitgetPublicSource(DataSource):
    """Converts public Bitget REST market data into TEXTRADER DataBundles."""

    def __init__(self, instruments: list[str], interval: str = "1m", limit: int = 100,
                 client: BitgetMarketClient | None = None):
        self.instruments = instruments
        self.interval = interval
        self.limit = limit
        self.client = client or BitgetMarketClient()

    @staticmethod
    def _missing_bundles(instrument: str, timestamp: datetime, error: Exception) -> list[DataBundle]:
        message = f"{type(error).__name__}: {error}"
        payload = {"instrument": instrument, "error": message}
        return [
            DataBundle("bitget://rest/market", timestamp, "missing", payload, hash="missing"),
            DataBundle("bitget://rest/orderbook", timestamp, "missing", payload, hash="missing"),
        ]

    def fetch(self, cycle_id: str) -> list[DataBundle]:
        ts = datetime.now(timezone.utc)
        bundles: list[DataBundle] = []
        for inst in self.instruments:
            try:
                snap = self.client.snapshot(inst, self.interval, self.limit)
                ticker = snap["ticker"]
                klines = snap["klines"]
                depth = snap["depth"]
                last_bar = klines[-1]
                bids = [[float(p), float(q)] for p, q, *_ in depth["bids"]]
                asks = [[float(p), float(q)] for p, q, *_ in depth["asks"]]
                if not bids or not asks:
                    raise ValueError(f"empty order book returned for {inst}")
                if bids[0][0] > asks[0][0]:
                    raise ValueError(f"crossed order book for {inst}: bid={bids[0][0]} ask={asks[0][0]}")

                payload = {
                    "instrument": inst,
                    "ohlcv": {
                        "open": float(last_bar[1]), "high": float(last_bar[2]),
                        "low": float(last_bar[3]), "close": float(last_bar[4]),
                        "volume": float(last_bar[5]),
                    },
                    "market": {
                        "last": float(ticker["lastPrice"]),
                        "bid": float(ticker["bid1Price"]),
                        "ask": float(ticker["ask1Price"]),
                        "change_pct": float(ticker.get("price24hPcnt", 0.0)) * 100.0,
                        "volume_24h": float(ticker.get("volume24h", 0.0)),
                    },
                    "history": [
                        {"ts": int(k[0]), "open": float(k[1]), "high": float(k[2]),
                         "low": float(k[3]), "close": float(k[4]), "volume": float(k[5])}
                        for k in klines
                    ],
                }
                bundles.append(DataBundle("bitget://rest/market", ts, "ok", payload,
                                           hash=sha256_of(payload)))
                book_payload = {"instrument": inst, "order_book": {"bids": bids, "asks": asks}}
                bundles.append(DataBundle("bitget://rest/orderbook", ts, "ok", book_payload,
                                           hash=sha256_of(book_payload)))
            except Exception as exc:
                bundles.extend(self._missing_bundles(inst, ts, exc))
        return bundles
