"""
Source connectors — the single, uniform on-ramp for "everything external".

Design goal (per owner request): whenever the system needs a new outside
source of information — a data vendor, a news feed, a broker, a research
paper, an arbitrary webpage — the owner should only ever have to supply
EITHER (a) an API key + base URL, OR, at minimum, (b) a plain URL, and the
system plugs it in without a code rewrite.

A `SourceConnector` is a small, named, persisted record:

    - api mode:  name, base_url, api_key_env (env var holding the secret —
                 keys are never written to disk in plaintext), optional
                 default headers/params.
    - url mode:  name, url only. Used for "go read this and figure out what's
                 ambiguous" cases — fetches the page and returns cleaned text
                 for the research/knowledge layer to consume.

Connectors are stored in config/connectors.yaml and are NOT wired into any
one module — anything (research engine, data reader, knowledge base) can look
one up by name via `get_connector(name)` and call `.fetch(...)`.

Stdlib-only (urllib + html.parser): no extra dependency is ever required just
to add a new source.
"""
from __future__ import annotations

import json
import os
import urllib.request
import urllib.error
import urllib.parse
from dataclasses import dataclass, field, asdict
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Optional

try:
    import yaml  # type: ignore
except ImportError:  # pragma: no cover
    yaml = None

CONNECTORS_PATH = Path(os.environ.get("TRADER_CONFIG_DIR", "config")) / "connectors.yaml"


class _TextExtractor(HTMLParser):
    """Minimal, dependency-free HTML → plain text (no bs4/lxml required)."""

    _SKIP = {"script", "style", "noscript"}

    def __init__(self) -> None:
        super().__init__()
        self._skip_depth = 0
        self.chunks: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in self._SKIP:
            self._skip_depth += 1

    def handle_endtag(self, tag):
        if tag in self._SKIP and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data):
        if not self._skip_depth:
            text = data.strip()
            if text:
                self.chunks.append(text)

    def text(self) -> str:
        return "\n".join(self.chunks)


@dataclass
class SourceConnector:
    name: str
    mode: str  # "api" | "url"
    base_url: str = ""            # api mode: base endpoint
    url: str = ""                 # url mode: fixed page/feed to fetch
    api_key_env: str = ""         # env var name holding the secret (never the key itself)
    headers: dict[str, str] = field(default_factory=dict)
    purpose: str = "research"     # free-text tag: research | market_data | news | broker | custom
    timeout_seconds: float = 20.0

    def _api_key(self) -> str | None:
        return os.getenv(self.api_key_env) if self.api_key_env else None

    def fetch(self, path: str = "", *, params: Optional[dict] = None,
              query: Optional[str] = None) -> dict[str, Any]:
        """Uniform entry point regardless of mode.

        - api mode: GET f"{base_url}{path}" with api key + params, JSON parsed.
        - url mode: GET the fixed url (query/params ignored beyond suffixing),
          HTML stripped to plain text for the research layer.
        """
        if self.mode == "api":
            if not self.base_url:
                raise ValueError(f"connector {self.name!r}: base_url is required in api mode")
            url = self.base_url.rstrip("/") + path
            if params:
                url += ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
            headers = dict(self.headers)
            key = self._api_key()
            if key:
                headers.setdefault("Authorization", f"Bearer {key}")
            raw, content_type = self._get(url, headers)
            if "json" in content_type or not content_type:
                try:
                    return {"connector": self.name, "mode": "api", "url": url, "data": json.loads(raw)}
                except json.JSONDecodeError:
                    pass
            return {"connector": self.name, "mode": "api", "url": url, "data": raw}

        if self.mode == "url":
            target = self.url
            if query:
                target += ("&" if "?" in target else "?") + urllib.parse.urlencode({"q": query})
            raw, content_type = self._get(target, dict(self.headers))
            if "html" in content_type:
                parser = _TextExtractor()
                parser.feed(raw)
                text = parser.text()
            else:
                text = raw
            return {"connector": self.name, "mode": "url", "url": target, "text": text[:20000]}

        raise ValueError(f"connector {self.name!r}: unknown mode {self.mode!r}")

    def _get(self, url: str, headers: dict[str, str]) -> tuple[str, str]:
        req = urllib.request.Request(url, headers={"User-Agent": "textrader-source-connector/1.0", **headers})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
                content_type = resp.headers.get("Content-Type", "").lower()
                return resp.read().decode("utf-8", errors="replace"), content_type
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"connector {self.name!r}: HTTP {e.code} for {url}") from e
        except urllib.error.URLError as e:
            raise RuntimeError(f"connector {self.name!r}: connection failed for {url}: {e.reason}") from e

    def ping(self) -> dict[str, Any]:
        try:
            out = self.fetch()
            return {"connector": self.name, "ok": True,
                     "preview": str(out.get("data", out.get("text", "")))[:200]}
        except Exception as e:  # noqa: BLE001
            return {"connector": self.name, "ok": False, "error": str(e)}


# ----------------------------------------------------------------------------
# Registry / persistence — connectors survive across CLI and web-panel use
# ----------------------------------------------------------------------------

def load_connectors(path: Path | None = None) -> dict[str, SourceConnector]:
    p = path or CONNECTORS_PATH
    if yaml is None or not p.exists():
        return {}
    with open(p, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    out: dict[str, SourceConnector] = {}
    for name, spec in (data.get("connectors") or {}).items():
        out[name] = SourceConnector(name=name, **{k: v for k, v in spec.items() if k != "name"})
    return out


def save_connectors(connectors: dict[str, SourceConnector], path: Path | None = None) -> None:
    if yaml is None:
        raise RuntimeError("PyYAML not installed; install with: pip install pyyaml")
    p = path or CONNECTORS_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    payload = {"connectors": {name: {k: v for k, v in asdict(c).items() if k != "name"}
                               for name, c in connectors.items()}}
    with open(p, "w", encoding="utf-8") as f:
        yaml.safe_dump(payload, f, allow_unicode=True, sort_keys=False)


def add_connector(connector: SourceConnector, path: Path | None = None) -> None:
    connectors = load_connectors(path)
    connectors[connector.name] = connector
    save_connectors(connectors, path)


def get_connector(name: str, path: Path | None = None) -> SourceConnector:
    connectors = load_connectors(path)
    if name not in connectors:
        raise KeyError(f"connector {name!r} not found. Known: {sorted(connectors)}")
    return connectors[name]


def remove_connector(name: str, path: Path | None = None) -> None:
    connectors = load_connectors(path)
    connectors.pop(name, None)
    save_connectors(connectors, path)
