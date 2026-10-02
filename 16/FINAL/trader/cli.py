"""Professional command-line interface for textrader."""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

from trader.core.config import load_risk_config, load_trader_config, save_trader_config
from trader.engine.orchestrator import Orchestrator
from trader.market.binance import BinanceMarketClient, BinancePublicSource


def _pretty(obj):
    print(json.dumps(obj, indent=2, ensure_ascii=False, default=str))


def _symbol(args):
    return args.symbol.upper().replace("-", "/")


def _build_orchestrator(args):
    tc = load_trader_config(Path(args.config) if getattr(args, "config", None) else None)
    rc = load_risk_config(Path(args.risk) if getattr(args, "risk", None) else None)
    mode = getattr(args, "mode", None)
    if mode:
        tc.mode = mode
    symbol = getattr(args, "symbol", None)
    if symbol:
        tc.instruments = [symbol.upper().replace("-", "/")]
    source = None
    data_source = os.getenv("TEXTRADER_MARKET_DATA", "binance" if tc.mode == "live" else "mock").lower()
    if data_source == "binance":
        source = BinancePublicSource(tc.instruments, interval=os.getenv("TEXTRADER_INTERVAL", "1m"))
    return Orchestrator(rc, tc, data_source=source)


def cmd_doctor(args):
    checks = {}
    checks["python"] = sys.version.split()[0]
    try:
        tc = load_trader_config(Path(args.config) if args.config else None)
        load_risk_config(Path(args.risk) if args.risk else None)
        checks["config"] = "ok"
        checks["mode"] = tc.mode
        checks["market_data"] = os.getenv("TEXTRADER_MARKET_DATA", "mock")
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
    os.environ["TEXTRADER_MARKET_DATA"] = args.source
    o = _build_orchestrator(args)
    r = o.run_cycle()
    _pretty(r.to_dict())
    return 0 if not r.errors else 1


def cmd_paper(args):
    os.environ["TEXTRADER_MARKET_DATA"] = args.source
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


def cmd_research(args):
    from trader.research import ResearchEngine
    _pretty(ResearchEngine().search(args.query))
    return 0


def cmd_llm_list(args):
    from trader.adapters.llm import available_providers
    tc = load_trader_config(Path(args.config) if args.config else None)
    _pretty({"active": tc.llm_provider, "available": available_providers()})
    return 0


def cmd_llm_set(args):
    tc = load_trader_config(Path(args.config) if args.config else None)
    tc.llm_provider = args.provider
    path = save_trader_config(tc, Path(args.config) if args.config else None)
    if args.model:
        env_var = {"ollama": "OLLAMA_MODEL", "openai": "OPENAI_MODEL", "anthropic": "ANTHROPIC_MODEL"}.get(args.provider)
        hint = f" (also export {env_var}={args.model})" if env_var else ""
    else:
        hint = ""
    _pretty({"llm_provider": tc.llm_provider, "saved_to": str(path), "note": f"restart to take effect{hint}"})
    return 0


def cmd_llm_test(args):
    from trader.adapters.llm import LLMAdapter
    tc = load_trader_config(Path(args.config) if args.config else None)
    provider = args.provider or tc.llm_provider
    result = LLMAdapter(provider_name=provider).ping()
    _pretty(result)
    return 0 if result.get("ok") else 1


def cmd_connector_add(args):
    from trader.adapters.source_connector import SourceConnector, add_connector
    if args.url and not args.base_url:
        conn = SourceConnector(name=args.name, mode="url", url=args.url, purpose=args.purpose)
    else:
        conn = SourceConnector(name=args.name, mode="api", base_url=args.base_url,
                                api_key_env=args.api_key_env or "", purpose=args.purpose)
    add_connector(conn)
    _pretty({"added": args.name, "mode": conn.mode})
    return 0


def cmd_connector_list(args):
    from trader.adapters.source_connector import load_connectors
    conns = load_connectors()
    _pretty({name: {"mode": c.mode, "purpose": c.purpose, "target": c.base_url or c.url}
             for name, c in conns.items()})
    return 0


