# TEXTRADER X 4.0.2 — Final Debugged Release

## Release contract

- Version is consistently **4.0.2**.
- Bitget is a **public market-data, read-only adapter**.
- Bitget uses only public `GET` market endpoints; no API key is accepted by the adapter and no trade/order endpoint is called.
- `analyze/paper --source bitget` is forced into decision-only mode and cannot submit a broker order.
- `--source bitget --mode live` is rejected by the CLI.
- Shared `Orchestrator.run_cycle()` calls are serialized with an internal re-entrant lock.
- Kill Switch state is persisted in SQLite and is visible to newly-created Orchestrator instances.
- CLI Kill Switch no longer assumes a nonexistent `symbol` argument.
- `market` supports both `--source bitget` and `--source binance`.

## Validation boundary

The release is suitable for paper/analysis testing. Real exchange order execution is intentionally outside the Bitget release path. Network availability, exchange accessibility, and third-party credentials remain environment-dependent and must be tested on the target machine.
