> پروژه: TRADER / textrader — مالک و مخترع: معید کفیل الناس (Moeid Kafilonas) — برند: XIR (اکسیر)
> تاریخ سند: 2026-09-22 (۱۴۰۵/۰۶/۳۱) — منبع حقیقت: `textrader.graphml` (SHA-256: 4eed88d72144592d)

# PRD کامل (سطح Implementation)

هر نیازمندی: ID، توضیح، ورودی، خروجی، وابستگی، قیود، شکست، پذیرش، تست، Definition of Done.

**Definition of Done عمومی:** کد + تست سبز + لاگ Observability + نگاشت در Traceability + بدون تغییر در طرح اصلی.

## REQ-DR-01 — خواندن تمام داده‌های بازار
- **جزء:** C01 Data Reader
- **توضیح:** خواندن همه داده‌های مرتبط با بازارهای مالی: قیمت، OHLCV، آمار خرید/فروش، Order Book، Trades، شاخص‌ها، افت/رشد، نمودار، اخبار، داده اقتصادی، پورتفوی، پوزیشن‌های باز.
- **ورودی:** پیکربندی منابع داده
- **خروجی:** DataBundle{source,timestamp,quality,payload}
- **قیود:** هیچ داده‌ای ساخته/حدس زده نمی‌شود؛ هر بسته زمان و منبع دارد
- **حالت‌های شکست:** منبع در دسترس نیست → missing_data ثبت و در Context علامت می‌خورد
- **معیار پذیرش:** همه انواع داده تحویل یا صراحتاً missing علامت شده
- **تست:** TST-DR-01
- **گره‌های گراف:** n0::n0

## REQ-DR-02 — ثبت خروجی Data Reader در حافظه
- **جزء:** C01 Data Reader
- **توضیح:** هر DataBundle در Memory/Database ذخیره می‌شود.
- **ورودی:** DataBundle
- **خروجی:** رکورد در DB
- **قیود:** قبل از ارسال به Context Maker ثبت شود
- **حالت‌های شکست:** خطای DB → هشدار Observability
- **معیار پذیرش:** رکورد قابل بازیابی با همان hash
- **تست:** TST-DR-02
- **گره‌های گراف:** n0::n0, n1

## REQ-DR-03 — ساخت Context
- **جزء:** C02 Context Maker
- **توضیح:** Context = داده + حافظه + تصمیم‌های قبلی + وضعیت بازار + تنظیمات کاربر + هر context لازم.
- **ورودی:** DataBundle, Memory, PreviousDecisions, MarketState, UserConfig
- **خروجی:** Context{context_id,hash,sections}
- **قیود:** همه بخش‌ها منبع و نسخه دارند
- **حالت‌های شکست:** بخشی خالی → با پرچم empty نه حذف
- **معیار پذیرش:** Context شامل هر ۵ بخش یا پرچم غیبت
- **تست:** TST-DR-03
- **گره‌های گراف:** n0::n1

## REQ-DR-04 — ارسال Context به Agent 1
- **جزء:** C03 Context Sender
- **توضیح:** تحویل Context به context compiler در Agent 1. `[INTERPRETATION OI-01]`
- **ورودی:** Context
- **خروجی:** Delivery ack
- **قیود:** هر Context دقیقاً یک بار تحویل شود
- **حالت‌های شکست:** ack نیامد → retry سپس هشدار
- **معیار پذیرش:** Agent 1 همان hash را دریافت کند
- **تست:** TST-DR-04
- **گره‌های گراف:** n0::n2, n2::n1

## REQ-AG-01 — قالب داخلی ایجنت
- **جزء:** C04-C06 Agents
- **توضیح:** هر ایجنت این ۱۰ جزء را دارد: llm, context compiler, decision system, planner, scheduler, tool manager, tool executer, hidden memory, database, Observability. جریان: compiler→llm→decision→(planner|scheduler)→tool manager→tool executer؛ همه به hidden memory→database؛ tool executer→Observability→database.
- **ورودی:** Context
- **خروجی:** خروجی ایجنت
- **قیود:** ترتیب جریان حفظ شود
- **حالت‌های شکست:** خطای هر جزء ثبت Observability
- **معیار پذیرش:** Trace کامل هر ۱۰ جزء در لاگ
- **تست:** TST-AG-01
- **گره‌های گراف:** n2, n3, n4

