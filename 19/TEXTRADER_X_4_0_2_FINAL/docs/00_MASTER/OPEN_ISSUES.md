> پروژه: TRADER / textrader — مالک و مخترع: معید کفیل الناس (Moeid Kafilonas) — برند: XIR (اکسیر)
> تاریخ سند: 2026-09-22 (۱۴۰۵/۰۶/۳۱) — منبع حقیقت: `textrader.graphml` (SHA-256: 4eed88d72144592d)


# ابهام‌ها، تفسیرها و پیشنهادها

> طرح اصلی دست‌نخورده است. هر مورد فقط **ابهام گراف** را ثبت می‌کند. اگر تفسیر را قبول داری هیچ کاری لازم نیست؛ اگر نه، بگو تا اصلاح شود.

## A) ابهام‌های گراف (INTERPRETATION)
| ID | مشاهده در گراف | تفسیر استفاده‌شده در بسته |
|---|---|---|
| OI-01 | از `data reader → context maker → context sender` یالی مستقیم به Agent 1 نیست | Context Sender خروجی را به ورودی Agent 1 (context compiler) می‌دهد (طبق پاسخ ۹) |
| OI-02 | حلقه RE-EVALUATE در گراف رسم نشده | طبق پاسخ ۹: بازگشت به Data Reader |
| OI-03 | دو گروه Risk Engine وجود دارد: `Risk Engine` (با ۱۱ قانون) و `RISK ENGINE` (بدون قانون) و زنجیره: Risk Engine → DECISION ENGINE → DECISION VALIDATOR → RISK ENGINE → EXECUTION GUARD → BROKER/EXCHANGE → final tools؛ همچنین agent 3 → Risk Engine | Agent 3 → Risk Engine(قوانین) → Decision Engine → Decision Validator → Risk Engine(بررسی نهایی) → Execution Guard → Broker/Exchange → Final Tools |
| OI-04 | یال `BROKER/EXCHANGE → final tools` | Final Tools ابزار اجرایی هستند (پاسخ ۱۱)؛ نتیجه/تایید Broker به Final Tools برمی‌گردد و ثبت می‌شود. فرمان اجرا از Guard می‌آید |
| OI-05 | یال‌های `sell → buy → skip` | فهرست‌وار (enumerative) است، نه ترتیب اجرا |
| OI-06 | زنجیره ۲۸ نوع حافظه با یال‌های ترتیبی | کاتالوگ حافظه است، نه pipeline اجباری؛ `memory manager agent → Sensory Memory` نقطه ورود است |
| OI-07 | پاسخ ۱۵: «همینا هستند» | لیست ۱۱ قانون همان قوانین رسمی‌اند و مقادیرشان قابل تنظیم‌اند `[نیاز به تایید]` |
| OI-08 | مدل LLM هر ایجنت مشخص نشده | Provider-agnostic |
| OI-09 | رابطه Agent 1-3 با DECISION ENGINE/VALIDATOR نامشخص | Agent 3 = تصمیم‌گیر نهایی؛ Decision Engine/Validator = لایه تبدیل به دستور و اعتبارسنجی |

## B) پیشنهادهای مهندسی (PROPOSED — اختیاری، نسخه اصلی حفظ شده)
| ID | ORIGINAL | ISSUE | PROPOSED |
|---|---|---|---|
| P-01 | RE-EVALUATE بدون سقف | خطر حلقه بی‌نهایت/هزینه | `max_reevaluate_cycles` قابل تنظیم؛ پس از سقف → WAIT |
| P-02 | سکوت کاربر ۲ دقیقه = اجرا | در خطا/قطعی ارتباط اجرای بدون آگاهی | گزینه قابل تنظیم `on_silence = execute | wait`؛ پیش‌فرض بسته = **مطابق اصل: execute** ولی با پرچم اجباری برای حالت live اولیه |
| P-03 | Risk Engine دارای llm | خروجی LLM غیرقطعی | قوانین عددی به‌صورت قطعی (deterministic) و LLM فقط مشورتی؛ veto قطعی |
| P-04 | Guard → Broker | ارسال تکراری سفارش | idempotency key برای هر سفارش |
| P-05 | Kill Switch آخر زنجیره ریسک | باید بالاتر از همه باشد | Kill Switch مستقل و با اولویت مطلق؛ قابل فعال‌سازی از Telegram/Email |
| P-06 | «تمام بازارها» | پیچیدگی | Adapter مجزا برای هر بازار؛ راه‌اندازی مرحله‌ای |
| P-07 | اجرای مستقیم | ریسک مالی واقعی | Paper trading اجباری قبل از live (فصل 17) |

## C) ریسک بحرانی حقوقی
ماده ۴ قانون ثبت اختراعات ایران بخش‌هایی مثل «روش‌های انجام کسب‌وکار» و «روش‌های ریاضی» را از حمایت پتنت خارج می‌کند. جزئیات: `12_PATENT_IRAN/PATENTABILITY_RISK.md`.
