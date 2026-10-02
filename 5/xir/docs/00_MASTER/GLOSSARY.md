> پروژه: TRADER / textrader — مالک و مخترع: معید کفیل الناس (Moeid Kafilonas) — برند: XIR (اکسیر)
> تاریخ سند: 2026-09-22 (۱۴۰۵/۰۶/۳۱) — منبع حقیقت: `textrader.graphml` (SHA-256: 4eed88d72144592d)


# واژه‌نامه

| اصطلاح | تعریف |
|---|---|
| Context | بسته‌ای شامل داده بازار + حافظه + تصمیم‌های قبلی + وضعیت بازار + تنظیمات (پاسخ ۲۳) |
| InitialDecision | خروجی Agent 1 |
| FailureReport | خروجی Agent 2؛ فهرست تمام مسیرهای شکست تصمیم اولیه |
| FinalDecision | خروجی Agent 3: BUY / SELL / WAIT / RE-EVALUATE |
| RE-EVALUATE | شروع دوباره کل چرخه از Data Reader |
| Hidden Memory | حافظه پنهان هر ایجنت/ماژول (گره `hidden memory`) |
| Agent Local Memory | یک حافظه محلی برای هر ایجنت |
| Memory Manager | ایجنت مدیریت/پاکسازی حافظه، اجرای دوره‌ای هر ۲ ساعت |
| Veto Window | پنجره ۲ دقیقه‌ای اعلام تصمیم به کاربر؛ رد = عدم اجرا |
| Kill Switch | آخرین قانون Risk Engine؛ توقف اضطراری |
| Execution Guard | لایه پیش از Broker/Exchange |
| Final Tools | سه ابزار اجرایی: buy system / sell system / skip |
| SKIP ≡ WAIT | `[INTERPRETATION]` ابزار skip معادل تصمیم WAIT |
| Source of Truth | فایل GraphML اصلی |