## REQ-AG-02 — تحلیل و تصمیم اولیه
- **جزء:** C04 Agent 1
- **توضیح:** تحلیل داده‌ها و تولید InitialDecision.
- **ورودی:** Context
- **خروجی:** InitialDecision{action,rationale,assumptions,evidence}
- **قیود:** خروجی طبق schema
- **حالت‌های شکست:** خروجی نامعتبر → ثبت شکست و RE-EVALUATE/WAIT
- **معیار پذیرش:** InitialDecision معتبر schema
- **تست:** TST-AG-02
- **گره‌های گراف:** n2

## REQ-AG-03 — یافتن همه مسیرهای شکست
- **جزء:** C05 Agent 2
- **توضیح:** دریافت InitialDecision و تلاش برای یافتن تمام راه‌های شکست تصمیم؛ طبق تعریف رسمی failure (ترکیب: پیش‌بینی غلط، ناسازگاری منطقی، داده گم‌شده، فرض نامعتبر، نقض ریسک، شواهد متناقض، شکست ابزار، عدم قطعیت مدل، ناممکن بودن اجرا).
- **ورودی:** InitialDecision, Context
- **خروجی:** FailureReport{paths[],category,severity}
- **قیود:** باید همه ۹ دسته را بررسی کند؛ خالی بودن دسته را صریح گزارش دهد
- **حالت‌های شکست:** ناتوانی در بررسی دسته → ثبت به‌عنوان model_uncertainty
- **معیار پذیرش:** گزارش برای هر ۹ دسته وضعیت دارد
- **تست:** TST-AG-03
- **گره‌های گراف:** n3

## REQ-AG-04 — تصمیم نهایی
- **جزء:** C06 Agent 3
- **توضیح:** دریافت InitialDecision + FailureReport و صدور FinalDecision ∈ {BUY,SELL,WAIT,RE-EVALUATE}؛ اختیار Override تصمیم اولیه را دارد.
- **ورودی:** InitialDecision, FailureReport
- **خروجی:** FinalDecision
- **قیود:** فقط ۴ مقدار مجاز
- **حالت‌های شکست:** خروجی خارج از مجموعه → رد و WAIT
- **معیار پذیرش:** Override (BUY→WAIT) قابل تولید و ثبت
- **تست:** TST-AG-04
- **گره‌های گراف:** n4

## REQ-AG-05 — RE-EVALUATE
- **جزء:** C06 Agent 3
- **توضیح:** در صورت RE-EVALUATE کل چرخه از Data Reader دوباره اجرا می‌شود.
- **ورودی:** FinalDecision=RE-EVALUATE
- **خروجی:** چرخه جدید با cycle_id جدید
- **قیود:** [PROPOSED P-01] سقف چرخه قابل تنظیم
- **حالت‌های شکست:** حلقه بی‌پایان → توقف و WAIT
- **معیار پذیرش:** چرخه از Data Reader شروع شود
- **تست:** TST-AG-05
- **گره‌های گراف:** n4, n0

## REQ-AG-06 — ثبت ایجنت‌ها در حافظه
- **جزء:** C04-C06 Agents
- **توضیح:** خروجی Agent 1، 2، 3 و Final Tools و Message System در Memory/Database ثبت شود.
- **ورودی:** خروجی‌ها
- **خروجی:** رکوردهای Audit
- **قیود:** append-only برای audit
- **حالت‌های شکست:** —
- **معیار پذیرش:** همه خروجی‌ها در DB
- **تست:** TST-AG-06
- **گره‌های گراف:** n2, n3, n4, n1

## REQ-MEM-01 — حفظ ۲۸ نوع حافظه
- **جزء:** C07 Memory Architecture
- **توضیح:** همه انواع حافظه گراف حفظ شوند (Sensory تا Meta + memory manager agent). حذف/ادغام ممنوع.
- **ورودی:** —
- **خروجی:** ۲۸ store منطقی
- **قیود:** بدون حذف/ادغام (امضای طراحی مالک)
- **حالت‌های شکست:** —
- **معیار پذیرش:** هر ۲۸ نوع در مدل داده وجود دارد
- **تست:** TST-MEM-01
- **گره‌های گراف:** n6::n0

