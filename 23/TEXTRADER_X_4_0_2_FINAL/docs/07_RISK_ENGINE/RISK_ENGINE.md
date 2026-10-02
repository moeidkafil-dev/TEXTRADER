> پروژه: TRADER / textrader — مالک و مخترع: معید کفیل الناس (Moeid Kafilonas) — برند: XIR (اکسیر)
> تاریخ سند: 2026-09-22 (۱۴۰۵/۰۶/۳۱) — منبع حقیقت: `textrader.graphml` (SHA-256: 4eed88d72144592d)


# Risk Engine (بخش اختراع + لایه محافظتی — پاسخ ۱۴)

ترتیب قوانین در گراف:
1. Position Size
2. Max Daily Loss
3. Max Drawdown
4. Exposure Limit
5. Leverage Limit
6. Stop Loss Validation
7. Take Profit Validation
8. Correlation Exposure
9. Portfolio Exposure
10. Trading Session Rules
11. Emergency Kill Switch

- همه قابل تنظیم `[OI-07]`؛ نقض هر قانون ⇒ رد.
- ساختار گراف: Risk Engine(قوانین) قبل از Decision Engine و RISK ENGINE پس از Validator (بررسی نهایی).
- `[PROPOSED P-03/P-05]` قطعی بودن قوانین عددی؛ Kill Switch با اولویت مطلق.

## پارامترهای نمونه (`RiskConfig` — مقادیر را مالک تعیین می‌کند)
`max_position_size, max_daily_loss, max_drawdown, exposure_limit, leverage_limit, require_stop_loss, require_take_profit, max_correlation, max_portfolio_exposure, trading_sessions, kill_switch`
