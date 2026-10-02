"""Dependency-light local Web UI/API server."""
from __future__ import annotations

import json
import mimetypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from trader.core.config import load_risk_config, load_trader_config
from trader.engine.orchestrator import Orchestrator
from trader.market.binance import BinanceMarketClient, BinancePublicSource

ROOT = Path(__file__).resolve().parent / "static"


def make_app(default_symbol: str):
    tc = load_trader_config()
    rc = load_risk_config()
    tc.instruments = [default_symbol]
    source = BinancePublicSource(tc.instruments, interval="1m", limit=100)
    orch = Orchestrator(rc, tc, data_source=source)
    client = source.client

    class Handler(BaseHTTPRequestHandler):
        server_version = "TRADER-XIR/2.0"

        def log_message(self, fmt, *args):
            print("[web] " + fmt % args)

        def send_json(self, data, status=200):
            raw = json.dumps(data, ensure_ascii=False, default=str).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self):
            u = urlparse(self.path)
            if u.path == "/":
                self.serve_file("index.html", "text/html; charset=utf-8")
                return
            if u.path.startswith("/static/"):
                self.serve_file(u.path.split("/static/", 1)[1])
                return
            if u.path == "/api/health":
                self.send_json({"status": "ok", "state": orch.state, "kill_switch": orch.kill_switch.to_dict()})
                return
            if u.path == "/api/market":
                q = parse_qs(u.query)
                symbol = q.get("symbol", [default_symbol])[0]
                interval = q.get("interval", ["1m"])[0]
                limit = min(500, max(10, int(q.get("limit", [100])[0])))
                try:
                    self.send_json(client.snapshot(symbol, interval, limit))
                except Exception as e:
                    self.send_json({"error": str(e)}, 502)
                return
            if u.path == "/api/analyze":
                q = parse_qs(u.query)
                symbol = q.get("symbol", [default_symbol])[0]
                orch.tc.instruments = [symbol]
                orch.data_source.instruments = [symbol]
                try:
                    result = orch.run_cycle()
                    self.send_json(result.to_dict())
                except Exception as e:
                    self.send_json({"error": str(e)}, 500)
                return
            self.send_json({"error": "not_found"}, 404)

        def do_POST(self):
            u = urlparse(self.path)
            if u.path == "/api/kill-switch/on":
                orch.activate_kill_switch("web_manual")
                self.send_json({"state": orch.state, "kill_switch": orch.kill_switch.to_dict()})
                return
            if u.path == "/api/kill-switch/off":
                orch.resume_from_halted("web_manual_resume")
                self.send_json({"state": orch.state, "kill_switch": orch.kill_switch.to_dict()})
                return
            self.send_json({"error": "not_found"}, 404)

        def serve_file(self, name, content_type=None):
            p = (ROOT / name).resolve()
            if ROOT.resolve() not in p.parents and p != ROOT.resolve():
                self.send_json({"error": "forbidden"}, 403); return
            if not p.exists() or not p.is_file():
                self.send_json({"error": "not_found"}, 404); return
            raw = p.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", content_type or mimetypes.guess_type(str(p))[0] or "application/octet-stream")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers(); self.wfile.write(raw)

    return Handler


def serve(host="127.0.0.1", port=8787, symbol="BTC/USDT"):
    httpd = ThreadingHTTPServer((host, port), make_app(symbol))
    print(f"TRADER/XIR Web UI: http://{host}:{port}")
    print("Public market data: Binance REST | Execution: PAPER/mock")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
