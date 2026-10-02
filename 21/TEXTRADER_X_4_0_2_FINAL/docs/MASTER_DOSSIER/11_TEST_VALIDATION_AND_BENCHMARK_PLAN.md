# Test, Validation & Benchmark Plan

## Unit
- context compiler
- schemas
- validators
- risk formulas
- state machines
- adapters
- memory retrieval

## Integration
- data → context
- context → agents
- agents → validator
- validator → risk
- risk → execution guard
- execution → reconciliation

## Adversarial
- malformed JSON
- contradictory agents
- prompt injection
- stale data
- missing candles
- duplicate order
- broker timeout
- partial fill
- corrupted response
- unavailable LLM
- invalid credentials
- kill switch during execution

## Simulation
- historical replay
- walk-forward
- out-of-sample
- Monte Carlo/scenario tests where appropriate
- slippage/latency models
- transaction costs

## AI evaluation
Measure:
- schema compliance;
- contradiction rate;
- calibration;
- uncertainty quality;
- tool misuse;
- latency;
- cost;
- reproducibility of the surrounding pipeline.

## Software safety metrics
- unauthorized execution count = 0
- risk bypass count = 0
- unreconciled live order count = 0 at steady state
- audit lineage completeness = 100% for critical actions

## Promotion gates
Prototype → Simulation → Paper → Restricted Live → Production

Each transition requires passing the corresponding test suite.
