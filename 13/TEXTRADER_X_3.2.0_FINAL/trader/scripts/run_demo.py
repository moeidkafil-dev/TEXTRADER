"""Run one demonstration cycle end-to-end with mock data."""
from __future__ import annotations

import json
import sys

from trader.core.config import load_risk_config, load_trader_config
from trader.engine.orchestrator import Orchestrator
from trader.storage.schema import init_schema


def main() -> int:
    rc = load_risk_config()
    tc = load_trader_config()
    tc.enable_user_veto = False  # silence ⇒ execute
    orch = Orchestrator(rc, tc, db_path=tc.db_path)
    init_schema(orch.db)
    result = orch.run_cycle()
    print(json.dumps(result.to_dict(), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