## REQ-MEM-02 — Agent Local Memory
- **جزء:** C07 Memory Architecture
- **توضیح:** برای هر ایجنت یک حافظه محلی.
- **ورودی:** agent_id
- **خروجی:** store محلی
- **قیود:** ۳ ایجنت → ۳ حافظه محلی
- **حالت‌های شکست:** —
- **معیار پذیرش:** ایزوله بودن store ها
- **تست:** TST-MEM-02
- **گره‌های گراف:** n6::n0::n23

## REQ-MEM-03 — پایپ‌لاین مدیریت حافظه
- **جزء:** C08 Memory Manager
- **توضیح:** input reader→input analyser→input setter→memory analyser→complete analyser→find junks→tables cleaner→memory analyser→output request analyser→result maker→result/log.
- **ورودی:** ورودی حافظه/درخواست
- **خروجی:** نتیجه + لاگ
- **قیود:** ترتیب طبق گراف
- **حالت‌های شکست:** —
- **معیار پذیرش:** هر مرحله لاگ دارد
- **تست:** TST-MEM-03
- **گره‌های گراف:** n6::n1

## REQ-MEM-04 — Sleep mode ۲ ساعته
- **جزء:** C08 Memory Manager
- **توضیح:** هر ۲ ساعت یک‌بار پاکسازی و مدیریت اجرا می‌شود.
- **ورودی:** زمان
- **خروجی:** اجرای cleanup
- **قیود:** بازه ۲ ساعت
- **حالت‌های شکست:** اجرا نشد → هشدار
- **معیار پذیرش:** اجرا در هر بازه ۲ساعته لاگ دارد
- **تست:** TST-MEM-04
- **گره‌های گراف:** n6::n1::n8

## REQ-MEM-05 — یافتن Junk
- **جزء:** C08 Memory Manager
- **توضیح:** یافتن داده‌های تکراری/اضافی/قدیمی با نسخه جدیدتر/مربوط به فایل‌های حذف‌شده و جمع‌کردن کش تسک‌ها در یک کش تک‌فایل سبک.
- **ورودی:** جداول
- **خروجی:** فهرست junk
- **قیود:** نباید داده audit را حذف کند `[INTERPRETATION]`
- **حالت‌های شکست:** حذف اشتباه → بازیابی از audit
- **معیار پذیرش:** junk شناسایی و audit دست‌نخورده
- **تست:** TST-MEM-05
- **گره‌های گراف:** n6::n1::n5

## REQ-MEM-06 — Tables Cleaner
- **جزء:** C08 Memory Manager
- **توضیح:** حذف junk و دسته‌بندی پویای اطلاعات مهم.
- **ورودی:** فهرست junk
- **خروجی:** جداول تمیز
- **قیود:** دسته‌بندی پویا
- **حالت‌های شکست:** —
- **معیار پذیرش:** ورودی مهم حفظ شود
- **تست:** TST-MEM-06
- **گره‌های گراف:** n6::n1::n6

## REQ-DB-01 — DB Manager Agent
- **جزء:** C09/C10 DB
- **توضیح:** پایپ‌لاین ۱۲مرحله‌ای: receiver→compile→reader→analyser→executer→DB analyser→DB situation analyser→DB log maker→result maker→log maker→result sender→log sender.
- **ورودی:** پیام درخواست DB
- **خروجی:** نتیجه + لاگ
- **قیود:** ترتیب طبق گراف
- **حالت‌های شکست:** —
- **معیار پذیرش:** هر پیام نتیجه و لاگ دارد
- **تست:** TST-DB-01
- **گره‌های گراف:** n7

## REQ-MSG-01 — اعلام تصمیم نهایی به کاربر
- **جزء:** C11 Message System
- **توضیح:** هر تصمیم نهایی که برای اجرا گرفته شود علاوه بر لاگ DB به کاربر (Email و Telegram) ارسال شود.
- **ورودی:** FinalDecision
- **خروجی:** پیام Email/Telegram
- **قیود:** ارسال از message maker→send manager→email/telegram sender
- **حالت‌های شکست:** ارسال ناموفق → لاگ و retry
- **معیار پذیرش:** پیام رسیده در هر دو کانال
- **تست:** TST-MSG-01
- **گره‌های گراف:** n8

