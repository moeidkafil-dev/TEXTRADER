# Roadmap

1. Add deterministic market-specific position units and portfolio valuation
   semantics, independently reviewed against selected venues.
2. Implement timestamped, authenticated real market-data adapters and data
   integrity/reconciliation tests.
3. Add audited provider adapters with bounded timeouts, structured outputs,
   prompt-injection evaluation, and provider failure testing.
4. Implement a real authenticated human notification/STOP channel with
   operator whitelist, persistent controls, and recovery audit.
5. Implement one venue-specific broker with durable idempotency and
   acknowledgement/fill reconciliation; retain the Guard choke point.
6. Run meaningful paper trading and out-of-sample research using licensed
   historical data. Do not infer profitability from this reference build.
7. Review database hardening, multi-process concurrency, observability
   export, deployment operations, and relevant legal/regulatory requirements.

Live trading remains intentionally disabled until external implementation,
independent review, and operational qualification have occurred.
