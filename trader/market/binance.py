"""Public Binance market-data adapter. No credentials are required for reads."""
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


class BinanceMarketClient:
    def __init__(self, base_url: str | None = None, timeout: float = 10.0):
        # Explicit constructor value wins; otherwise allow deployments/tests to
        # select a compatible public Binance endpoint without changing code.
        self.base_url = (base_url or os.getenv("BINANCE_BASE_URL") or "https://api.binance.com").rstrip("/")
        self.timeout = timeout

    def _get(self, path: str, params: dict[str, Any]) -> Any:
        query = urllib.parse.urlencode(params)
        req = urllib.request.Request(
            f"{self.base_url}{path}?{query}",
            headers={"User-Agent": "TRADER-XIR/2.0", "Accept": "application/json"},
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=self.timeout, context=ssl.create_default_context()) as r:
            return json.loads(r.read().decode("utf-8"))

    @staticmethod
    def symbol(symbol: str) -> str:
        return symbol.replace("/", "").replace("-", "").upper()

    def ticker(self, symbol: str) -> dict[str, Any]:
        return self._get("/api/v3/ticker/24hr", {"symbol": self.symbol(symbol)})

    def depth(self, symbol: str, limit: int = 20) -> dict[str, Any]:
        return self._get("/api/v3/depth", {"symbol": self.symbol(symbol), "limit": limit})

    def klines(self, symbol: str, interval: str = "1m", limit: int = 200) -> list[list[Any]]:
        return self._get("/api/v3/klines", {"symbol": self.symbol(symbol), "interval": interval, "limit": limit})

    def snapshot(self, symbol: str, interval: str = "1m", limit: int = 100) -> dict[str, Any]:
        ticker = self.ticker(symbol)
        depth = self.depth(symbol, 20)
        # Ask for one extra bar and exclude the currently forming candle.
        # Binance kline responses identify each bar by open time and close time;
        # using only closed bars avoids look-ahead/partial-candle contamination.
        raw_klines = self.klines(symbol, interval, min(1000, limit + 1))
        now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
        klines = [k for k in raw_klines if len(k) >= 7 and int(k[6]) < now_ms]
        klines = klines[-limit:]
        if not klines:
            raise ValueError(f"no closed klines returned for {symbol}")
        return {"ticker": ticker, "depth": depth, "klines": klines}


class BinancePublicSource(DataSource):
    """Converts live public Binance REST data into XIR DataBundles."""
    def __init__(self, instruments: list[str], interval: str = "1m", limit: int = 100,
                 client: BinanceMarketClient | None = None):
        self.instruments = instruments
        self.interval = interval
        self.limit = limit
        self.client = client or BinanceMarketClient()

    @staticmethod
    def _missing_bundles(instrument: str, timestamp: datetime, error: Exception) -> list[DataBundle]:
        message = f"{type(error).__name__}: {error}"
        payload = {"instrument": instrument, "error": message}
        return [
            DataBundle("binance://rest/market", timestamp, "missing", payload, hash="missing"),
            DataBundle("binance://rest/orderbook", timestamp, "missing", payload, hash="missing"),
        ]

    def fetch(self, cycle_id: str) -> list[DataBundle]:
        ts = datetime.now(timezone.utc)
        bundles: list[DataBundle] = []
        for inst in self.instruments:
            try:
                snap = self.client.snapshot(inst, self.interval, self.limit)
                ticker = snap["ticker"]
                klines = snap["klines"]
                last = float(ticker["lastPrice"])
                payload = {
                    "instrument": inst,
                    "ohlcv": {
                        "open": float(klines[-1][1]),
                        "high": float(klines[-1][2]),
                        "low": float(klines[-1][3]),
                        "close": float(klines[-1][4]),
                        "volume": float(klines[-1][5]),
                    },
                    "market": {
                        "last": last,
                        "bid": float(ticker["bidPrice"]),
                        "ask": float(ticker["askPrice"]),
                        "change_pct": float(ticker["priceChangePercent"]),
                        "volume_24h": float(ticker["volume"]),
                    },
                    "history": [
                        {"ts": int(k[0]), "open": float(k[1]), "high": float(k[2]),
                         "low": float(k[3]), "close": float(k[4]), "volume": float(k[5])}
                        for k in klines
                    ],
                }
                bundles.append(DataBundle("binance://rest/market", ts, "ok", payload, hash=sha256_of(payload)))
                book_payload = {
                    "instrument": inst,
                    "order_book": {
                        "bids": [[float(p), float(q)] for p, q in snap["depth"]["bids"]],
                        "asks": [[float(p), float(q)] for p, q in snap["depth"]["asks"]],
                    },
                }
                bundles.append(DataBundle("binance://rest/orderbook", ts, "ok", book_payload,
                                          hash=sha256_of(book_payload)))
            except Exception as exc:
                # Public data failures are data-quality failures, not fabricated
                # market values. Preserve the instrument and source so Context
                # Maker can fail closed while other instruments can still proceed.
                bundles.extend(self._missing_bundles(inst, ts, exc))
        return bundles
