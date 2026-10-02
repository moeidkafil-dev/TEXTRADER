# BUILD NOTES — TRADER/XIR 1.1.0

Release: 1.1.0-stress-verified  
Date: 2026-09-25

The final package is derived from the stress-tested runtime and removes the
older duplicate `xir_trader/` implementation so the distribution has one
authoritative runtime.

Key hardening fixes retained:
1. RE-EVALUATE state transition corruption fixed.
2. Kill-switch final execution race hardened.
3. Config-time kill switch reliably initializes HALTED.
4. `on_silence=wait` is fail-closed and cannot execute.
5. Runtime configuration is validated fail-closed.
6. Position-size risk is evaluated against the requested size rather than a
   pre-clamped size.

Final suite: 75 tests passed.
