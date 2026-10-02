> پروژه: TRADER / textrader — مالک و مخترع: معید کفیل الناس (Moeid Kafilonas) — برند: XIR (اکسیر)
> تاریخ سند: 2026-09-22 (۱۴۰۵/۰۶/۳۱) — منبع حقیقت: `textrader.graphml` (SHA-256: 4eed88d72144592d)


# تست و اعتبارسنجی

## تست‌های ردیابی‌شده به PRD
هر `TST-*` در `COMPLETE_PRD.md` باید حداقل یک تست خودکار داشته باشد.

## تست‌های سیستمی الزامی
| ID | سناریو | انتظار |
|---|---|---|
| TST-SYS-01 | Agent1=BUY، Agent2 شکست blocking، Agent3=WAIT | هیچ سفارشی؛ Override ثبت |
| TST-SYS-02 | RE-EVALUATE | چرخه از Data Reader؛ سقف چرخه |
| TST-SYS-03 | کاربر ظرف ۲ دقیقه رد کند | عدم اجرا |
| TST-SYS-04 | سکوت ۲ دقیقه | اجرا (مطابق طرح) |
| TST-SYS-05 | stop کاربر | WAITING تا فرمان بعدی |
| TST-SYS-06 | نقض هر یک از ۱۱ قانون | رد + دلیل |
| TST-SYS-07 | Kill Switch | صفر سفارش |
| TST-SYS-08 | خروجی LLM نامعتبر | WAIT |
| TST-SYS-09 | سفارش تکراری | یک اجرا |
| TST-SYS-10 | منبع داده قطع | missing_data علامت‌گذاری |

## پروتکل‌ها
1. **Backtest:** داده تاریخی؛ بدون look-ahead؛ هزینه/اسلیپیج مدل‌شده.
2. **Paper trading:** حداقل مدت `[تعیین توسط مالک]` قبل از live `[PROPOSED P-07]`.
3. **Failure injection:** قطع API، تاخیر، پاسخ خراب LLM.
4. **Ablation** (پژوهش): با/بدون Agent 2؛ با/بدون Agent 3؛ با/بدون Risk؛ حافظه کامل/کاهش‌یافته — برای سنجش کارکرد، **بدون تغییر طرح اصلی**.

## Definition of Done پروژه
همه REQ پیاده، همه TST سبز، یک دوره paper بدون نقض اینواریانت I1–I5.
