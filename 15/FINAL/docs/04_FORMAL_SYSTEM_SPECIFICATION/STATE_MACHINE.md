> پروژه: TRADER / textrader — مالک و مخترع: معید کفیل الناس (Moeid Kafilonas) — برند: XIR (اکسیر)
> تاریخ سند: 2026-09-22 (۱۴۰۵/۰۶/۳۱) — منبع حقیقت: `textrader.graphml` (SHA-256: 4eed88d72144592d)


# ماشین حالت

| حالت | توضیح |
|---|---|
| IDLE | آماده |
| READING | Data Reader |
| CONTEXTING | Context Maker/Sender |
| A1 / A2 / A3 | ایجنت‌ها |
| AWAIT_VETO | پنجره ۲ دقیقه |
| RISK_CHECK | Risk + Engine + Validator + Risk |
| GUARD | Execution Guard |
| EXECUTING | Broker + Final Tools |
| WAITING | WAIT/Skip یا پس از رد/stop کاربر تا فرمان بعدی |
| REEVAL | RE-EVALUATE |
| HALTED | Kill Switch |

گذارها:
```
IDLE→READING→CONTEXTING→A1→A2→A3
A3--BUY/SELL-->AWAIT_VETO--(سکوت|OK)-->RISK_CHECK--pass-->GUARD-->EXECUTING-->IDLE
AWAIT_VETO--(رد|stop)-->WAITING--(فرمان کاربر)-->IDLE
A3--WAIT-->WAITING/IDLE ; A3--RE-EVALUATE-->REEVAL→READING
RISK_CHECK--reject-->WAITING ; هر حالت--KillSwitch-->HALTED--(فرمان صریح)-->IDLE
```