## REQ-MSG-02 — پنجره وتو ۲ دقیقه‌ای
- **جزء:** C11 Message System
- **توضیح:** اگر ظرف ۲ دقیقه پاسخی نیامد یا کاربر OK داد، تصمیم اجرا می‌شود؛ اگر کاربر رد کرد، اجرا نمی‌شود؛ فرمان stop/توقف/رد → سیستم منتظر فرمان بعدی می‌ماند.
- **ورودی:** FinalDecision, پاسخ کاربر
- **خروجی:** اجازه/رد
- **قیود:** [PROPOSED P-02] on_silence قابل تنظیم
- **حالت‌های شکست:** قطعی ارتباط → ثبت
- **معیار پذیرش:** سه سناریو: سکوت، OK، رد
- **تست:** TST-MSG-02
- **گره‌های گراف:** n8

## REQ-MSG-03 — دریافت پیام کاربر
- **جزء:** C11 Message System
- **توضیح:** message receiver→message analyser→context maker→sender to agent.
- **ورودی:** پیام کاربر
- **خروجی:** Context برای ایجنت
- **قیود:** —
- **حالت‌های شکست:** —
- **معیار پذیرش:** پیام کاربر به Context تبدیل شود
- **تست:** TST-MSG-03
- **گره‌های گراف:** n8

## REQ-DEC-01 — Decision Engine
- **جزء:** C12 Decision Engine
- **توضیح:** تبدیل تصمیم نهایی به دستور اجرایی ساخت‌یافته (دارای ۱۰ جزء ایجنتی).
- **ورودی:** FinalDecision
- **خروجی:** ExecutionOrder
- **قیود:** —
- **حالت‌های شکست:** —
- **معیار پذیرش:** دستور معتبر schema
- **تست:** TST-DEC-01
- **گره‌های گراف:** n9

## REQ-DEC-02 — Decision Validator
- **جزء:** C13 Decision Validator
- **توضیح:** اعتبارسنجی دستور پیش از بررسی نهایی ریسک.
- **ورودی:** ExecutionOrder
- **خروجی:** Validated/Rejected
- **قیود:** —
- **حالت‌های شکست:** رد → WAIT
- **معیار پذیرش:** دستور نامعتبر رد شود
- **تست:** TST-DEC-02
- **گره‌های گراف:** n10

## REQ-RSK-01 — Position Size
- **جزء:** C14 Risk Engine
- **توضیح:** حداکثر اندازه پوزیشن — پارامترها قابل تنظیم `[نیاز به تایید OI-07]`. نقض → رد سفارش.
- **ورودی:** ExecutionOrder, PortfolioState, RiskConfig
- **خروجی:** Pass/Reject{rule,reason}
- **قیود:** قانون عددی قطعی `[PROPOSED P-03]`
- **حالت‌های شکست:** نقض = veto
- **معیار پذیرش:** سناریوی نقض رد و ثبت شود
- **تست:** TST-RSK-01
- **گره‌های گراف:** n14::n10

## REQ-RSK-02 — Max Daily Loss
- **جزء:** C14 Risk Engine
- **توضیح:** حداکثر ضرر روزانه — پارامترها قابل تنظیم `[نیاز به تایید OI-07]`. نقض → رد سفارش.
- **ورودی:** ExecutionOrder, PortfolioState, RiskConfig
- **خروجی:** Pass/Reject{rule,reason}
- **قیود:** قانون عددی قطعی `[PROPOSED P-03]`
- **حالت‌های شکست:** نقض = veto
- **معیار پذیرش:** سناریوی نقض رد و ثبت شود
- **تست:** TST-RSK-02
- **گره‌های گراف:** n14::n11

## REQ-RSK-03 — Max Drawdown
- **جزء:** C14 Risk Engine
- **توضیح:** حداکثر افت سرمایه — پارامترها قابل تنظیم `[نیاز به تایید OI-07]`. نقض → رد سفارش.
- **ورودی:** ExecutionOrder, PortfolioState, RiskConfig
- **خروجی:** Pass/Reject{rule,reason}
- **قیود:** قانون عددی قطعی `[PROPOSED P-03]`
- **حالت‌های شکست:** نقض = veto
- **معیار پذیرش:** سناریوی نقض رد و ثبت شود
- **تست:** TST-RSK-03
- **گره‌های گراف:** n14::n12

## REQ-RSK-04 — Exposure Limit
- **جزء:** C14 Risk Engine
- **توضیح:** سقف اکسپوژر — پارامترها قابل تنظیم `[نیاز به تایید OI-07]`. نقض → رد سفارش.
- **ورودی:** ExecutionOrder, PortfolioState, RiskConfig
- **خروجی:** Pass/Reject{rule,reason}
- **قیود:** قانون عددی قطعی `[PROPOSED P-03]`
- **حالت‌های شکست:** نقض = veto
- **معیار پذیرش:** سناریوی نقض رد و ثبت شود
- **تست:** TST-RSK-04
- **گره‌های گراف:** n14::n13

