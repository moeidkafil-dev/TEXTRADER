"""Run N paper-trading cycles back-to-back with the mock broker."""
from __future__ import annotations

import argparse
import json
import sys

from trader.core.config import load_risk_config, load_trader_config
from trader.engine.orchestrator import Orchestrator
from trader.storage.schema import init_schema


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cycles", type=int, default=20)
    ap.add_argument("--db", type=str, default="data/trader_paper.db")
    ap.add_argument("--veto", choices=["silence", "ok", "reject", "stop"], default="silence")
    args = ap.parse_args()

    rc = load_risk_config()
    tc = load_trader_config()
    tc.db_path = args.db
    tc.enable_user_veto = True

    from trader.core.schemas import VetoResponse
    veto_map = {"silence": VetoResponse.SILENCE.value,
                "ok": VetoResponse.OK.value,
                "reject": VetoResponse.REJECT.value,
                "stop": VetoResponse.STOP.value}
    user_veto_hook = (lambda o: veto_map[args.veto])

    orch = Orchestrator(rc, tc, db_path=tc.db_path, user_veto_hook=user_veto_hook)
    init_schema(orch.db)

    results = []
    for i in range(args.cycles):
        if orch.is_halted():
            print(f"[{i}] HALTED — skipping remaining cycles")
            break
        r = orch.run_cycle()
        results.append(r.to_dict())
        decision = r.final.decision if r.final else "?"
        exec_status = r.execution.status if r.execution else "-"
        print(f"[{i:3d}] {r.cycle_id} final={decision:12s} exec={exec_status:10s} state={r.final_state}")

    summary = {
        "cycles_run": len(results),
        "halted": orch.is_halted(),
        "buys": sum(1 for r in results if (r.get("final") or {}).get("decision") == "BUY"),
        "sells": sum(1 for r in results if (r.get("final") or {}).get("decision") == "SELL"),
        "waits": sum(1 for r in results if (r.get("final") or {}).get("decision") == "WAIT"),
        "reevals": sum(1 for r in results if (r.get("final") or {}).get("decision") == "RE-EVALUATE"),
        "filled": sum(1 for r in results
                      if (r.get("execution") or {}).get("status") == "filled"),
        "errors": sum(len(r.get("errors", [])) for r in results),
    }
    print("\nSummary:")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
