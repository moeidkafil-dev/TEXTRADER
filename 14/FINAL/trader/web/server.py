"""FastAPI control plane for TEXTRADER X.

The web layer is intentionally thin: it never makes trading decisions itself.
It accepts normalized/manual market snapshots, invokes the same Orchestrator used
by the CLI, and exposes an auditable decision trace to the admin UI.
"""
from __future__ import annotations

import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, ConfigDict, model_validator, field_validator

from trader.core.config import load_risk_config, load_trader_config
from trader.core.schemas import DataBundle
from trader.core.util import sha256_of
from trader.engine.orchestrator import Orchestrator
from trader.market.binance import BinancePublicSource
from trader.services.data_reader import DataSource

ROOT = Path(__file__).resolve().parent / "static"


class ManualMarketSource(DataSource):
    """Single-cycle source populated by the operator/API."""
    def __init__(self, bundles: list[DataBundle]):
        self.bundles = bundles

    def fetch(self, cycle_id: str) -> list[DataBundle]:
        return list(self.bundles)


class AnalyzeRequest(BaseModel):
    symbol: str = "BTC/USDT"
    source: str = Field(default="binance", pattern="^(binance|manual)$")
    interval: str = "1m"
    limit: int = Field(default=100, ge=10, le=1000)
    market: dict[str, Any] | None = None
    mode: str = Field(default="paper", pattern="^(paper|backtest)$")


class ManualDataRequest(BaseModel):
    """Professional manual market snapshot.

    The flat OHLCV/account fields remain backwards compatible with v3.1.x.
    Advanced sections are optional and are preserved as auditable bundles.
    """
    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    snapshot_id: str | None = None
    symbol: str = "BTC/USDT"
    exchange: str = "manual"
    timestamp: str | None = None
    timeframe: str = "1m"

    price: float | None = None
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0

    order_book: dict[str, Any] | None = None
    trades: dict[str, Any] | None = None
    derivatives: dict[str, Any] | None = None
    volatility: dict[str, Any] | None = None
    technical: dict[str, Any] | None = None
    sentiment: float = 0.0
    sentiment_detail: dict[str, Any] | None = None
    news: list[Any] = Field(default_factory=list)
    macro: dict[str, Any] | None = None
    onchain: dict[str, Any] | None = None

    equity: float = 100000.0
    cash: float = 100000.0
    positions: dict[str, Any] = Field(default_factory=dict)
    risk_limits: dict[str, Any] | None = None
    execution: dict[str, Any] | None = None
    data_quality: dict[str, Any] | None = None
    agent_context: dict[str, Any] | None = None

    @field_validator("timestamp")
    @classmethod
    def validate_timestamp(cls, value):
        if value:
            try:
                parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=timezone.utc)
            except ValueError as exc:
                raise ValueError("timestamp must be ISO-8601") from exc
        return value

    @model_validator(mode="after")
    def validate_snapshot(self):
        import math
        nums = {"open": self.open, "high": self.high, "low": self.low,
                "close": self.close, "volume": self.volume, "sentiment": self.sentiment,
                "equity": self.equity, "cash": self.cash}
        if self.price is not None:
            nums["price"] = self.price
        for name, value in nums.items():
            if not math.isfinite(value):
                raise ValueError(f"{name} must be finite")
        if self.high < max(self.open, self.close):
            raise ValueError("high must be >= open and close")
        if self.low > min(self.open, self.close):
            raise ValueError("low must be <= open and close")
        if self.volume < 0:
            raise ValueError("volume must be >= 0")
        if self.equity <= 0:
            raise ValueError("equity must be > 0")
        if self.cash < 0:
            raise ValueError("cash must be >= 0")
        if self.order_book:
            bids = self.order_book.get("bids", []) or []
            asks = self.order_book.get("asks", []) or []
            if not isinstance(bids, list) or not isinstance(asks, list):
                raise ValueError("order_book bids and asks must be arrays")
            for side_name, levels in (("bids", bids), ("asks", asks)):
                for level in levels:
                    if not isinstance(level, (list, tuple)) or len(level) < 2:
                        raise ValueError(f"order_book {side_name} levels must be [price, size]")
                    price, size = float(level[0]), float(level[1])
                    if not math.isfinite(price) or not math.isfinite(size) or price <= 0 or size < 0:
                        raise ValueError(f"order_book {side_name} contains invalid price/size")
            if bids and asks:
                best_bid = float(bids[0][0])
                best_ask = float(asks[0][0])
                if best_bid > best_ask:
                    raise ValueError("order_book best bid cannot exceed best ask")
        if self.data_quality and self.data_quality.get("completeness") is not None:
            completeness = float(self.data_quality["completeness"])
            if not 0 <= completeness <= 1:
                raise ValueError("data_quality.completeness must be between 0 and 1")
        return self


