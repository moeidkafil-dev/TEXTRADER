# Risk and execution specification

Risk enforcement is deterministic; no model controls limits. The engine
reports machine-readable rule outcomes and the first failure. It checks
position size, daily loss, drawdown, exposure, leverage, stop-loss and take
profit presence, correlation exposure, portfolio exposure, UTC sessions,
liquidity/spread facts, and emergency kill switch. Kill switch short-circuits
and fails all rules; a final kill-switch rule is also checked on the normal
path. Values are configured in `config/risk.yaml` and are illustrative only.

No production thresholds are asserted. `max_spread` is optional and must be
calibrated for a reviewed instrument/venue; liquidity data itself is required
by default. Position units/value conventions and correlation calculations
must be made market-specific by a real integration before deployment.

For a BUY/SELL the runtime requires valid directionally placed strategy stop
and take-profit values when configured as mandatory. Orders carry requested
size without clamping; the risk rule can genuinely reject an oversized size.

## Execution invariants

1. The Guard is the only code path to `BrokerAdapter.execute`.
2. A caller-created passing-looking `RiskResult` is insufficient. RiskEngine
   signs the complete ordered rule result and exact order facts with a
   per-instance HMAC key; Guard verifies authenticity and no mutation.
3. The Guard checks both in-memory and persisted state is `EXECUTING`, checks
   the recorded veto response, and rejects human STOP/REJECT or unknown state.
4. The SQLite order row reserves a unique idempotency key before external I/O.
   Timeout outcomes remain `unknown`; the key is not released for retry.
5. Only a matching, recognized broker acknowledgement is accepted. Invalid
   acknowledgement is an error and does not become a successful order.

Human `STOP`/`REJECT` sets persistent `HALTED`; only an explicit operator
recovery can return to IDLE. The reference console does not implement an
authenticated external-control channel. Veto silence defaults to `wait`; the
optional `execute` silence policy is an explicit configuration choice and
still cannot override STOP/REJECT.
