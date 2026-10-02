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
from pydantic import BaseModel, Field

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
    symbol: str = "BTC/USDT"
    timestamp: str | None = None
    price: float | None = None
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0
    order_book: dict[str, Any] | None = None
    news: list[str] = []
    sentiment: float = 0.0
    equity: float = 100000.0
    cash: float = 100000.0
    positions: dict[str, Any] = {}


def _bundles_from_manual(d: ManualDataRequest) -> list[DataBundle]:
    ts = datetime.fromisoformat(d.timestamp.replace("Z", "+00:00")) if d.timestamp else datetime.now(timezone.utc)
    ohlcv = {"open": d.open, "high": d.high, "low": d.low, "close": d.close, "volume": d.volume}
    bundles = [DataBundle(source="manual://ohlcv", timestamp=ts, quality="ok",
                          payload={"instrument": d.symbol.upper().replace("-", "/"), "ohlcv": ohlcv},
                          hash=sha256_of(ohlcv))]
    if d.order_book:
        payload = {"instrument": d.symbol.upper().replace("-", "/"), "order_book": d.order_book}
        bundles.append(DataBundle(source="manual://orderbook", timestamp=ts, quality="ok",
                                  payload=payload, hash=sha256_of(payload)))
    payload = {"headlines": d.news, "sentiment": d.sentiment}
    bundles.append(DataBundle(source="manual://news", timestamp=ts, quality="ok",
                              payload=payload, hash=sha256_of(payload)))
    payload = {"cash": d.cash, "positions": d.positions, "equity": d.equity}
    bundles.append(DataBundle(source="manual://portfolio", timestamp=ts, quality="ok",
                              payload=payload, hash=sha256_of(payload)))
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
    app = FastAPI(title="TEXTRADER X Control Plane", version="3.1.0",
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

    return app


app = create_app()


def serve(host="127.0.0.1", port=8787, symbol="BTC/USDT"):
    import uvicorn
    global app
    app = create_app(symbol)
    uvicorn.run(app, host=host, port=port, log_level="info")
