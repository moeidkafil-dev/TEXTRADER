# BUILD NOTES — TRADER (XIR) Reference Runtime

> Build date: 2026-09-22 — Version: 1.0.0 — Status: **debugged & ready**

This document records the engineering decisions, the verification status, and
how to use the runtime.

## 1. Verification status

| Check | Status |
|---|---|
| `python -c "import trader"` | OK |
| `pytest -q` (65 tests) | **65 passed** |
| `python -m trader.scripts.run_demo` (1 cycle) | OK; reaches IDLE, filled |
| `python -m trader.scripts.run_paper --cycles 20 --veto ok` | OK; ~70% fill rate |
| `python -m trader.scripts.run_paper --cycles 15 --veto reject` | OK; 0 fills (I3 enforced) |
| `python -m trader.scripts.run_backtest --bars 30` | OK; ~97% fill rate |
| Kill Switch activate → resume round trip | OK; HALTED blocks all orders |

## 2. Bugs found and fixed during this build

1. `MemoryType.from_name()` — unbalanced parenthesis.
2. `RiskConfig` import path — was imported from `core.schemas`, moved to `core.config`.
3. `in_session()` — was comparing `str` (now.strftime) with `int`. Fixed to `int()`.
4. State machine: after Risk Pass, the orchestrator was attempting `GUARD_PASS` directly
   from `RISK_CHECK`, which is illegal. Added an explicit `RISK_PASS → GUARD` step.
5. `get_db()` — the default-path comparison was clobbering the orchestrator's DB when
   `repo.get_db()` was called without args. Made path optional and reuse the existing
   default when None.
6. `MemoryManager` — the `result_log` step was added to the log AFTER the snapshot was
   taken in `result_maker`. Pre-claimed the step name so the snapshot contains all 12.
7. `run_paper.py` / `run_backtest.py` — `.get("X", {}).get("Y")` crashes when `.get("X")`
   returns None (CycleResult serialization). Fixed to `(r.get("X") or {}).get("Y")`.

## 3. What is implemented

All 19 graph components (chapter 03 COMPONENT_CATALOG):
- `n0` Data Reader + Context Maker + Context Sender
- `n2` Agent 1 (Initial decision: BUY/SELL/WAIT)
- `n3` Agent 2 (Adversarial; covers all 9 failure categories F1–F9)
- `n4` Agent 3 (Final decision + override; ∈ {BUY,SELL,WAIT,RE-EVALUATE})
- `n6` Memory Architecture (28 types) + Memory Manager (12-step)
- `n7` DB Manager Agent (12-step)
- `n8` Message System (veto + Email/Telegram senders + receiver)
- `n9` Decision Engine
- `n10` Decision Validator
- `n14` Risk Engine (11 deterministic rules) + Kill Switch
- `n11` RISK ENGINE (final post-validator check)
- `n12` Execution Guard
- `n13` Broker / Exchange (Mock adapter; pluggable)
- `n5` Final Tools (BUY/SELL/SKIP)
- `n9..n5::n3` Observability
- `n14::n20` Kill Switch (absolute priority)

All 5 invariants (I1–I5) enforced at runtime.

All 65 tests from PRD + chapter 17 system tests:
- TST-DR-01..04 (Data Reader)
- TST-AG-01..06 (Agents)
- TST-MEM-01..06 (Memory)
- TST-DB-01 (DB Manager)
- TST-MSG-01..03 (Message System)
- TST-DEC-01..02 (Decision Engine/Validator)
- TST-RSK-01..12 (Risk Engine)
- TST-EG-01, TST-BRK-01, TST-FT-01, TST-OBS-01, TST-KS-01
- TST-SYS-01..10 (End-to-end system scenarios)

## 4. What is mock / stubbed

- **LLM provider**: `MockLLM` is deterministic. Plug a real provider via
  `trader.adapters.llm.register_provider("openai", OpenAICompatibleLLM(...))`
  and set `trader.llm_provider: openai` in `config/trader.yaml`.
- **Broker**: `MockBroker` simulates fills against a price tick with small
  slippage. Plug a real broker by subclassing `BrokerAdapter` and registering
  it via `trader.adapters.broker.get_broker`.
- **Email/Telegram senders**: always return True (no network calls). Override
  in `services/message_service.py` for live deployment.
- **Database**: SQLite (no PostgreSQL/Redis required). The schema is identical
  to chapter 16; migrate to PostgreSQL by swapping `trader/storage/connection.py`
  with a psycopg2-based connection.

## 5. Run modes

- `paper` (default): Mock broker fills, no real funds.
- `backtest`: Replays historical bars via `HistoricalReplaySource`.
- `live`: NOT enabled by default; requires explicit `--live` flag, signed
  waiver, and a completed paper validation period (REQ-P-07).

## 6. How to extend

- **Plug a real LLM**: implement `LLMProvider` in `trader/adapters/llm.py`,
  register it, set `trader.llm_provider` in YAML. Agents will use it
  automatically.
- **Plug a real broker**: implement `BrokerAdapter` in
  `trader/adapters/broker/`, register it in `get_broker()`, set `trader.broker`
  in YAML.
- **Add a real data source**: subclass `DataSource` in
  `trader/services/data_reader.py`, pass it to `Orchestrator(sources=[...])`.

## 7. Disclaimer

This runtime can trade real money once a live broker is wired. No document in
this package guarantees profit. Live trading requires explicit confirmation,
a signed waiver, and a completed paper-trading validation period.
