> پروژه: TRADER / textrader — مالک و مخترع: معید کفیل الناس (Moeid Kafilonas) — برند: XIR (اکسیر)
> تاریخ سند: 2026-09-22 (۱۴۰۵/۰۶/۳۱) — منبع حقیقت: `textrader.graphml` (SHA-256: 4eed88d72144592d)


# فهرست اصلی بسته مستندات TRADER (XIR)

این بسته از روی **طرح اصلی خودت (`textrader.graphml`: ۱۸۹ نود، ۲۱۷ یال)** ساخته شده و طبق تصمیم تو **هیچ بخشی از طراحی اصلی حذف یا تغییر نکرده است**.

## قواعد بسته
1. **اصل طراحی = فایل GraphML.** هر چیزی که مستقیم در گراف نیست با برچسب زیر مشخص شده:
   - `[ORIGINAL]` = مستقیم از گراف یا پاسخ‌های خودت.
   - `[INTERPRETATION]` = تفسیر من برای پر کردن ابهام گراف (باید تایید کنی) — در `OPEN_ISSUES.md`.
   - `[PROPOSED]` = پیشنهاد مهندسی من؛ **جدا از طرح اصلی** و اختیاری (قالب: ORIGINAL → ISSUE → RATIONALE → PROPOSED CHANGE).
2. هیچ اطلاعات هویتی ساختگی وارد نشده؛ جاهای خالی `[PLACEHOLDER]` هستند.
3. ادعای «جدید بودن» (novelty) بدون جست‌وجوی prior-art واقعی ثبت نشده است.

## نقشه پوشه‌ها
| پوشه | محتوا |
|---|---|
| 00_MASTER | فهرست، منبع حقیقت، تاریخچه، واژه‌نامه، **OPEN_ISSUES** |
| 01_OWNER_AND_INVENTOR | مالک، مخترع، مشارکت، پیش‌نویس اظهار مالکیت |
| 02_PROJECT_IDENTITY | تعریف پروژه، مأموریت، مسئله، راه‌حل، کاربردها |
| 03_ORIGINAL_ARCHITECTURE | تحلیل گراف، کاتالوگ اجزا، جریان داده |
| 04_FORMAL_SYSTEM_SPECIFICATION | مدل سیستم، ماشین حالت، پروتکل‌ها |
| 05_AGENT_AND_MEMORY_MODEL | ایجنت‌ها و ۲۸ نوع حافظه + Memory Manager |
| 06_DECISION_AND_FAILURE_MODEL | تصمیم، تعریف رسمی failure |
| 07_RISK_ENGINE | قوانین ریسک و Kill Switch |
| 08_EXECUTION_MODEL | Guard، Broker، Final Tools، Message/Veto |
| 09_SECURITY | مدل امنیتی |
| 10_RESEARCH | برنامه پژوهشی کامل |
| 11_ACADEMIC_MONOGRAPH | مونوگراف |
| 12_PATENT_IRAN | پرونده اختراع (ایران) + **ریسک بحرانی ماده ۴** |
| 13_PRIOR_ART | برنامه جست‌وجوی پیشینه |
| 14_COMPLETE_PRD | PRD در سطح implementation |
| 15_ENGINEERING_SPEC | مشخصات مهندسی |
| 16_DATABASE_AND_API | دیتابیس و قراردادها |
| 17_TEST_AND_VALIDATION | تست، بک‌تست، paper trading |
| 18_AI_BUILD_SYSTEM | SUPER_PROMPT و پرامپت‌های نقش‌ها |
| 19_TRACEABILITY | ماتریس گره گراف → نیازمندی → جزء → تست |
| 20_SOURCE_OF_TRUTH | GraphML اصلی، manifest، قفل پروژه |

## ترتیب خواندن پیشنهادی
`OPEN_ISSUES` → `12_PATENT_IRAN/PATENTABILITY_RISK` → `03` → `14_COMPLETE_PRD` → `18/SUPER_PROMPT`.
