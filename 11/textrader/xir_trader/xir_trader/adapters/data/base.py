"""
Data source adapter interface. Real venues (exchange REST/WS feeds, news
APIs, economic calendars, portfolio/position sources) implement this;
the mock adapter (mock.py) is the only one wired in by default.
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class DataSourceAdapter(ABC):
    name: str = "base"

    @abstractmethod
    def fetch(self, instrument: str) -> dict:
        """Return a raw payload dict for this source. Must never fabricate values —
        if data can't be obtained, raise DataUnavailable (REQ-DR-01 constraint)."""
        raise NotImplementedError


class DataUnavailable(RuntimeError):
    pass
