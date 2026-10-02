> پروژه: TRADER / textrader — مالک و مخترع: معید کفیل الناس (Moeid Kafilonas) — برند: XIR (اکسیر)
> تاریخ سند: 2026-09-22 (۱۴۰۵/۰۶/۳۱) — منبع حقیقت: `textrader.graphml` (SHA-256: 4eed88d72144592d)


# ایجنت‌ها و حافظه

## سه ایجنت
| ایجنت | نقش [ORIGINAL] | خروجی |
|---|---|---|
| 1 | تحلیل داده و تصمیم اولیه | InitialDecision |
| 2 | یافتن تمام راه‌های شکست تصمیم اولیه (adversarial) | FailureReport |
| 3 | دریافت تصمیم اولیه + شکست‌ها؛ تصمیم نهایی: دوباره تصمیم‌گیری / خرید / فروش / صبر | FinalDecision |

## ۲۸ نوع حافظه (حفظ کامل — حذف/ادغام ممنوع)
1. Sensory Memory
2. Working Memory
3. Short-Term Memory (STM)
4. Long-Term Memory (LTM)
5. Episodic Memory
6. Semantic (Knowledge) Memory
7. Procedural Memory
8. Goal Memory
9. Task Memory
10. Context Memory
11. Conversation Memory
12. Tool Memory
13. Environment / World State
14. User Profile Memory
15. Learning Memory
16. Experience Memory
17. Failure Memory
18. Success Memory
19. Reflection Memory
20. Planning Memory
21. RAG Memory
22. Cache Memory
23. Shared Memory
24. Agent Local Memory
25. Audit / History Memory
26. Temporal Memory
27. Meta Memory
28. memory manager agent

`[OI-06]` یال‌های ترتیبی بین انواع حافظه کاتالوگ‌اند؛ «memory manager agent» نقطه ورود است.

## Memory Manager (۱۲ مرحله)
input reader → input analyser → input setter in memory → memory analyser → memory complete analyser → find junks → tables cleaner → memory analyser → being in sleep mode (هر ۲ ساعت) → output request analyser → result maker → result/log

- find junks: تکراری/اضافی/قدیمی با نسخه جدیدتر/مربوط به فایل‌های حذف‌شده؛ کش تسک‌ها را در یک کش تک‌فایل سبک جمع می‌کند.
- tables cleaner: حذف junk و دسته‌بندی پویا.

## DB Manager Agent
receiver → compile → reader → analyser → executer → DB analyser → DB situation analyser → DB log maker → result maker → log maker → result sender → log sender
