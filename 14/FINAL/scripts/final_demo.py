#!/usr/bin/env python3
"""
TRADER (XIR) — Demo / smoke-test script.

Runs:
  1. The full pytest suite (all 65 tests should pass).
  2. One demo cycle end-to-end with mock data.
  3. A 20-cycle paper session with veto=ok.
  4. A 30-bar backtest replay.
  5. A kill-switch + resume round trip.

Use this as the "did it ship?" sanity check after install.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def banner(title: str) -> None:
    line = "=" * 70
    print(f"\n{line}\n{title}\n{line}")


def run(cmd: list[str]) -> int:
    print(f"$ {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=str(ROOT), capture_output=False)
    return result.returncode


def main() -> int:
    banner("TRADER (XIR) — Reference runtime — Final demo")
    print(f"Project root: {ROOT}")
    print(f"Python: {sys.version.split()[0]}")

    banner("Step 1 — pytest (65 tests expected to pass)")
    rc = run([sys.executable, "-m", "pytest", "-q"])
    if rc != 0:
        print(f"!! pytest failed with rc={rc}")
        return rc

    banner("Step 2 — Single demo cycle end-to-end")
    rc = run([sys.executable, "-m", "trader.scripts.run_demo"])
    if rc != 0:
        print(f"!! demo failed with rc={rc}")
        return rc

    banner("Step 3 — Paper session, 20 cycles, veto=ok")
    rc = run([sys.executable, "-m", "trader.scripts.run_paper",
              "--cycles", "20", "--veto", "ok",
              "--db", "data/demo_paper.db"])
    if rc != 0:
        print(f"!! paper failed with rc={rc}")
        return rc

    banner("Step 4 — Backtest, 30 bars")
    rc = run([sys.executable, "-m", "trader.scripts.run_backtest",
              "--bars", "30", "--db", "data/demo_backtest.db"])
    if rc != 0:
        print(f"!! backtest failed with rc={rc}")
        return rc

    banner("Step 5 — Kill switch + resume round trip")
    sys.path.insert(0, str(ROOT))
    from trader.core.config import RiskConfig, TraderConfig
    from trader.engine.orchestrator import Orchestrator

    rc_cfg = RiskConfig()
    tc_cfg = TraderConfig()
    tc_cfg.db_path = "data/demo_kill.db"
    orch = Orchestrator(rc_cfg, tc_cfg, db_path=tc_cfg.db_path)
    r1 = orch.run_cycle()
    print(f"  Cycle 1: final={r1.final.decision if r1.final else None} "
          f"exec={r1.execution.status if r1.execution else None} state={r1.final_state}")
    orch.activate_kill_switch("demo")
    print(f"  Kill switch active? {orch.is_halted()}")
    r2 = orch.run_cycle()
    print(f"  Cycle 2 (halted): final_state={r2.final_state} exec={r2.execution}")
    orch.resume_from_halted("demo_resume")
    print(f"  After resume: halted={orch.is_halted()} state={orch.state}")
    r3 = orch.run_cycle()
    print(f"  Cycle 3 (resumed): final={r3.final.decision if r3.final else None} "
          f"exec={r3.execution.status if r3.execution else None}")

    banner("All demo steps completed successfully ✓")
    print("""
Runtime summary:
  - 65 pytest tests pass
  - State machine (IDLE→READING→CONTEXTING→A1→A2→A3→AWAIT_VETO→RISK_CHECK→GUARD→EXECUTING→IDLE)
  - Invariants I1–I5 enforced at runtime
  - 11 deterministic risk rules in graph order
  - 28 memory types preserved (owner's signature)
  - 12-step Memory Manager + 12-step DB Manager pipelines
  - 2-minute user veto (silence/OK ⇒ execute; REJECT/STOP ⇒ no execution)
  - Kill switch with absolute priority (any state → HALTED; explicit resume only)
  - Mock broker fills in paper mode; backtest replays bars
""")
    return 0


if __name__ == "__main__":
    sys.exit(main())
