> پروژه: TRADER / textrader — مالک و مخترع: معید کفیل الناس (Moeid Kafilonas) — برند: XIR (اکسیر)
> تاریخ سند: 2026-09-22 (۱۴۰۵/۰۶/۳۱) — منبع حقیقت: `textrader.graphml` (SHA-256: 4eed88d72144592d)


# جریان داده

```
Data Reader ─▶ Context Maker ─▶ Context Sender ─▶ Agent 1 ─▶ Agent 2 ─▶ Agent 3
     │ (ثبت در Memory/DB)                          │ همه ثبت در Memory/DB
                                                    ▼
                    Agent 3 ─▶ Message System (Email/Telegram) ─▶ [Veto ۲ دقیقه]
                    Agent 3 ─▶ Risk Engine(قوانین) ─▶ DECISION ENGINE ─▶ DECISION VALIDATOR
                              ─▶ RISK ENGINE ─▶ EXECUTION GUARD ─▶ BROKER/EXCHANGE ─▶ Final Tools
Agent 3 = RE-EVALUATE ─▶ بازگشت به Data Reader
کاربر ─▶ Message Receiver ─▶ Analyser ─▶ Context Maker ─▶ Sender to Agent
```
`[INTERPRETATION]` مسیر Context Sender→Agent 1 و حلقه RE-EVALUATE در گراف رسم نشده‌اند (OI-01/02).

## حالت‌های مسیر
| FinalDecision | مسیر |
|---|---|
| BUY | Message → (Veto) → Risk → Engine → Validator → Risk → Guard → Broker → buy system |
| SELL | همان با sell system |
| WAIT | skip، ثبت در DB |
| RE-EVALUATE | چرخه جدید از Data Reader |
