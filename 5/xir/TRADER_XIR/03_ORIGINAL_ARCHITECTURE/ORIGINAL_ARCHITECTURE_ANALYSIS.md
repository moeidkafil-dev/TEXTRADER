> پروژه: TRADER / textrader — مالک و مخترع: معید کفیل الناس (Moeid Kafilonas) — برند: XIR (اکسیر)
> تاریخ سند: 2026-09-22 (۱۴۰۵/۰۶/۳۱) — منبع حقیقت: `textrader.graphml` (SHA-256: 4eed88d72144592d)


# تحلیل ساختاری معماری اصلی

- نودها: **189** (شامل 15 گروه سطح‌بالا) — یال‌ها: **217**
- سازنده: yEd 3.25.1

## هسته
1. **Data Reader**: data reader → context maker → context sender
2. **سه ایجنت متوالی**: agent 1 → agent 2 → agent 3
3. **معماری حافظه**: ۲۸ نوع حافظه + memory manager (۱۲ گره) + DB manager agent (۱۲ گره) + database/memory
4. **Message System**: ارتباط با کاربر (Email/Telegram) و دریافت پیام
5. **زنجیره تصمیم/ریسک/اجرا**: Risk Engine → DECISION ENGINE → DECISION VALIDATOR → RISK ENGINE → EXECUTION GUARD → BROKER/EXCHANGE → final tools
6. **Final Tools**: sell system، buy system، skip

## الگوی تکرارشونده «قالب ایجنت»
اجزای `context compiler→llm→decision system→planner/scheduler→tool manager→tool executer` با `hidden memory→database` و `Observability` در ۹ گروه تکرار شده‌اند: Agent 1/2/3، Decision Engine، Decision Validator، Risk Engine، Execution Guard، Broker/Exchange (و Risk Engine دوم). یعنی **هر لایه، یک ایجنت کامل است** — این خود یک ویژگی معماری است.

## پرتکرارترین یال‌ها (تکرار قالب)
- context compiler → llm ×9
- llm → decision system ×9
- decision system → planner ×9
- decision system → schduler ×9
- planner → tool manager ×9
- schduler → tool manager ×9
- tool manager → tool executer ×9
- llm → hidden memory ×9

## ویژگی‌های متمایز طرح (بدون ادعای novelty)
- ایجنت ۲ عمداً «شکست‌یاب» است، نه تاییدکننده.
- ایجنت ۳ اختیار Override دارد.
- Risk Engine بخشی از اختراع اعلام شده است.
- انسان می‌تواند با پنجره ۲ دقیقه‌ای رد کند.
- حافظه با ۲۸ نوع + پاکسازی دوره‌ای.

ابهام‌ها: `00_MASTER/OPEN_ISSUES.md`
