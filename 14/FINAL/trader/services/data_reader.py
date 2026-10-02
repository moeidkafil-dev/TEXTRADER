"""
Data Reader — chapter 03 C01 (n0::n0) / REQ-DR-01, REQ-DR-02.

Reads ALL relevant market data: price, OHLCV, buy/sell stats, order book,
trades, indices, drops/gains, charts, news, economic data, portfolio, open
positions. The default source is a mock feed; a real source must implement
`DataSource.fetch(cycle_id) -> list[DataBundle]`.

Hard rule: never fabricate data. Every bundle has a timestamp and source.
A source being unreachable ⇒ the bundle is marked `quality="missing"` and
the Context Maker flags it (REQ-DR-01 failure handling).
"""
from __future__ import annotations

import math
import random
from datetime import datetime, timezone
from typing import Any, Callable, Optional

from trader.core.schemas import DataBundle
from trader.core.util import sha256_of


class DataSource:
    def fetch(self, cycle_id: str) -> list[DataBundle]:
        raise NotImplementedError


class MockOHLCVSource(DataSource):
    """Deterministic synthetic OHLCV source. Useful for paper mode + backtests."""

    def __init__(self, instruments: list[str], seed: int = 7,
                 base_price: float = 100.0, volatility: float = 0.01):
        self.instruments = instruments
        self._rng = random.Random(seed)
        self.base_price = base_price
        self.vol = volatility
        self._last_price: dict[str, float] = {k: base_price for k in instruments}
        # pre-seed some "news" + "economic" content
        self._news = ["Market consolidates near key support.",
                      "Volatility rises on macro uncertainty.",
                      "Sector rotation detected by momentum models."]

    def fetch(self, cycle_id: str) -> list[DataBundle]:
        ts = datetime.now(timezone.utc)
        bundles: list[DataBundle] = []
        for inst in self.instruments:
            p = self._tick(inst)
            ohlcv = {
                "open": round(p / (1 + self._rng.random() * self.vol), 4),
                "high": round(p * (1 + self._rng.random() * self.vol), 4),
                "low":  round(p * (1 - self._rng.random() * self.vol), 4),
                "close": round(p, 4),
                "volume": round(1000 + self._rng.random() * 5000, 2),
            }
            payload: dict[str, Any] = {"instrument": inst, "ohlcv": ohlcv}
            h = sha256_of(payload)
            bundles.append(DataBundle(source="mock://ohlcv", timestamp=ts,
                                       quality="ok", payload=payload, hash=h))
        # market stats / order book
        for inst in self.instruments:
            p = self._last_price[inst]
            book = {
                "bids": [[round(p * 0.999, 4), 100], [round(p * 0.998, 4), 200]],
                "asks": [[round(p * 1.001, 4), 100], [round(p * 1.002, 4), 200]],
            }
            payload = {"instrument": inst, "order_book": book}
            bundles.append(DataBundle(source="mock://orderbook", timestamp=ts,
                                       quality="ok", payload=payload,
                                       hash=sha256_of(payload)))
        # news
        payload = {"headlines": self._news[:2], "sentiment": self._rng.choice([-1, 0, 1])}
        bundles.append(DataBundle(source="mock://news", timestamp=ts,
                                    quality="ok", payload=payload,
                                    hash=sha256_of(payload)))
        # portfolio
        payload = {"cash": 100_000.0, "positions": {}, "equity": 100_000.0}
        bundles.append(DataBundle(source="mock://portfolio", timestamp=ts,
                                    quality="ok", payload=payload,
                                    hash=sha256_of(payload)))
        return bundles

    def _tick(self, inst: str) -> float:
        p = self._last_price[inst]
        p = max(1.0, p * (1 + (self._rng.random() - 0.5) * 2 * self.vol))
        self._last_price[inst] = p
        return p


class HistoricalReplaySource(DataSource):
    """Replays a list of pre-built bars. For backtest mode."""

    def __init__(self, bars: list[dict]):
        """bars: list of {instrument, open, high, low, close, volume, ts}."""
        self.bars = list(bars)
        self._i = 0

    def fetch(self, cycle_id: str) -> list[DataBundle]:
        if self._i >= len(self.bars):
            return [DataBundle(source="replay://end", timestamp=datetime.now(timezone.utc),
                                quality="missing", payload={"end": True}, hash="end")]
        bar = self.bars[self._i]
        self._i += 1
        ts = bar.get("ts") or datetime.now(timezone.utc).isoformat()
        if isinstance(ts, str):
            ts = datetime.fromisoformat(ts)
        payload = {"instrument": bar["instrument"], "ohlcv": {
            "open": bar["open"], "high": bar["high"],
            "low": bar["low"], "close": bar["close"],
            "volume": bar.get("volume", 1000),
        }}
        return [DataBundle(source="replay://ohlcv", timestamp=ts,
                            quality="ok", payload=payload,
                            hash=sha256_of(payload))]


class UnreachableSource(DataSource):
    """Used by failure-injection tests (TST-SYS-10). Always returns missing."""
    def __init__(self, name: str = "broken://source"):
        self.name = name
    def fetch(self, cycle_id: str) -> list[DataBundle]:
        return [DataBundle(source=self.name, timestamp=datetime.now(timezone.utc),
                            quality="missing", payload={"error": "unreachable"},
                            hash="missing")]


class DataReader:
    """Coordinates one or more data sources for a cycle."""

    def __init__(self, sources: list[DataSource], observability=None):
        self.sources = sources
        self._obs = observability

    def read(self, cycle_id: str) -> list[DataBundle]:
        all_bundles: list[DataBundle] = []
        for src in self.sources:
            try:
                bs = src.fetch(cycle_id)
            except Exception as e:
                if self._obs:
                    self._obs.error("data_reader", trace_id=cycle_id,
                                    data={"event": "source_error",
                                          "error": str(e)})
                bs = [DataBundle(source="unknown", timestamp=datetime.now(timezone.utc),
                                  quality="missing", payload={"error": str(e)},
                                  hash="missing")]
            all_bundles.extend(bs)
        if self._obs:
            self._obs.info("data_reader", trace_id=cycle_id,
                            data={"event": "read_done", "count": len(all_bundles),
                                   "missing": sum(1 for b in all_bundles if b.quality == "missing")})
        return all_bundles


def get_default_source(instruments: list[str]) -> DataSource:
    return MockOHLCVSource(instruments)
