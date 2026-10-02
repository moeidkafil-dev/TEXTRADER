# TEXTRADER X — Changes made in this pass

Base used: `TEXTRADER_X_4_0_0_DEBUGGED_FINAL.zip` (version 4.0.0 — the most
complete of the 19 uploaded archives: 127 .py files vs 27–73 in the others,
and it already contains fixes the other archives don't).

## Important: two of the three bugs you found were already fixed in THIS archive

Your last debug session ran against code in `~/Desktop/14/FINAL` and
`~/Desktop/15/FINAL` — those are older extractions, not this 4.0.0 archive.
Checked against this archive specifically:

1. **CLI kill-switch `AttributeError: 'Namespace' object has no attribute
   'symbol'`** — NOT present here. `trader/cli.py::_build_orchestrator` already
   uses `getattr(args, "symbol", None)`, not `args.symbol` directly.
2. **Shared-Orchestrator thread-safety** (40 concurrent threads → 39 illegal
   state transitions) — NOT present here. `Orchestrator.__init__` already
   creates `self._cycle_lock = threading.RLock()` and `run_cycle()` already
   wraps the entire cycle body in `with self._cycle_lock:`. A second orchestrator
   instance calling in from another thread will now block/queue instead of
   racing the state machine.
3. **Version mismatch** (pyproject 3.2.0 vs CLI/web 4.0.0) — not present
   here either; `pyproject.toml`, `trader/__init__.py`, and the CLI `--version`
   flag all report `4.0.0` consistently.

## Bug fixed in this pass

**`/openapi.json` crash — `PydanticUserError: ... TypeAdapter[...ForwardRef
('LLMSelectRequest')...] is not fully defined`**, which failed
`test_openapi_exposes_professional_manual_contract` and
`test_web_contract_and_manual_analysis`, and would also break `/docs` and the
admin panel's schema-driven bits in production.

Root cause: `trader/web/server.py` uses `from __future__ import annotations`
(PEP 563), so every Pydantic model's field annotations are strings resolved
lazily. FastAPI normally resolves these the first time each model is used in
a route, but by the time `/openapi.json` walked every route's request/response
models together, `LLMSelectRequest`'s internal `TypeAdapter` hadn't been built
yet and pydantic refused to guess.

Fix: added an explicit rebuild loop immediately after all four request models
are defined and before `create_app()` runs:

```python
for _request_model in (AnalyzeRequest, ManualDataRequest, LLMSelectRequest, ConnectorIn):
    _request_model.model_rebuild(force=True)
```

This forces every model to resolve its forward references eagerly at import
time (failing loudly at import time if something is genuinely broken) instead
of lazily at first-request time. This is precisely the fix pydantic's own
error message points to (`errors.pydantic.dev/2.13/u/class-not-fully-defined`).

## What I verified in this sandbox (and what I could not)

This container has **no network access and no fastapi/pydantic/pytest
installed**, and I'm not able to install them here. So I could not re-run your
exact `pytest -q` and reproduce the green suite myself. What I *did* verify:

- `python3 -m py_compile` on the changed files and `python3 -m compileall
  trader/` — the whole tree parses with no syntax errors.
- Read the exact tracebacks you pasted, matched them to the exact lines in
  this archive, and confirmed by inspection which were already fixed vs. not.

**Please run this yourself to confirm** (this is the same command from your
own audit script):

```bash
cd FINAL
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest -q --tb=short
```

If `test_openapi_exposes_professional_manual_contract` and
`test_web_contract_and_manual_analysis` are still red after this, paste me
the new traceback — the shape of the fix may need one more iteration once you
have the real pydantic error message.

## What already exists that you asked me to "build the groundwork for"

You asked for the ability to switch between local (Ollama) and hosted LLM
providers, and for a way to plug in "just an API or, worst case, a URL" for
any external source. **Both already exist in this archive** and are solid:

- `trader/adapters/llm.py`: `mock`, `ollama`, `openai` (OpenAI-compatible —
  this also covers OpenRouter/Groq/Together/vLLM/LM Studio by pointing
  `OPENAI_BASE_URL` elsewhere), and `anthropic`, switchable at runtime via
  `textrader llm set <name>` or `POST /api/llm/select`, no code changes,
  no required extra dependencies (stdlib `urllib` only). `register_factory()`
  lets you add a brand-new provider type without touching this file again.
- `trader/adapters/source_connector.py`: register a named connector as either
  `api` mode (base URL + env var holding the key) or `url` mode (just a
  URL — it fetches and strips it to plain text for the research/knowledge
  layer). Managed via `textrader connector add/list/test/remove` or
  `POST /api/connectors`.

I did not rebuild these — they were already correctly designed for exactly
the extensibility you described.

## What I did NOT do in this pass (scope reality check)

- **Did not re-run or fix the 87-test suite / coverage** — no pytest available
  here (see above). Coverage was already at 70% per your own report; raising
  it meaningfully (CCXT broker, source_connector, research, metrics are all
  at 0%) is real, multi-day test-writing work, not something to rush.
- **Did not do a full visual/UX redesign of the CLI or the admin web panel.**
  The CLI's command structure (`doctor`, `market`, `analyze`, `paper`,
  `backtest`, `research`, `llm`, `connector`, `kill-switch`, `ingest`, `web`)
  is already coherent; the admin panel (`trader/web/static/index.html`) is a
  single 125-line functional page with a working module registry
  (`/api/modules`) that already reserves slots for backtesting-lab,
  multi-account, notifications, plugin marketplace, and audit-export — so the
  "grow into new panels later" scaffolding is there. A genuine visual redesign
  (typography, layout, dark/light, charts) is a separate, sizeable front-end
  project — happy to do that as a follow-up if you tell me the look you want.
