# Debug & test log

Environment note: this build environment has no outbound network access, so
`pytest` could not be installed from PyPI. Everything below was verified with
(a) a hand-written smoke runner exercising the same code paths, and (b) a
~150-line pytest-compatible shim (fixtures + `pytest.raises`) good enough to
execute the actual `tests/*.py` files unmodified. The test files themselves
are plain pytest and need no changes to run under a real `pytest` once you
have network access: `pip install -r requirements.txt && pytest -q`.

## Bug found and fixed during this build

**Position-size risk rule was unfalsifiable.** The orchestrator originally
built every order with
`size = min(100.0, risk_config.max_position_size)` — i.e. it clamped the
requested size to the configured limit *before* asking the Risk Engine
whether that size was acceptable. That meant Risk Engine rule
`01_position_size` could never actually reject an order: whatever the limit
was, the order was always sized to fit under it.

This is exactly the kind of bug the spec's own Definition of Done ("تست سبز")
exists to catch, and it's a meaningful one for a system whose entire premise
is "no order reaches a broker without passing Risk" — a risk rule that can
never fire is not a control, just decoration.

Fix: `AppConfig.default_order_size` is now an independent policy input
(default `100.0`), unrelated to the risk limit. The Risk Engine sees the
*requested* size and genuinely decides whether to allow it. Added
`test_position_size_rejected` (unit, risk engine in isolation) and confirmed
via a targeted end-to-end run that a tight `max_position_size` blocks every
fill for a whole run of cycles, not just once.

## Full run log (final state, after the fix)

```
State machine:          5/5   PASS
Risk engine:             8/8   PASS  (all 11 rules present/ordered, kill switch
                                       first + absolute, position size, daily
                                       loss, stop-loss requirement, trading
                                       session window all independently tested)
Invariants (I1, I5):     4/4   PASS
Memory manager:          3/3   PASS  (28 types preserved, dedup works, 2h
                                       interval respected)
End-to-end paper mode:   6/6   PASS  (returns to IDLE, veto reject blocks
                                       execution, kill switch blocks all future
                                       cycles + zero fills, RiskConfig kill
                                       switch flag halts runtime, audit log
                                       populated every cycle, every submitted
                                       order has all 11 risk_results rows)
--------------------------------------------------------------------
Total: 25/25 PASS (0 failures) after the position-size fix above
```

CLI smoke test: `python -m xir_trader.cli --cycles 3 --veto-response OK`
ran 3 full cycles (BUY / BUY / WAIT in that particular run — the
`RuleBasedProvider`'s momentum stub is stochastic by instrument, not fixed)
and returned to `IDLE` cleanly each time.

`--mode live` was confirmed to exit non-zero with an explicit refusal message
rather than silently doing anything, per SUPER_PROMPT.md's absolute
prohibitions.

`py_compile` over every module in the package: clean, no syntax errors.

## What this does *not* prove

- No statistical/backtesting validation of the trading logic itself — the
  `RuleBasedProvider` is a placeholder, not a strategy, and was never meant
  to be evaluated as one.
- No load, concurrency, or failover testing (single-process, single-threaded
  reference build).
- No security penetration testing of a real deployment (this build has no
  network-facing surface to test — there's no live broker or real channel
  wired in).
- No review of whether the 11 risk rules' *default values* in `risk.yaml`
  are appropriate for any particular market or account size — those are
  owner-set per `OI-07` and need your own judgment, not a default I chose.
