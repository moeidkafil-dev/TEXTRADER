# Agent and adapter protocols

## Agent contracts

- Agent 1 returns `InitialDecision`: action (`BUY|SELL|WAIT`), exact requested
  instrument, non-empty rationale, assumptions, evidence, confidence in [0,1],
  and optional non-negative stop/take levels. BUY/SELL requires cited open and
  close values matching the current validated critical feed.
- Agent 2 returns exactly one structured `FailurePath` for each of the nine
  `FailureCategory` values. Each finding has description, severity, explicit
  blocking/found flags, evidence, counter-evidence, assumption, and bounded
  confidence. Invalid/incomplete/duplicate-category output becomes a blocking
  report. Provider failure also blocks.
- Agent 3 returns `FinalDecision` (`BUY|SELL|WAIT|RE-EVALUATE`) with rationale,
  confidence, evidence, blocking issues, risk summary, and agent trace fields.
  Final trade evidence must be traceable to current critical data. Deterministic
  policy overrides a model response.

Schemas are Python dataclasses and `.validate()` methods in
`xir_trader/core/schemas.py`; they are the implementation's source of truth.
Provider output must be plain mapping-compatible data, not trusted code. Never
put secrets or tool execution authority in prompts.

## Adapter contracts

- `MarketDataProvider.fetch(instrument)`: returns a mapping with provider
  timestamp (`timestamp` or `ts`). Critical feeds must supply finite OHLCV;
  optional bid/ask feeds must provide finite positive bid, ask, and sizes.
  Wrong instrument, invalid, stale, or future-dated records fail quality
  checks. Unavailable providers raise `DataUnavailable`.
- `BrokerAdapter.execute(order)`: returns `BrokerAck` bound to the exact
  `order_id` and `idempotency_key`; only `filled` or `rejected` is accepted.
  Exceptions/invalid acknowledgements are not successful fills.
- `LLMProvider.complete(role, context)`: returns untrusted structured output
  for the named agent. Provider timeouts/exceptions produce safe behavior.

External adapters must implement their own authentication, timeout, retry,
reconciliation, and data contract verification. No real adapters are included.
