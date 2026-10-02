> پروژه: TRADER / textrader — مالک و مخترع: معید کفیل الناس (Moeid Kafilonas) — برند: XIR (اکسیر)
> تاریخ سند: 2026-09-22 (۱۴۰۵/۰۶/۳۱) — منبع حقیقت: `textrader.graphml` (SHA-256: 4eed88d72144592d)


# مدل تصمیم و شکست

## تعریف رسمی failure [ORIGINAL: پاسخ ۲۴ — ترکیب همه]
| کد | نوع | مثال |
|---|---|---|
| F1 | wrong prediction | پیش‌بینی جهت اشتباه |
| F2 | logical inconsistency | استدلال متناقض |
| F3 | missing data | داده لازم غایب |
| F4 | invalid assumption | فرض غلط |
| F5 | risk violation | نقض قانون Risk |
| F6 | contradictory evidence | شواهد متضاد |
| F7 | tool failure | خطای ابزار/API |
| F8 | model uncertainty | عدم قطعیت مدل |
| F9 | execution impossibility | نقدینگی/بازار بسته |

## قواعد تصمیم
- Agent 2 باید هر ۹ دسته را بررسی و وضعیت هر یک را گزارش دهد.
- Agent 3 با توجه به شدت `blocking` نمی‌تواند BUY/SELL بدهد مگر با توجیه ثبت‌شده `[PROPOSED]`.
- Override مجاز: BUY→WAIT، SELL→WAIT، BUY→SELL و … (پاسخ ۸).
