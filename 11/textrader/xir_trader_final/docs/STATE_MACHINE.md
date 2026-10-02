# State machine

The authoritative transition table is in `xir_trader/core/state_machine.py`.
States are `IDLE`, `READING`, `CONTEXTING`, `A1`, `A2`, `A3`, `AWAIT_VETO`,
`RISK_CHECK`, `GUARD`, `EXECUTING`, `WAITING`, `REEVAL`, and `HALTED`.

```text
IDLE → READING → CONTEXTING → A1 → A2 → A3
  A3 BUY/SELL → AWAIT_VETO → RISK_CHECK → GUARD → EXECUTING → IDLE
  A3 WAIT → WAITING → IDLE
  A3 RE-EVALUATE → REEVAL → READING (whole pipeline restarts)
  veto STOP/REJECT → WAITING → HALTED
  risk/guard rejection → WAITING → IDLE
  kill switch/error/corrupted in-flight startup → HALTED
  HALTED → IDLE only via explicit `recover_from_halt(operator_confirmed=True)`
```

`Runtime` loads persisted state at startup. Unknown/corrupt or interrupted
nonterminal state fails closed to `HALTED`. A halted runtime refuses cycles;
manual recovery is explicit and audited. `RiskConfig.max_reevaluate_cycles`
limits RE-EVALUATE restarts; exceeding it finishes in `WAIT`.

The runtime rejects concurrent cycles on the same instance. Database uniqueness
and atomic cycle claims prevent a repeated cycle ID from being reused. This is
not a claim of a multi-process orchestration lease or distributed lock.
