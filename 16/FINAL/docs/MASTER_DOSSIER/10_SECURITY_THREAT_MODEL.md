# Security Threat Model

## Assets
- broker/exchange credentials;
- portfolio state;
- market data;
- model/API keys;
- user identity;
- strategies;
- audit records;
- prompts/context/memory;
- execution authority.

## Threats
1. prompt injection through external data;
2. malicious tool arguments;
3. credential exfiltration;
4. unauthorized order;
5. replay/duplicate order;
6. stale data;
7. corrupted market data;
8. compromised broker adapter;
9. model hallucination;
10. memory poisoning;
11. tenant isolation failure;
12. audit tampering;
13. supply-chain compromise;
14. API abuse.

## Controls
- least privilege;
- secret vault;
- schema validation;
- policy engine;
- execution guard;
- idempotency keys;
- circuit breakers;
- kill switch;
- tenant isolation;
- immutable/auditable events;
- signed artifacts where appropriate;
- dependency pinning and scanning;
- rate limits;
- approval workflows.

## Security invariant
Untrusted text must never become an authority-bearing command without crossing a typed and policy-enforced boundary.
