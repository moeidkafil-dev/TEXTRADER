# TRADER / XIR — Reference Python Runtime

> Project: **TRADER (textrader)** — Brand: **XIR** — Owner/Inventor: **Moeid Kafilonas**
> Date: 2026-09-22 (1405/06/31) — Source of truth: `textrader.graphml`
> Implementation language: **Python 3.10+** (target 3.12)

This is the reference runtime implementation of the TRADER/XIR chain-of-agents
autonomous trading system. It implements the formal specification, state machine,
invariants I1–I5, all 11 deterministic risk rules, the 2-minute user veto window,
the kill switch with absolute priority, and the full 28-type memory catalog.

The runtime is **paper-first by default**: live execution requires an explicit
flag and a completed paper-trading validation period (REQ-P-07).

---

## 1. Project layout

```
trader/
├── pyproject.toml
├── README.md
├── requirements.txt
├── config/
│   ├── risk.yaml          # 11 risk rules + kill_switch (deterministic config)
│   └── trader.yaml         # runtime config (mode, sources, veto window, etc.)
├── data/
│   └── trader.db          # SQLite database (created at runtime)
├── trader/
│   ├── __init__.py
│   ├── core/              # schemas, state machine, config, invariants, models
│   ├── storage/           # SQLite-backed DB layer (11 tables from DATABASE_AND_API)
│   ├── memory/            # 28 memory types + Memory Manager (12-step) + DB Manager (12-step)
│   ├── adapters/          # provider-agnostic LLM adapter + broker adapter (mock)
│   ├── services/          # one module per graph component (C01–C19)
│   ├── engine/            # orchestrator (state machine + invariants + cycle runner)
│   └── scripts/           # run_paper.py, run_backtest.py, run_demo.py
└── tests/                # pytest: TST-DR..TST-KS, TST-SYS-01..10
```

## 2. Components implemented (1:1 with graph nodes / dossier chapter 03)

| Graph node | Component | Module |
|---|---|---|
| `n0` | Data Reader + Context Maker + Context Sender | `services/data_reader.py`, `services/context_service.py` |
| `n2` | Agent 1 (Initial decision) | `services/agent1.py` |
| `n3` | Agent 2 (Adversarial failure finder) | `services/agent2.py` |
| `n4` | Agent 3 (Final decision + override) | `services/agent3.py` |
| `n6` | Memory Architecture (28 types) + Memory Manager | `memory/` |
| `n7` | DB Manager Agent (12-step) | `memory/db_manager.py` |
| `n8` | Message System (veto + email/telegram) | `services/message_service.py` |
| `n9` | Decision Engine | `services/decision_engine.py` |
| `n10` | Decision Validator | `services/decision_validator.py` |
| `n14` | Risk Engine (11 deterministic rules) | `services/risk_engine.py` |
| `n11` | RISK ENGINE (final post-validator check) | `services/risk_engine.py` (`final_check`) |
| `n12` | Execution Guard | `services/execution_guard.py` |
| `n13` | Broker / Exchange | `adapters/broker/` |
| `n5` | Final Tools (BUY/SELL/SKIP) | `services/final_tools.py` |
| `n9..n5::n3` | Observability | `services/observability.py` |
| `n14::n20` | Kill Switch | `services/kill_switch.py` |

## 3. State machine (chapter 04)

```
IDLE → READING → CONTEXTING → A1 → A2 → A3
A3 --(BUY/SELL)--> AWAIT_VETO --(silence|OK)--> RISK_CHECK --(pass)--> GUARD --> EXECUTING --> IDLE
AWAIT_VETO --(reject|stop)--> WAITING --(user command)--> IDLE
A3 --(WAIT)--> WAITING/IDLE
A3 --(RE-EVALUATE)--> REEVAL → READING
RISK_CHECK --(reject)--> WAITING
ANY --(KillSwitch)--> HALTED --(explicit resume)--> IDLE
```

## 4. Invariants enforced at runtime

- **I1**: No order reaches Broker without passing Risk + Guard.
- **I2**: HALTED state ⇒ zero orders pass.
- **I3**: User reject ⇒ no execution.
- **I4**: Every decision is written to Audit Memory (append-only).
- **I5**: Any agent output violating schema ⇒ WAIT.

## 5. Failure taxonomy (chapter 06)

`F1 wrong_prediction · F2 logical_inconsistency · F3 missing_data · F4 invalid_assumption ·
F5 risk_violation · F6 contradictory_evidence · F7 tool_failure · F8 model_uncertainty ·
F9 execution_impossibility`

Agent 2 must explicitly report status for all 9 categories (empty category ⇒ explicit
`model_uncertainty` flag).

## 6. Risk Engine (11 deterministic rules — chapter 07)

Order matches the graph: `Position Size → Max Daily Loss → Max Drawdown → Exposure Limit →
Leverage Limit → Stop Loss Validation → Take Profit Validation → Correlation Exposure →
Portfolio Exposure → Trading Session Rules → Emergency Kill Switch`.

All rules are deterministic numeric checks. LLM is **not** consulted in the Risk path
(REQ-P-03). Kill Switch has absolute priority and can be triggered from Telegram/Email.

## 7. Memory (28 types — chapter 05)

All 28 types are preserved as logical stores in `trader/memory/stores.py`. No type is
merged or removed (signature design of owner). The Memory Manager runs the 12-step
pipeline on every memory request and a sleep-mode cleanup every 2 hours.

## 8. Run modes

- `paper` (default): Mock broker, simulated fills, no real funds.
- `backtest`: Historical replay, no look-ahead, modeled cost/slippage.
- `live`: Requires explicit `--live` flag + signed waiver + completed paper period.

## 9. Quick start

```bash
pip install -e .
pytest -q                          # run the full test suite (50+ cases)
python -m trader.scripts.run_demo   # one cycle end-to-end with mock data
python -m trader.scripts.run_paper --cycles 20   # 20-cycle paper session
python -m trader.scripts.run_backtest --bars 200  # backtest replay
```

## 10. CLI

```bash
trader-demo                 # one demonstration cycle
trader-paper --cycles 50    # paper session
trader-backtest --bars 200  # backtest replay
```

## 11. Disclaimer

This system can trade real money. No document in this package guarantees profit.
Live trading requires explicit confirmation, a signed waiver, and a completed
paper-trading validation period. See chapter 17 (Test & Validation) of the dossier.

## 12. Traceability

Every requirement (`REQ-*`) and test (`TST-*`) in `COMPLETE_PRD.md` is mapped to a
code path and an automated test in `tests/`. See `TRADER_XIR/19_TRACEABILITY/traceability.csv`
for the source mapping.
