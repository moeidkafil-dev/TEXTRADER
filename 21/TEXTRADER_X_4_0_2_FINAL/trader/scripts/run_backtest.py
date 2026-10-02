"""Backtest replay over synthetic bars."""
from __future__ import annotations

import argparse
import json
import random
import sys
from datetime import datetime, timezone

from trader.core.config import load_risk_config, load_trader_config
from trader.engine.orchestrator import Orchestrator
from trader.storage.schema import init_schema
from trader.services.data_reader import HistoricalReplaySource, DataReader


def gen_bars(instruments: list[str], n: int, seed: int = 7) -> list[dict]:
    rng = random.Random(seed)
    bars: list[dict] = []
    last_price = {k: 100.0 for k in instruments}
    for i in range(n):
        ts = datetime.now(timezone.utc).isoformat()
        for inst in instruments:
            p = last_price[inst]
            o = p
            h = p * (1 + rng.random() * 0.02)
            l = p * (1 - rng.random() * 0.02)
            c = p * (1 + (rng.random() - 0.5) * 0.03)
            last_price[inst] = c
            bars.append({"instrument": inst, "open": o, "high": h, "low": l, "close": c,
                         "volume": 1000 + rng.random() * 5000, "ts": ts})
    return bars


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bars", type=int, default=200)
    ap.add_argument("--instrument", type=str, default="XIR/USDT")
    ap.add_argument("--db", type=str, default="data/trader_backtest.db")
    args = ap.parse_args()

    rc = load_risk_config()
    tc = load_trader_config()
    tc.db_path = args.db
    tc.enable_user_veto = False
    tc.instruments = [args.instrument]

    orch = Orchestrator(rc, tc, db_path=tc.db_path)
    init_schema(orch.db)

    # Replace data source with replay
    bars = gen_bars([args.instrument], args.bars)
    src = HistoricalReplaySource(bars)
    orch.data_reader = DataReader([src], observability=orch.obs)

    results = []
    for i in range(args.bars):
        if orch.is_halted():
            print(f"[{i}] HALTED")
            break
        r = orch.run_cycle()
        results.append(r.to_dict())
        decision = r.final.decision if r.final else "?"
        exec_status = r.execution.status if r.execution else "-"
        print(f"[bar {i:3d}] {r.cycle_id} final={decision:12s} exec={exec_status:10s} state={r.final_state}")

    summary = {
        "bars_replayed": len(results),
        "buys": sum(1 for r in results if (r.get("final") or {}).get("decision") == "BUY"),
        "sells": sum(1 for r in results if (r.get("final") or {}).get("decision") == "SELL"),
        "waits": sum(1 for r in results if (r.get("final") or {}).get("decision") == "WAIT"),
        "reevals": sum(1 for r in results if (r.get("final") or {}).get("decision") == "RE-EVALUATE"),
        "filled": sum(1 for r in results
                      if (r.get("execution") or {}).get("status") == "filled"),
    }
    print("\nBacktest summary:")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