def _bundles_from_manual(d: ManualDataRequest) -> list[DataBundle]:
    ts = datetime.fromisoformat(d.timestamp.replace("Z", "+00:00")) if d.timestamp else datetime.now(timezone.utc)
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    instrument = d.symbol.upper().replace("-", "/")
    bundles: list[DataBundle] = []

    def add(source: str, payload: dict[str, Any], quality: str = "ok") -> None:
        bundles.append(DataBundle(source=source, timestamp=ts, quality=quality,
                                   payload=payload, hash=sha256_of(payload)))

    ohlcv = {"open": d.open, "high": d.high, "low": d.low, "close": d.close, "volume": d.volume}
    if d.price is not None:
        ohlcv["price"] = d.price
    add("manual://ohlcv", {"instrument": instrument, "ohlcv": ohlcv,
                            "exchange": d.exchange, "timeframe": d.timeframe})

    sections = {
        "orderbook": d.order_book, "trades": d.trades, "derivatives": d.derivatives,
        "volatility": d.volatility, "technical": d.technical, "macro": d.macro,
        "onchain": d.onchain, "execution": d.execution, "risk_limits": d.risk_limits,
        "data_quality": d.data_quality, "agent_context": d.agent_context,
    }
    for name, value in sections.items():
        if value is not None:
            payload_name = "order_book" if name == "orderbook" else name
            add(f"manual://{name}", {"instrument": instrument, payload_name: value})

    add("manual://news", {"instrument": instrument, "headlines": d.news,
                           "sentiment": d.sentiment, "sentiment_detail": d.sentiment_detail})
    add("manual://portfolio", {"instrument": instrument, "cash": d.cash,
                                "positions": d.positions, "equity": d.equity})
    return bundles


class ControlPlane:
    def __init__(self, default_symbol: str):
        self.lock = threading.RLock()
        self.default_symbol = default_symbol
        self.history: list[dict[str, Any]] = []
        self.last_market: dict[str, Any] | None = None
        self.last_result: dict[str, Any] | None = None
        self.orch = self._build(default_symbol)

    def _build(self, symbol: str, source=None):
        tc = load_trader_config()
        rc = load_risk_config()
        tc.instruments = [symbol]
        tc.mode = "paper"
        return Orchestrator(rc, tc, data_source=source or BinancePublicSource([symbol], interval="1m", limit=100))

    def analyze(self, req: AnalyzeRequest, manual_bundles=None):
        symbol = req.symbol.upper().replace("-", "/")
        with self.lock:
            source = ManualMarketSource(manual_bundles) if manual_bundles else BinancePublicSource([symbol], interval=req.interval, limit=req.limit)
            self.orch = self._build(symbol, source)
            result = self.orch.run_cycle()
            payload = result.to_dict()
            payload["meta"] = {
                "symbol": symbol, "source": req.source, "mode": req.mode,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "pipeline": ["market_data", "context", "agent_1", "failure_analysis", "agent_3", "order_sizing", "validation", "risk", "execution_guard"],
            }
            self.last_result = payload
            self.history.insert(0, payload)
            self.history = self.history[:50]
            return payload


