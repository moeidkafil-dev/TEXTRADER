> پروژه: TRADER / textrader — مالک و مخترع: معید کفیل الناس (Moeid Kafilonas) — برند: XIR (اکسیر)
> تاریخ سند: 2026-09-22 (۱۴۰۵/۰۶/۳۱) — منبع حقیقت: `textrader.graphml` (SHA-256: 4eed88d72144592d)


# پروتکل ایجنت و ابزار (JSON schemas)

```json
InitialDecision: {"cycle_id":"str","action":"BUY|SELL|WAIT","instrument":"str","rationale":"str","assumptions":["str"],"evidence":["ref"]}
FailureReport:   {"cycle_id":"str","paths":[{"category":"wrong_prediction|logical_inconsistency|missing_data|invalid_assumption|risk_violation|contradictory_evidence|tool_failure|model_uncertainty|execution_impossibility","description":"str","severity":"low|med|high|blocking"}]}
FinalDecision:   {"cycle_id":"str","decision":"BUY|SELL|WAIT|RE-EVALUATE","overrode_initial":true,"reason":"str"}
ExecutionOrder:  {"order_id":"uuid","idempotency_key":"str","side":"BUY|SELL","instrument":"str","size":0,"sl":0,"tp":0}
RiskResult:      {"order_id":"uuid","rules":[{"rule":"str","pass":true,"reason":"str"}]}
```
قانون: خروجی LLM قبل از استفاده با schema اعتبارسنجی می‌شود؛ شکست = WAIT.
