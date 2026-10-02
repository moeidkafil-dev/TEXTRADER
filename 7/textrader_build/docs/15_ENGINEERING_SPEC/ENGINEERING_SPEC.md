> پروژه: TRADER / textrader — مالک و مخترع: معید کفیل الناس (Moeid Kafilonas) — برند: XIR (اکسیر)
> تاریخ سند: 2026-09-22 (۱۴۰۵/۰۶/۳۱) — منبع حقیقت: `textrader.graphml` (SHA-256: 4eed88d72144592d)


# مشخصات مهندسی (Reference Implementation — قابل تغییر، طرح اصلی ثابت)

## پشته پیشنهادی `[PROPOSED]`
- زبان: Python 3.12 (ایجنت‌ها، Risk، Adapterها)؛ سرویس‌ها مستقل.
- پایگاه داده: PostgreSQL (+ pgvector برای RAG Memory)؛ صف: Redis/NATS.
- LLM: لایه Provider-agnostic (OI-08).
- Observability: OpenTelemetry + لاگ ساخت‌یافته.

## سرویس‌ها (۱‑به‑۱ با اجزای گراف)
`data_reader, context_service, agent1, agent2, agent3, memory_service (28 stores), memory_manager, db_manager, message_service, decision_engine, decision_validator, risk_engine, execution_guard, broker_adapter(+mock), final_tools, observability, kill_switch`

## ساختار مخزن
```
trader/
  services/<component>/   # هر جزء یک پوشه
  core/schemas/           # JSON schemas (فصل 04)
  core/state_machine.py
  adapters/broker/{base.py,mock.py}
  config/risk.yaml
  tests/ (unit, integration, e2e, failure_injection)
  docs/ (همین بسته)
```
## قواعد
- مرز Risk/Guard/Kill Switch: بدون وابستگی به LLM.
- ایجنت‌ها به `risk.yaml` و Broker دسترسی مستقیم ندارند.
- حالت‌های اجرا: `backtest | paper | live` (live فقط با پرچم صریح).
