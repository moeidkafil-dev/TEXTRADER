> پروژه: TRADER / textrader — مالک و مخترع: معید کفیل الناس (Moeid Kafilonas) — برند: XIR (اکسیر)
> تاریخ سند: 2026-09-22 (۱۴۰۵/۰۶/۳۱) — منبع حقیقت: `textrader.graphml` (SHA-256: 4eed88d72144592d)


# مدل امنیتی

| تهدید | کنترل |
|---|---|
| Prompt injection از اخبار/وب | داده بازار به‌عنوان data نه instruction؛ schema validation |
| نشت API key بروکر | vault/متغیر محیطی؛ هرگز در لاگ/حافظه |
| سفارش تکراری | idempotency key |
| تغییر Risk config توسط ایجنت | ایجنت‌ها دسترسی write به RiskConfig ندارند |
| جعل پیام کاربر | احراز هویت Telegram/Email (whitelist) |
| از کار افتادن LLM | خروجی نامعتبر ⇒ WAIT |
| تخریب Audit | Audit append-only |
