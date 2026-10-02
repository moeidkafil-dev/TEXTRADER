# Debug and test log

This file records significant defects found during the reference build. Final
test counts and reproducible commands are maintained in
`FINAL_RELEASE_REPORT.md`.

## Position-size rule was unfalsifiable

The orchestrator originally clamped every requested order to the configured
maximum before asking the Risk Engine whether it was allowed:
`size = min(default_size, max_position_size)`. Thus the position-size risk rule
could never reject an oversized request. The fix made requested order size an
independent policy input and tests the raw requested size at Risk Engine.

## Release-hardening defects

- **Forged risk approvals:** the Guard previously accepted a caller-created
  all-passing result. The Risk Engine now HMAC-seals the complete results to
  the exact order and its instance key. A caller-created or modified result
  cannot pass Guard verification.
- **Missing timestamps:** absent timestamps were treated as current. Missing,
  malformed, future-dated, stale, and wrong-instrument provider payloads are
  now explicitly invalid.
- **Agent 3 evidence:** a final trade could omit verifiable current market
  evidence. BUY/SELL now requires cited open and close values matching the
  critical current input.
- **Cycle replay:** IDs marked `started` were eligible for reuse. Atomic
  database cycle claims now refuse any previously used identifier.
- **Execution authorization:** Guard now checks risk authorization, persisted
  EXECUTING state, and the persisted human veto response. STOP/REJECT is
  terminal until explicit operator recovery.
- **Adversarial coverage:** duplicated Agent 2 categories and Python booleans
  masquerading as numbers are rejected.

## Scope of verification

The release includes real pytest unit, integration, backtest, and adversarial
tests. Same-process concurrent duplicate submissions are tested. No multi-host
load, failover, real exchange, authenticated messaging, or real-capital test
was run. The bundled provider, market feeds, and broker are test doubles, and
no real historical dataset is included. See `FINAL_RELEASE_REPORT.md` for the
exact latest test results and limitations.
