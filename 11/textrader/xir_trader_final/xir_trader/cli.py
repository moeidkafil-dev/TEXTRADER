"""
CLI — defaults to PAPER mode. LIVE mode requires --i-confirm-live-trading
AND a real BrokerAdapter wired in by the operator in code (there is no
built-in live broker in this reference build) — SUPER_PROMPT.md §3 and
P-07 ("Paper trading اجباری قبل از live").
"""
from __future__ import annotations

import argparse
import csv
import json
import sys

from .core.config import AppConfig, RiskConfig
from .runtime import Runtime
from .services.backtest import HistoricalBar, BacktestConfig, run_backtest, walk_forward_splits


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="xir-trader", description="TRADER / XIR reference runtime")
    p.add_argument("--instrument", default="EURUSD")
    p.add_argument("--cycles", type=int, default=1)
    p.add_argument("--mode", choices=["backtest", "paper", "live"], default="paper")
    p.add_argument("--risk-config", default=None, help="path to risk.yaml")
    p.add_argument("--i-confirm-live-trading", action="store_true",
                    help="required (in addition to a real broker adapter wired in code) to run --mode live")
    p.add_argument("--veto-response", choices=["OK", "REJECT", "STOP"], default=None,
                    help="test/dev shortcut: OK|REJECT|STOP to skip the interactive veto window")
    p.add_argument("--db-path", default="xir_trader.db")
    p.add_argument("--backtest-csv", default=None,
                    help="historical CSV with timestamp,open,high,low,close,volume (required for --mode backtest)")
    p.add_argument("--fee-bps", type=float, default=0.0)
    p.add_argument("--slippage-bps", type=float, default=0.0)
    p.add_argument("--spread-bps", type=float, default=0.0)
    p.add_argument("--synthetic-data", action="store_true",
                   help="label supplied backtest data as synthetic (never evidence of market performance)")
    p.add_argument("--i-confirm-halt-recovery", action="store_true",
                    help="explicitly authorize recovery from persisted HALTED state")
    return p


def main(argv=None) -> int:
    args = build_arg_parser().parse_args(argv)

    if args.cycles <= 0:
        print("--cycles must be a positive integer", file=sys.stderr)
        return 2

    if args.mode == "backtest":
        if not args.backtest_csv:
            print("--mode backtest requires --backtest-csv", file=sys.stderr)
            return 2
        try:
            with open(args.backtest_csv, newline="", encoding="utf-8") as handle:
                bars = [HistoricalBar(float(row["timestamp"]), float(row["open"]), float(row["high"]),
                                      float(row["low"]), float(row["close"]), float(row["volume"]))
                        for row in csv.DictReader(handle)]
            def momentum(history):
                if len(history) < 2:
                    return "WAIT"
                return "BUY" if history[-1].close > history[-2].close else "SELL" if history[-1].close < history[-2].close else "WAIT"
            config = BacktestConfig(fee_bps=args.fee_bps, slippage_bps=args.slippage_bps,
                                    spread_bps=args.spread_bps)
            result = run_backtest(bars, momentum, config, synthetic=args.synthetic_data)
            splits = walk_forward_splits(bars)
            result["walk_forward_counts"] = {key: len(splits[key]) for key in ("development", "validation", "unseen_test")}
            print(json.dumps(result, indent=2, default=str))
            return 0
        except Exception as exc:
            print(f"backtest failed safely: {type(exc).__name__}: {exc}", file=sys.stderr)
            return 2

    if args.mode == "live":
        print(
            "REFUSING: live mode is disabled in this reference release; no reviewed live broker adapter exists.",
            file=sys.stderr,
        )
        return 2

    app_config = AppConfig(mode=args.mode, db_path=args.db_path, live_confirmed=args.i_confirm_live_trading)
    risk_config = RiskConfig.from_yaml(args.risk_config) if args.risk_config else RiskConfig()

    runtime = Runtime(app_config=app_config, risk_config=risk_config)

    if runtime.sm.state.value == "HALTED" and args.i_confirm_halt_recovery:
        runtime.recover_from_halt(operator_confirmed=True)

    for i in range(args.cycles):
        cycle_result = runtime.run_cycle(args.instrument, fast_veto_response=args.veto_response)
        print(f"[cycle {i+1}/{args.cycles}] {cycle_result}")
        if cycle_result.final_state == "HALTED":
            break

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
