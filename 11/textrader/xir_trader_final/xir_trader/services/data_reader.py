"""
C01 Data Reader — REQ-DR-01, REQ-DR-02.

Constraint: no data is fabricated or guessed; every bundle carries a
timestamp and a source, and unavailable sources are recorded explicitly
as missing_data (not silently skipped) — this also feeds Agent 2's F3
(missing_data) category later in the cycle.
"""
from __future__ import annotations

import hashlib
import json
import math
import time
from typing import Iterable

from ..core.schemas import DataBundle
from ..adapters.data.base import DataSourceAdapter, DataUnavailable
from .db_manager import DBManager
from .observability import Observability


class DataReader:
    def __init__(self, adapters: Iterable[DataSourceAdapter], db: DBManager, obs: Observability,
                 max_age_seconds: int = 60, clock=time.time):
        self.adapters = list(adapters)
        self.db = db
        self.obs = obs
        self.max_age_seconds = max_age_seconds
        self.clock = clock

    def _quality(self, adapter: DataSourceAdapter, payload, received_at: float,
                 instrument: str) -> tuple[str, float]:
        if not isinstance(payload, dict):
            return "INVALID", received_at
        source_ts = payload.get("timestamp", payload.get("ts"))
        if not isinstance(source_ts, (int, float)) or isinstance(source_ts, bool) or not math.isfinite(source_ts):
            return "INVALID", received_at
        if payload.get("instrument", instrument) != instrument:
            return "INVALID", float(source_ts)
        age = received_at - source_ts
        if age < -5:
            return "INVALID", float(source_ts)
        if age > self.max_age_seconds:
            return "STALE", float(source_ts)
        if (getattr(adapter, "critical", False) or adapter.name == "mock_price_ohlcv"
                or {"open", "high", "low", "close"}.intersection(payload)):
            required = ("open", "high", "low", "close", "volume")
            values = [payload.get(key) for key in required]
            if any(not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value) for value in values):
                return "INVALID", float(source_ts)
            open_, high, low, close, volume = (float(payload[key]) for key in required)
            if min(open_, high, low, close) <= 0 or volume < 0 or high < max(open_, close) or low > min(open_, close) or low > high:
                return "INVALID", float(source_ts)
            return "VALID", float(source_ts)
        if {"bid", "ask", "bid_size", "ask_size"}.intersection(payload):
            quote = [payload.get(key) for key in ("bid", "ask", "bid_size", "ask_size")]
            if any(not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value) or value <= 0
                   for value in quote):
                return "INVALID", float(source_ts)
            bid, ask, bid_size, ask_size = (float(payload[key]) for key in ("bid", "ask", "bid_size", "ask_size"))
            if ask < bid:
                return "INVALID", float(source_ts)
        if not payload:
            return "MISSING", float(source_ts)
        # Optional feeds may be partial; the mandatory price feed is validated separately.
        return "VALID" if payload else "MISSING", float(source_ts)

    def read_all(self, instrument: str, cycle_id: str, trace_id: str) -> list[DataBundle]:
        bundles: list[DataBundle] = []
        for adapter in self.adapters:
            received_at = self.clock()
            try:
                payload = adapter.fetch(instrument)
            except DataUnavailable as e:
                payload = {"error": str(e)}
                quality = "MISSING"
                self.obs.warn(trace_id, msg=f"data source unavailable: {adapter.name}", error=str(e))
            except Exception as e:
                payload = {"error_type": type(e).__name__, "error": "provider fetch failed"}
                quality = "MISSING"
                self.obs.error(trace_id, msg=f"data source failure: {adapter.name}", error_type=type(e).__name__)
            else:
                quality, source_ts = self._quality(adapter, payload, self.clock(), instrument)
                received_at = source_ts if math.isfinite(source_ts) else received_at

            raw = json.dumps(payload, sort_keys=True, default=str).encode()
            bundle = DataBundle(
                source=adapter.name,
                timestamp=received_at,
                quality=quality,
                payload=payload,
                hash=hashlib.sha256(raw).hexdigest(),
                critical=bool(getattr(adapter, "critical", False)),
            )
            bundle.cycle_id = cycle_id  # type: ignore[attr-defined]
            self.db.save_data_bundle(bundle)  # REQ-DR-02: persisted before Context Maker sees it
            bundles.append(bundle)

        self.obs.info(trace_id, msg="data_read_complete", n_bundles=len(bundles),
                      n_invalid=sum(1 for b in bundles if b.quality in ("INVALID", "MISSING", "STALE")))
        return bundles
