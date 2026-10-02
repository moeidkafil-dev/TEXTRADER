> پروژه: TRADER / textrader — مالک و مخترع: معید کفیل الناس (Moeid Kafilonas) — برند: XIR (اکسیر)
> تاریخ سند: 2026-09-22 (۱۴۰۵/۰۶/۳۱) — منبع حقیقت: `textrader.graphml` (SHA-256: 4eed88d72144592d)


# مدل رسمی سیستم

**سیستم** S = (D, C, A₁, A₂, A₃, M, R, G, X, U) که:
- D: Data Reader، C: Context Maker/Sender
- A₁,A₂,A₃: ایجنت‌ها
- M: حافظه (۲۸ نوع) + Memory Manager + DB
- R: Risk Engine، G: Execution Guard، X: Broker + Final Tools
- U: Message System (کاربر)

## توابع
- ctx = C(D(t), M, prev, market_state, user_cfg)
- d₁ = A₁(ctx)
- F = A₂(ctx, d₁)   (مجموعه مسیرهای شکست)
- d* = A₃(ctx, d₁, F) ∈ {BUY, SELL, WAIT, RE-EVALUATE}
- اگر d* ∈ {BUY,SELL}: o = Engine(d*) ؛ v = Validator(o) ؛ r = R(v) ؛ اجرا ⇔ v ∧ r ∧ G ∧ ¬veto ∧ ¬halt
- d* = RE-EVALUATE ⇒ چرخه جدید از D

## اینواریانت‌ها (باید همیشه برقرار باشند)
- I1: هیچ سفارشی بدون عبور از R و G به X نمی‌رسد.
- I2: حالت HALTED ⇒ صفر سفارش.
- I3: رد کاربر ⇒ عدم اجرا.
- I4: هر تصمیم در Audit Memory ثبت می‌شود.
- I5: خروجی ایجنت خارج از schema ⇒ WAIT.