def cmd_connector_test(args):
    from trader.adapters.source_connector import get_connector
    result = get_connector(args.name).ping()
    _pretty(result)
    return 0 if result.get("ok") else 1


def cmd_connector_remove(args):
    from trader.adapters.source_connector import remove_connector
    remove_connector(args.name)
    _pretty({"removed": args.name})
    return 0


def cmd_kill(args):
    o = _build_orchestrator(args)
    if args.action == "on":
        o.activate_kill_switch(args.reason)
    else:
        o.resume_from_halted(args.reason)
    _pretty({"kill_switch": o.kill_switch.to_dict(), "state": o.state})
    return 0


def cmd_ingest(args):
    from trader.web.server import AnalyzeRequest, ManualDataRequest, _bundles_from_manual, ControlPlane
    try:
        payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
        data = ManualDataRequest(**payload)
        req = AnalyzeRequest(symbol=data.symbol, source="manual", mode="paper")
        result = ControlPlane(data.symbol).analyze(req, _bundles_from_manual(data))
        _pretty(result)
        return 0 if not result.get("errors") else 1
    except Exception as e:
        print(f"ERROR: manual ingestion failed: {e}", file=sys.stderr)
        return 2


def build_parser():
    p = argparse.ArgumentParser(prog="textrader", description="TEXTRADER X autonomous trading runtime")
    p.add_argument("--version", action="version", version="textrader 4.0.0")
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

    rs = sp.add_parser("research", help="run auditable knowledge research/search")
    rs.add_argument("query", nargs="?", default="trading risk management")
    rs.set_defaults(func=cmd_research)

    ll = sp.add_parser("llm", help="manage/switch the LLM provider (mock, ollama, openai, anthropic, custom)")
    llsp = ll.add_subparsers(dest="llm_command", required=True)
    ll_list = llsp.add_parser("list", help="show active + available providers")
    ll_list.set_defaults(func=cmd_llm_list)
    ll_set = llsp.add_parser("set", help="switch provider (persists to trader.yaml)")
    ll_set.add_argument("provider", choices=["mock", "ollama", "openai", "anthropic"])
    ll_set.add_argument("--model", help="model name hint (printed, set via provider-specific env var)")
    ll_set.set_defaults(func=cmd_llm_set)
    ll_test = llsp.add_parser("test", help="send a 1-token probe through the provider")
    ll_test.add_argument("--provider", help="override the configured provider for this test")
    ll_test.set_defaults(func=cmd_llm_test)

    cn = sp.add_parser("connector", help="manage external source connectors (API key or plain URL)")
    cnsp = cn.add_subparsers(dest="connector_command", required=True)
    cn_add = cnsp.add_parser("add", help="register a connector: --base-url+--api-key-env (api mode) or --url (url mode)")
    cn_add.add_argument("name")
    cn_add.add_argument("--base-url", default="", help="API base URL (api mode)")
    cn_add.add_argument("--api-key-env", default="", help="env var name holding the API key (api mode)")
    cn_add.add_argument("--url", default="", help="fixed page/feed URL to research (url mode)")
    cn_add.add_argument("--purpose", default="research", help="research | market_data | news | broker | custom")
    cn_add.set_defaults(func=cmd_connector_add)
    cn_list = cnsp.add_parser("list", help="list registered connectors")
    cn_list.set_defaults(func=cmd_connector_list)
    cn_test = cnsp.add_parser("test", help="fetch once and report ok/error")
    cn_test.add_argument("name")
    cn_test.set_defaults(func=cmd_connector_test)
    cn_rm = cnsp.add_parser("remove", help="remove a connector")
    cn_rm.add_argument("name")
    cn_rm.set_defaults(func=cmd_connector_remove)

    k = sp.add_parser("kill-switch", help="activate/resume the safety halt")
    k.add_argument("action", choices=["on", "off"])
    k.add_argument("--reason", default="manual")
    k.set_defaults(func=cmd_kill)

    mi = sp.add_parser("ingest", help="analyze a normalized/manual market JSON snapshot")
    mi.add_argument("input", help="JSON file containing open/high/low/close and portfolio fields")
    mi.set_defaults(func=cmd_ingest)

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
