"""Source-aware research registry.

This is deliberately provider-neutral: sources are explicit, timestamped and
traceable. The trading engine never treats an unverified web result as fact.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Iterable
from urllib.parse import urlparse


@dataclass(frozen=True)
class SourceRecord:
    name: str
    url: str
    category: str
    reliability: str = "reference"
    fetched_at: str = ""

    def to_dict(self):
        return asdict(self)


DEFAULT_SOURCES = (
    SourceRecord("Binance API Docs", "https://developers.binance.com/docs/binance-spot-api-docs", "exchange"),
    SourceRecord("CCXT Manual", "https://docs.ccxt.com/", "exchange-integration"),
    SourceRecord("SEC Investor Publications", "https://www.sec.gov/investor", "regulatory"),
    SourceRecord("CFTC", "https://www.cftc.gov/", "regulatory"),
    SourceRecord("Federal Reserve", "https://www.federalreserve.gov/", "macro"),
    SourceRecord("arXiv", "https://arxiv.org/", "research"),
)


def validate_sources(records: Iterable[SourceRecord]) -> list[SourceRecord]:
    out = []
    for r in records:
        p = urlparse(r.url)
        if p.scheme not in {"http", "https"} or not p.netloc:
            continue
        out.append(SourceRecord(r.name, r.url, r.category, r.reliability,
                                r.fetched_at or datetime.now(timezone.utc).isoformat()))
    return out