## REQ-RSK-05 — Leverage Limit
- **جزء:** C14 Risk Engine
- **توضیح:** سقف اهرم — پارامترها قابل تنظیم `[نیاز به تایید OI-07]`. نقض → رد سفارش.
- **ورودی:** ExecutionOrder, PortfolioState, RiskConfig
- **خروجی:** Pass/Reject{rule,reason}
- **قیود:** قانون عددی قطعی `[PROPOSED P-03]`
- **حالت‌های شکست:** نقض = veto
- **معیار پذیرش:** سناریوی نقض رد و ثبت شود
- **تست:** TST-RSK-05
- **گره‌های گراف:** n14::n14

## REQ-RSK-06 — Stop Loss Validation
- **جزء:** C14 Risk Engine
- **توضیح:** اعتبارسنجی حد ضرر — پارامترها قابل تنظیم `[نیاز به تایید OI-07]`. نقض → رد سفارش.
- **ورودی:** ExecutionOrder, PortfolioState, RiskConfig
- **خروجی:** Pass/Reject{rule,reason}
- **قیود:** قانون عددی قطعی `[PROPOSED P-03]`
- **حالت‌های شکست:** نقض = veto
- **معیار پذیرش:** سناریوی نقض رد و ثبت شود
- **تست:** TST-RSK-06
- **گره‌های گراف:** n14::n15

## REQ-RSK-07 — Take Profit Validation
- **جزء:** C14 Risk Engine
- **توضیح:** اعتبارسنجی حد سود — پارامترها قابل تنظیم `[نیاز به تایید OI-07]`. نقض → رد سفارش.
- **ورودی:** ExecutionOrder, PortfolioState, RiskConfig
- **خروجی:** Pass/Reject{rule,reason}
- **قیود:** قانون عددی قطعی `[PROPOSED P-03]`
- **حالت‌های شکست:** نقض = veto
- **معیار پذیرش:** سناریوی نقض رد و ثبت شود
- **تست:** TST-RSK-07
- **گره‌های گراف:** n14::n16

## REQ-RSK-08 — Correlation Exposure
- **جزء:** C14 Risk Engine
- **توضیح:** اکسپوژر همبستگی — پارامترها قابل تنظیم `[نیاز به تایید OI-07]`. نقض → رد سفارش.
- **ورودی:** ExecutionOrder, PortfolioState, RiskConfig
- **خروجی:** Pass/Reject{rule,reason}
- **قیود:** قانون عددی قطعی `[PROPOSED P-03]`
- **حالت‌های شکست:** نقض = veto
- **معیار پذیرش:** سناریوی نقض رد و ثبت شود
- **تست:** TST-RSK-08
- **گره‌های گراف:** n14::n17

## REQ-RSK-09 — Portfolio Exposure
- **جزء:** C14 Risk Engine
- **توضیح:** اکسپوژر پورتفوی — پارامترها قابل تنظیم `[نیاز به تایید OI-07]`. نقض → رد سفارش.
- **ورودی:** ExecutionOrder, PortfolioState, RiskConfig
- **خروجی:** Pass/Reject{rule,reason}
- **قیود:** قانون عددی قطعی `[PROPOSED P-03]`
- **حالت‌های شکست:** نقض = veto
- **معیار پذیرش:** سناریوی نقض رد و ثبت شود
- **تست:** TST-RSK-09
- **گره‌های گراف:** n14::n18

## REQ-RSK-10 — Trading Session Rules
- **جزء:** C14 Risk Engine
- **توضیح:** قوانین ساعت معاملاتی — پارامترها قابل تنظیم `[نیاز به تایید OI-07]`. نقض → رد سفارش.
- **ورودی:** ExecutionOrder, PortfolioState, RiskConfig
- **خروجی:** Pass/Reject{rule,reason}
- **قیود:** قانون عددی قطعی `[PROPOSED P-03]`
- **حالت‌های شکست:** نقض = veto
- **معیار پذیرش:** سناریوی نقض رد و ثبت شود
- **تست:** TST-RSK-10
- **گره‌های گراف:** n14::n19

