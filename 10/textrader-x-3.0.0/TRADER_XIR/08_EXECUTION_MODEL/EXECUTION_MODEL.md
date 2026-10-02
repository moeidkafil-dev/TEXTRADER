> پروژه: TRADER / textrader — مالک و مخترع: معید کفیل الناس (Moeid Kafilonas) — برند: XIR (اکسیر)
> تاریخ سند: 2026-09-22 (۱۴۰۵/۰۶/۳۱) — منبع حقیقت: `textrader.graphml` (SHA-256: 4eed88d72144592d)


# مدل اجرا

- Final Tools = ابزار اجرا (نه تصمیم‌گیر): buy system / sell system / skip.
- Execution Guard → Broker/Exchange (Adapter مستقل).
- **Veto Window:** پیام برای کاربر (Email + Telegram)؛ ۲ دقیقه: سکوت/OK ⇒ اجرا؛ رد ⇒ عدم اجرا؛ stop/توقف ⇒ WAITING تا فرمان بعدی.
- خودمختار؛ انسان می‌تواند متوقف کند.
- `[PROPOSED]` idempotency، Paper mode، Mock Broker.
