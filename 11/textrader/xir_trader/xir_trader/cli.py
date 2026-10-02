"""
CLI — defaults to PAPER mode. LIVE mode requires --i-confirm-live-trading
AND a real BrokerAdapter wired in by the operator in code (there is no
built-in live broker in this reference build) — SUPER_PROMPT.md §3 and
P-07 ("Paper trading اجباری قبل از live").
"""
from __future__ import annotations

import argparse
import sys

from .core.config import AppConfig, RiskConfig
from .runtime import Runtime


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="xir-trader", description="TRADER / XIR reference runtime")
    p.add_argument("--instrument", default="EURUSD")
    p.add_argument("--cycles", type=int, default=1)
    p.add_argument("--mode", choices=["backtest", "paper", "live"], default="paper")
    p.add_argument("--risk-config", default=None, help="path to risk.yaml")
    p.add_argument("--i-confirm-live-trading", action="store_true",
                    help="required (in addition to a real broker adapter wired in code) to run --mode live")
    p.add_argument("--veto-response", default=None,
                    help="test/dev shortcut: OK|REJECT|STOP to skip the interactive veto window")
    p.add_argument("--db-path", default="xir_trader.db")
    return p


def main(argv=None) -> int:
    args = build_arg_parser().parse_args(argv)

    app_config = AppConfig(mode=args.mode, db_path=args.db_path, live_confirmed=args.i_confirm_live_trading)
    risk_config = RiskConfig.from_yaml(args.risk_config) if args.risk_config else RiskConfig()

    if args.mode == "live":
        print(
            "REFUSING: this reference build ships no live broker adapter. "
            "Implement adapters/broker/<venue>.py (BrokerAdapter, is_live=True), "
            "pass it to Runtime(broker=...), and only then is --mode live reachable. "
            "This is intentional (SUPER_PROMPT.md absolute prohibitions + P-07).",
            file=sys.stderr,
        )
        return 2

    runtime = Runtime(app_config=app_config, risk_config=risk_config)

    for i in range(args.cycles):
        result = runtime.run_cycle(args.instrument, fast_veto_response=args.veto_response)
        print(f"[cycle {i+1}/{args.cycles}] {result}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