## REQ-RSK-11 — Emergency Kill Switch
- **جزء:** C14 Risk Engine
- **توضیح:** توقف اضطراری — پارامترها قابل تنظیم `[نیاز به تایید OI-07]`. نقض → رد سفارش.
- **ورودی:** ExecutionOrder, PortfolioState, RiskConfig
- **خروجی:** Pass/Reject{rule,reason}
- **قیود:** قانون عددی قطعی `[PROPOSED P-03]`
- **حالت‌های شکست:** نقض = veto
- **معیار پذیرش:** سناریوی نقض رد و ثبت شود
- **تست:** TST-RSK-11
- **گره‌های گراف:** n14::n20

## REQ-RSK-12 — ترتیب قوانین
- **جزء:** C14 Risk Engine
- **توضیح:** قوانین به ترتیب گراف اجرا شوند: Position Size → … → Emergency Kill Switch؛ Risk Engine پس از Validator یک‌بار دیگر بررسی نهایی انجام می‌دهد `[OI-03]`.
- **ورودی:** ExecutionOrder
- **خروجی:** Pass/Reject
- **قیود:** —
- **حالت‌های شکست:** —
- **معیار پذیرش:** ترتیب اجرا در لاگ
- **تست:** TST-RSK-12
- **گره‌های گراف:** n14, n11

## REQ-EG-01 — Execution Guard
- **جزء:** C15 Execution Guard
- **توضیح:** آخرین گارد پیش از Broker/Exchange؛ فقط سفارش تایید‌شده توسط Risk و بدون رد کاربر عبور کند.
- **ورودی:** سفارش تاییدشده
- **خروجی:** ارسال به Broker یا رد
- **قیود:** [PROPOSED P-04] idempotency key
- **حالت‌های شکست:** ارسال تکراری ممنوع
- **معیار پذیرش:** بدون تایید Risk هیچ سفارشی عبور نکند
- **تست:** TST-EG-01
- **گره‌های گراف:** n12

## REQ-BRK-01 — لایه Broker/Exchange مستقل از فروشنده
- **جزء:** C16 Broker/Exchange
- **توضیح:** Adapter برای بازارها/بروکرهای مختلف؛ هیچ بروکر خاصی ثابت نیست.
- **ورودی:** سفارش
- **خروجی:** تایید/رد Broker
- **قیود:** [PROPOSED P-06] Adapter مجزا
- **حالت‌های شکست:** خطای Broker → ثبت و WAIT
- **معیار پذیرش:** Mock Broker کامل کار کند
- **تست:** TST-BRK-01
- **گره‌های گراف:** n13

## REQ-FT-01 — ابزارهای نهایی
- **جزء:** C17 Final Tools
- **توضیح:** سه ابزار اجرایی: buy system، sell system، skip (≡ WAIT)؛ فقط ابزار اجرا هستند و تصمیم نمی‌گیرند. نتیجه در DB و Observability ثبت شود.
- **ورودی:** Approved order
- **خروجی:** نتیجه اجرا
- **قیود:** ابزار تصمیم‌گیر نیست
- **حالت‌های شکست:** —
- **معیار پذیرش:** هر سه ابزار قابل فراخوانی
- **تست:** TST-FT-01
- **گره‌های گراف:** n5

## REQ-OBS-01 — Observability
- **جزء:** C18 Observability
- **توضیح:** هر ایجنت/ماژول و Final Tools خروجی Observability دارد که به database می‌رود.
- **ورودی:** رویدادها
- **خروجی:** لاگ/متریک/trace
- **قیود:** —
- **حالت‌های شکست:** —
- **معیار پذیرش:** هر رویداد قابل ردیابی
- **تست:** TST-OBS-01
- **گره‌های گراف:** n2::n9, n3::n9, n4::n9, n5::n3

## REQ-KS-01 — Emergency Kill Switch
- **جزء:** C19 Kill Switch
- **توضیح:** فعال‌سازی → توقف کامل ارسال سفارش. `[PROPOSED P-05]` اولویت مطلق و فعال‌سازی از Telegram/Email.
- **ورودی:** فرمان/شرط
- **خروجی:** حالت HALTED
- **قیود:** —
- **حالت‌های شکست:** —
- **معیار پذیرش:** پس از فعال‌سازی صفر سفارش عبور کند
- **تست:** TST-KS-01
- **گره‌های گراف:** n14::n20
