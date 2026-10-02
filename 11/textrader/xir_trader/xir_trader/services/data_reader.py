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
import time
from typing import Iterable

from ..core.schemas import DataBundle
from ..adapters.data.base import DataSourceAdapter, DataUnavailable
from .db_manager import DBManager
from .observability import Observability


class DataReader:
    def __init__(self, adapters: Iterable[DataSourceAdapter], db: DBManager, obs: Observability):
        self.adapters = list(adapters)
        self.db = db
        self.obs = obs

    def read_all(self, instrument: str, cycle_id: str, trace_id: str) -> list[DataBundle]:
        bundles: list[DataBundle] = []
        for adapter in self.adapters:
            try:
                payload = adapter.fetch(instrument)
                quality = "ok"
            except DataUnavailable as e:
                payload = {"error": str(e)}
                quality = "missing"
                self.obs.warn(trace_id, msg=f"data source unavailable: {adapter.name}", error=str(e))

            raw = json.dumps(payload, sort_keys=True, default=str).encode()
            bundle = DataBundle(
                source=adapter.name,
                timestamp=time.time(),
                quality=quality,
                payload=payload,
                hash=hashlib.sha256(raw).hexdigest(),
            )
            bundle.cycle_id = cycle_id  # type: ignore[attr-defined]
            self.db.save_data_bundle(bundle)  # REQ-DR-02: persisted before Context Maker sees it
            bundles.append(bundle)

        self.obs.info(trace_id, msg="data_read_complete", n_bundles=len(bundles),
                      n_missing=sum(1 for b in bundles if b.quality == "missing"))
        return bundles
