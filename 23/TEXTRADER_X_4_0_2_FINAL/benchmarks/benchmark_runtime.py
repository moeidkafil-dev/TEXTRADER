"""Small deterministic runtime benchmark; no external benchmark package required."""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from trader.core.config import RiskConfig
from trader.core.schemas import ExecutionOrder
from trader.services.risk_engine import RiskEngine


def main() -> None:
    engine = RiskEngine(RiskConfig())
    order = ExecutionOrder(
        order_id="bench-order",
        idempotency_key="bench-key",
        cycle_id="bench-cycle",
        side="BUY",
        instrument="XIR/USDT",
        size=1.0,
        sl=99.0,
        tp=102.0,
    )
    kwargs = dict(
        portfolio={},
        equity=100_000.0,
        peak_equity=100_000.0,
        daily_loss=0.0,
        positions_exposure=0.0,
        correlations={},
    )

    for _ in range(1000):
        engine.final_check(order, **kwargs)

    n = 100_000
    start = time.perf_counter()
    for _ in range(n):
        engine.final_check(order, **kwargs)
    elapsed = time.perf_counter() - start

    print(f"risk_checks={n}")
    print(f"elapsed_seconds={elapsed:.6f}")
    print(f"checks_per_second={n / elapsed:.2f}")
    print(f"microseconds_per_check={elapsed / n * 1_000_000:.2f}")


if __name__ == "__main__":
    main()
