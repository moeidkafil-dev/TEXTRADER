# Architecture

The original multi-stage design remains the organizing structure:

```text
MarketDataProvider adapters
  → Data Reader (quality, freshness, source identity, persistence)
  → Context Maker/Sender (hashed data + memory + history + config)
  → Agent 1 (initial BUY / SELL / WAIT)
  → Agent 2 (structured adversarial failure report, nine categories)
  → Agent 3 (BUY / SELL / WAIT / RE-EVALUATE synthesis)
  → deterministic policy and Risk Engine
  → human veto/STOP boundary
  → Execution Guard
  → BrokerAdapter / ExecutionAdapter
  → SQLite memory, decision and append-only audit
```

The orchestration lives in `xir_trader/runtime.py`; service interfaces remain
replaceable and run in one process in this reference release. Agent output is
untrusted input. Only the deterministic policy and Risk Engine authorize
execution. The Guard is the sole broker choke point.

`LLMProvider` is provider-neutral. `RuleBasedProvider` is included as a
deterministic stand-in; it is not a language model. Market data and broker
interfaces are adapters. Included adapters return synthetic examples or mock
fills and do not connect to venues.

## Service boundaries

- `adapters/data/base.py`: `MarketDataProvider` / `DataSourceAdapter` contract.
- `adapters/broker/base.py`: `Broker`, `ExecutionAdapter`, and normalized
  `BrokerAdapter` contract.
- `services/agents.py`: schema validation, memory writes, traces, and audit
  records for the three distinct agents.
- `core/policy.py`: current-data and evidence policies independent of model
  output.
- `services/risk_engine.py`: deterministic configured limits and per-instance
  authorization seal tied to order facts and all rule outcomes.
- `services/execution.py`: validates the seal, system state, recorded human
  response, and idempotency before calling the broker.
- `services/db_manager.py`: SQLite persistence used by the reference build.

There is no live execution adapter in the release. See
[`SECURITY_AND_DEPLOYMENT.md`](SECURITY_AND_DEPLOYMENT.md).
