"""Safe, auditable research facade.

Research is supplemental intelligence, never an execution authority. It stores
source metadata and requires explicit provider configuration for live fetching.
"""
from __future__ import annotations
import json, os, urllib.parse, urllib.request
from datetime import datetime, timezone
from .knowledge import DEFAULT_SOURCES, SourceRecord, validate_sources


class ResearchEngine:
    def __init__(self, timeout: float = 8.0):
        self.timeout = timeout
        self.sources = validate_sources(DEFAULT_SOURCES)

    def registry(self):
        return [s.to_dict() for s in self.sources]

    def fetch_url(self, url: str) -> dict:
        req = urllib.request.Request(url, headers={"User-Agent": "TEXTRADER-X/3.0"})
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            raw = r.read(200_000).decode("utf-8", errors="replace")
        return {"url": url, "fetched_at": datetime.now(timezone.utc).isoformat(), "bytes": len(raw), "content": raw}

    def search(self, query: str) -> dict:
        """Optional external search endpoint.

        Set TEXTRADER_SEARCH_URL to a trusted search service that accepts q=.
        Without it, return the registered authoritative source catalog rather
        than pretending an internet search happened.
        """
        endpoint = os.getenv("TEXTRADER_SEARCH_URL")
        if not endpoint:
            return {"query": query, "searched": False, "reason": "no_search_provider_configured",
                    "sources": self.registry()}
        url = endpoint + ("&" if "?" in endpoint else "?") + urllib.parse.urlencode({"q": query})
        return self.fetch_url(url)