- **Did not attempt "100 years of future-proofing" or any guarantee of
  profitability** — see the note below.

## Pass 2 — admin panel visual redesign

Rewrote `trader/web/static/index.html`'s `<style>` block and the market
`draw()` function only — **did not touch any JS that calls the API or wires
buttons**, since I can't run FastAPI here to verify behavior live, and
breaking a working control plane to make it "prettier" would be a bad trade.

- New type system: Manrope (headings/values) + Inter (body) + JetBrains Mono
  (JSON/code), via Google Fonts — was plain system-ui before.
- Refined dark palette, softer borders, real depth (layered shadows,
  hover lift on cards), animated live-status dot, gradient accent bar on
  the active sidebar item instead of a flat highlight.
- The price chart went from a single interpolated line to real OHLC
  candlesticks with a volume strip and a dashed last-price marker —
  same `<canvas id="chart">`, same `draw(k)` signature, same Binance kline
  input shape, so nothing calling it needed to change.
- Verified: `python3 -m html.parser` parses the file with no fatal errors,
  and `node --check` on the extracted `<script>` block passes (brace/paren
  balance was 0/0, and Node's own parser accepts it) — the closest to a real
  test I can do without a browser or a running server in this sandbox. I
  still can't guarantee pixel-perfect rendering without you opening it in an
  actual browser against a live `textrader web` process.

CLI structure (`doctor/market/analyze/paper/backtest/research/llm/connector/
kill-switch/ingest/web`) was left as-is — it was already coherent; if you
want specific things about it changed (colored output, a different command
grouping, `rich`-style tables), tell me exactly what bothers you about it and
I'll do that pass next, rather than guessing and possibly making it worse.

## Bitget read-only decision-only patch — 2026-09-29

- Added native `BitgetMarketClient` + `BitgetPublicSource` using public GET market-data endpoints only.
- Added `bitget` to `analyze` and `paper` source choices.
- Added `--decision-only` to `analyze` and `paper`.
- Decision-only mode fail-closes the silence path to `WAIT`, so no broker submission/fill occurs.
- Added Bitget parsing/regression tests including symbol normalization, malformed/network failure, and crossed order-book handling.
- Existing mock/backtest/Binance paths remain available.