def create_app(default_symbol: str = "BTC/USDT") -> FastAPI:
    app = FastAPI(title="TEXTRADER X Control Plane", version="4.0.0",
                  description="Auditable admin/control plane for autonomous trading analysis.")
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
    cp = ControlPlane(default_symbol)

    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(ROOT / "index.html")

    @app.get("/api/health")
    def health():
        return {"status": "ok", "service": "textrader-control-plane", "version": app.version,
                "state": cp.orch.state, "kill_switch": cp.orch.kill_switch.to_dict(),
                "history_size": len(cp.history)}

    @app.get("/api/market")
    def market(symbol: str = "BTC/USDT", interval: str = "1m", limit: int = 100):
        if limit < 10 or limit > 1000:
            raise HTTPException(400, "limit must be 10..1000")
        try:
            client = BinancePublicSource([symbol], interval=interval, limit=limit).client
            return client.snapshot(symbol.upper().replace("-", "/"), interval, limit)
        except Exception as exc:
            raise HTTPException(502, f"market data unavailable: {exc}") from exc

    @app.post("/api/analyze")
    def analyze(req: AnalyzeRequest):
        try:
            if req.source == "manual":
                if not req.market:
                    raise HTTPException(400, "manual source requires market payload")
                d = ManualDataRequest(**req.market)
                return cp.analyze(req, _bundles_from_manual(d))
            return cp.analyze(req)
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(500, f"analysis failed: {exc}") from exc

    @app.post("/api/analyze/manual")
    def analyze_manual(data: ManualDataRequest):
        req = AnalyzeRequest(symbol=data.symbol, source="manual", mode="paper")
        return cp.analyze(req, _bundles_from_manual(data))

    @app.get("/api/runs")
    def runs(limit: int = 20):
        return {"runs": cp.history[:max(1, min(limit, 50))]}

    @app.get("/api/runs/{cycle_id}")
    def run(cycle_id: str):
        for item in cp.history:
            if item.get("cycle_id") == cycle_id:
                return item
        raise HTTPException(404, "cycle not found")

    @app.post("/api/kill-switch/on")
    def kill_on(reason: str = "web_manual"):
        with cp.lock:
            cp.orch.activate_kill_switch(reason)
            return {"state": cp.orch.state, "kill_switch": cp.orch.kill_switch.to_dict()}

    @app.post("/api/kill-switch/off")
    def kill_off(reason: str = "web_manual_resume"):
        with cp.lock:
            cp.orch.resume_from_halted(reason)
            return {"state": cp.orch.state, "kill_switch": cp.orch.kill_switch.to_dict()}

    @app.get("/api/config")
    def config():
        return {"risk": cp.orch.rc.__dict__, "trader": cp.orch.tc.__dict__}

    # -- LLM provider switching --------------------------------------------
    @app.get("/api/llm/providers")
    def llm_providers():
        from trader.adapters.llm import available_providers
        return {"active": cp.orch.tc.llm_provider, "available": available_providers()}

    class LLMSelectRequest(BaseModel):
        provider: str

    @app.post("/api/llm/select")
    def llm_select(req: LLMSelectRequest):
        from trader.adapters.llm import available_providers
        if req.provider not in available_providers():
            raise HTTPException(400, f"unknown provider {req.provider!r}")
        with cp.lock:
            tc = load_trader_config()
            tc.mode = cp.orch.tc.mode
            tc.llm_provider = req.provider
            from trader.core.config import save_trader_config
            save_trader_config(tc)
            cp.orch.tc.llm_provider = req.provider
        return {"llm_provider": req.provider, "note": "restart the process (or `textrader web` again) to fully re-init agents"}

    @app.post("/api/llm/test")
    def llm_test(provider: str | None = None):
        from trader.adapters.llm import LLMAdapter
        return LLMAdapter(provider_name=provider or cp.orch.tc.llm_provider).ping()

    # -- External source connectors (API key or bare URL) -------------------
    class ConnectorIn(BaseModel):
        name: str
        mode: str = Field(pattern="^(api|url)$")
        base_url: str = ""
        url: str = ""
        api_key_env: str = ""
        purpose: str = "research"

    @app.get("/api/connectors")
    def connectors_list():
        from trader.adapters.source_connector import load_connectors
        from dataclasses import asdict
        return {name: asdict(c) for name, c in load_connectors().items()}

    @app.post("/api/connectors")
    def connectors_add(c: ConnectorIn):
        from trader.adapters.source_connector import SourceConnector, add_connector
        add_connector(SourceConnector(**c.model_dump()))
        return {"added": c.name}

    @app.post("/api/connectors/{name}/test")
    def connectors_test(name: str):
        from trader.adapters.source_connector import get_connector
        try:
            return get_connector(name).ping()
        except KeyError as exc:
            raise HTTPException(404, str(exc)) from exc

    @app.delete("/api/connectors/{name}")
    def connectors_remove(name: str):
        from trader.adapters.source_connector import remove_connector
        remove_connector(name)
        return {"removed": name}

    # -- Module registry: drives the panel's sidebar. Adding a future
    # capability later means adding one entry here — the UI renders it
    # automatically, active or reserved, with no template rewrite. -----------
    @app.get("/api/modules")
    def modules():
        return {"modules": [
            {"id": "overview", "label": "Overview", "status": "active"},
            {"id": "cycle", "label": "Run Cycle", "status": "active"},
            {"id": "history", "label": "History", "status": "active"},
            {"id": "risk", "label": "Risk & Kill-Switch", "status": "active"},
            {"id": "llm", "label": "LLM Provider", "status": "active"},
            {"id": "connectors", "label": "Source Connectors", "status": "active"},
            {"id": "config", "label": "Configuration", "status": "active"},
            {"id": "backtesting", "label": "Backtesting Lab", "status": "reserved",
             "note": "CLI backtest exists (`textrader backtest`); a visual results explorer goes here next."},
            {"id": "multi_account", "label": "Multi-Account / Portfolio", "status": "reserved",
             "note": "run several instrument/broker configs from one panel."},
            {"id": "notifications", "label": "Alerts & Notifications", "status": "reserved",
             "note": "email/Telegram hooks already flagged in trader.yaml (enable_email, enable_telegram) — wiring goes here."},
            {"id": "plugins", "label": "Plugin Marketplace", "status": "reserved",
             "note": "install community adapters (brokers, data vendors) without editing source."},
            {"id": "audit", "label": "Audit & Compliance Export", "status": "reserved",
             "note": "export the full decision trace (already logged) for external review."},
        ]}

    return app


app = create_app()


def serve(host="127.0.0.1", port=8787, symbol="BTC/USDT"):
    import uvicorn
    global app
    app = create_app(symbol)
    uvicorn.run(app, host=host, port=port, log_level="info")
