"""Professional command-line interface for TRADER/XIR."""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

from trader.core.config import load_risk_config, load_trader_config
from trader.engine.orchestrator import Orchestrator
from trader.market.binance import BinanceMarketClient, BinancePublicSource


def _pretty(obj):
    print(json.dumps(obj, indent=2, ensure_ascii=False, default=str))


def _symbol(args):
    return args.symbol.upper().replace("-", "/")


def _build_orchestrator(args):
    tc = load_trader_config(Path(args.config) if args.config else None)
    rc = load_risk_config(Path(args.risk) if args.risk else None)
    if args.mode:
        tc.mode = args.mode
    if args.symbol:
        tc.instruments = [_symbol(args)]
    source = None
    data_source = os.getenv("XIR_MARKET_DATA", "binance" if tc.mode == "live" else "mock").lower()
    if data_source == "binance":
        source = BinancePublicSource(tc.instruments, interval=os.getenv("XIR_INTERVAL", "1m"))
    return Orchestrator(rc, tc, data_source=source)


def cmd_doctor(args):
    checks = {}
    checks["python"] = sys.version.split()[0]
    try:
        tc = load_trader_config(Path(args.config) if args.config else None)
        load_risk_config(Path(args.risk) if args.risk else None)
        checks["config"] = "ok"
        checks["mode"] = tc.mode
        checks["market_data"] = os.getenv("XIR_MARKET_DATA", "mock")
        checks["db"] = tc.db_path
    except Exception as e:
        checks["config"] = f"ERROR: {e}"
    _pretty(checks)
    return 0 if checks.get("config") == "ok" else 1


def cmd_market(args):
    c = BinanceMarketClient()
    try:
        snap = c.snapshot(_symbol(args), args.interval, args.limit)
    except Exception as e:
        print(f"ERROR: market data request failed: {e}", file=sys.stderr)
        print("Hint: verify internet/DNS access and that the exchange endpoint is reachable.", file=sys.stderr)
        return 2
    _pretty({"symbol": _symbol(args), "ticker": snap["ticker"],
             "best_bid": snap["depth"]["bids"][0] if snap["depth"]["bids"] else None,
             "best_ask": snap["depth"]["asks"][0] if snap["depth"]["asks"] else None,
             "bars": len(snap["klines"])})
    return 0


def cmd_analyze(args):
    os.environ["XIR_MARKET_DATA"] = args.source
    o = _build_orchestrator(args)
    r = o.run_cycle()
    _pretty(r.to_dict())
    return 0 if not r.errors else 1


def cmd_paper(args):
    os.environ["XIR_MARKET_DATA"] = args.source
    o = _build_orchestrator(args)
    for i in range(args.cycles):
        r = o.run_cycle()
        print(f"[{i+1}/{args.cycles}] cycle={r.cycle_id} state={r.final_state} decision={r.final.decision if r.final else 'N/A'} errors={len(r.errors)}")
        if r.final_state == "HALTED":
            break
        if args.interval > 0 and i + 1 < args.cycles:
            time.sleep(args.interval)
    return 0


def cmd_backtest(args):
    # Keep the established deterministic backtest path.
    from trader.scripts.run_backtest import main as backtest_main
    argv = ["--bars", str(args.bars)]
    old = sys.argv
    sys.argv = [old[0]] + argv
    try:
        backtest_main()
    finally:
        sys.argv = old
    return 0


def cmd_kill(args):
    o = _build_orchestrator(args)
    if args.action == "on":
        o.activate_kill_switch(args.reason)
    else:
        o.resume_from_halted(args.reason)
    _pretty({"kill_switch": o.kill_switch.to_dict(), "state": o.state})
    return 0


def build_parser():
    p = argparse.ArgumentParser(prog="xir", description="TRADER/XIR production CLI")
    p.add_argument("--version", action="version", version="TRADER/XIR 2.0.0")
    p.add_argument("--config", help="trader.yaml path")
    p.add_argument("--risk", help="risk.yaml path")
    sp = p.add_subparsers(dest="command", required=True)

    d = sp.add_parser("doctor", help="validate runtime/configuration")
    d.set_defaults(func=cmd_doctor)

    m = sp.add_parser("market", help="read real public market data")
    m.add_argument("symbol")
    m.add_argument("--interval", default="1m")
    m.add_argument("--limit", type=int, default=100)
    m.set_defaults(func=cmd_market)

    a = sp.add_parser("analyze", help="run one XIR decision cycle")
    a.add_argument("symbol", nargs="?", default="BTC/USDT")
    a.add_argument("--source", choices=["mock", "binance"], default="binance")
    a.add_argument("--mode", choices=["paper", "backtest", "live"])
    a.set_defaults(func=cmd_analyze)

    pp = sp.add_parser("paper", help="run paper cycles")
    pp.add_argument("symbol", nargs="?", default="BTC/USDT")
    pp.add_argument("--cycles", type=int, default=20)
    pp.add_argument("--interval", type=float, default=0.0)
    pp.add_argument("--source", choices=["mock", "binance"], default="binance")
    pp.set_defaults(func=cmd_paper)

    b = sp.add_parser("backtest", help="run deterministic historical replay")
    b.add_argument("--bars", type=int, default=1000)
    b.set_defaults(func=cmd_backtest)

    k = sp.add_parser("kill-switch", help="activate/resume the safety halt")
    k.add_argument("action", choices=["on", "off"])
    k.add_argument("--reason", default="manual")
    k.set_defaults(func=cmd_kill)

    w = sp.add_parser("web", help="start local web dashboard")
    w.add_argument("--host", default="127.0.0.1")
    w.add_argument("--port", type=int, default=8787)
    w.add_argument("--symbol", default="BTC/USDT")
    w.set_defaults(func=cmd_web)
    return p


def cmd_web(args):
    from trader.web.server import serve
    serve(args.host, args.port, args.symbol)
    return 0


def main():
    p = build_parser()
    args = p.parse_args()
    raise SystemExit(args.func(args))


if __name__ == "__main__":
    main()
