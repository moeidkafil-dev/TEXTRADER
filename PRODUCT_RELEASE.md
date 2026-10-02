# TEXTRADER X 3.1.0 — Control Center Release

## What changed
- FastAPI control plane with OpenAPI docs.
- Unified analysis API for live public market data and manual normalized snapshots.
- Professional admin dashboard with market chart, decision pipeline, failure-path inspection, risk gate, run history, audit/raw trace, and safety controls.
- CLI `ingest <json>` command for reproducible manual-market experiments.
- Same Orchestrator is used by CLI and Web; the UI never bypasses deterministic risk/execution guards.
- Manual data is hashed and stored as auditable `DataBundle`s.

## Run
```bash
source .venv/bin/activate
textrader web --host 127.0.0.1 --port 8787 --symbol BTC/USDT
```
Open `http://127.0.0.1:8787`.

API docs: `/docs`
OpenAPI JSON: `/openapi.json`

## Manual ingestion
```bash
textrader ingest market.json
```
Or POST the same normalized snapshot to `/api/analyze/manual`.

## Safety
The dashboard defaults to paper analysis. No live broker order is enabled by the UI. Kill switch is exposed as an explicit safety control.
