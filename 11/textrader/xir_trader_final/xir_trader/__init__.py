"""
XIR / TRADER runtime — reference implementation.

Traceability: this package implements the requirements in
00_MASTER/../14_COMPLETE_PRD/COMPLETE_PRD.md (REQ-*) against the
state machine in 04_FORMAL_SYSTEM_SPECIFICATION/STATE_MACHINE.md.

Source of truth precedence (per 20_SOURCE_OF_TRUTH/SOURCE_OF_TRUTH.md):
  1. original_graph.graphml (design intent — not machine-read here)
  2. project_lock.md
  3. Approved [INTERPRETATION] entries in OPEN_ISSUES.md (OI-01..OI-09)
  4. This implementation (derived)

Absolute prohibitions honored by this codebase (18_AI_BUILD_SYSTEM/SUPER_PROMPT.md §3):
  - No order reaches a broker without passing RiskEngine + ExecutionGuard + KillSwitch check.
  - Agents never get write access to RiskConfig or broker credentials.
  - No secret is ever written to a log or to the audit trail.
  - LIVE execution requires an explicit operator flag AND a recorded PAPER track record
    (P-07). There is no code path that reaches a real broker adapter by default.
"""

__version__ = "0.1.0-reference"
