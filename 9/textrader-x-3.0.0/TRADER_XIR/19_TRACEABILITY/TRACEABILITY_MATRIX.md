> پروژه: TRADER / textrader — مالک و مخترع: معید کفیل الناس (Moeid Kafilonas) — برند: XIR (اکسیر)
> تاریخ سند: 2026-09-22 (۱۴۰۵/۰۶/۳۱) — منبع حقیقت: `textrader.graphml` (SHA-256: 4eed88d72144592d)

# ماتریس ردیابی

| گره گراف | برچسب | نیازمندی | جزء | تست |
|---|---|---|---|---|
| n0::n0 | data reader | REQ-DR-01 | C01 Data Reader | TST-DR-01 |
| n0::n0 | data reader | REQ-DR-02 | C01 Data Reader | TST-DR-02 |
| n1 | memory / database | REQ-DR-02 | C01 Data Reader | TST-DR-02 |
| n0::n1 | context maker | REQ-DR-03 | C02 Context Maker | TST-DR-03 |
| n0::n2 | context sender | REQ-DR-04 | C03 Context Sender | TST-DR-04 |
| n2::n1 | context compiler | REQ-DR-04 | C03 Context Sender | TST-DR-04 |
| n2 | agent 1 | REQ-AG-01 | C04-C06 Agents | TST-AG-01 |
| n3 | agent 2 | REQ-AG-01 | C04-C06 Agents | TST-AG-01 |
| n4 | agent 3 | REQ-AG-01 | C04-C06 Agents | TST-AG-01 |
| n2 | agent 1 | REQ-AG-02 | C04 Agent 1 | TST-AG-02 |
| n3 | agent 2 | REQ-AG-03 | C05 Agent 2 | TST-AG-03 |
| n4 | agent 3 | REQ-AG-04 | C06 Agent 3 | TST-AG-04 |
| n4 | agent 3 | REQ-AG-05 | C06 Agent 3 | TST-AG-05 |
| n0 | data reader | REQ-AG-05 | C06 Agent 3 | TST-AG-05 |
| n2 | agent 1 | REQ-AG-06 | C04-C06 Agents | TST-AG-06 |
| n3 | agent 2 | REQ-AG-06 | C04-C06 Agents | TST-AG-06 |
| n4 | agent 3 | REQ-AG-06 | C04-C06 Agents | TST-AG-06 |
| n1 | memory / database | REQ-AG-06 | C04-C06 Agents | TST-AG-06 |
| n6::n0 | memory architecture | REQ-MEM-01 | C07 Memory Architecture | TST-MEM-01 |
| n6::n0::n23 | Agent Local Memory | REQ-MEM-02 | C07 Memory Architecture | TST-MEM-02 |
| n6::n1 | memory manager | REQ-MEM-03 | C08 Memory Manager | TST-MEM-03 |
| n6::n1::n8 | being in sleep mode | REQ-MEM-04 | C08 Memory Manager | TST-MEM-04 |
| n6::n1::n5 | finde junks | REQ-MEM-05 | C08 Memory Manager | TST-MEM-05 |
| n6::n1::n6 | tables cleaner | REQ-MEM-06 | C08 Memory Manager | TST-MEM-06 |
| n7 | DB manager agent architecture | REQ-DB-01 | C09/C10 DB | TST-DB-01 |
| n8 | message system | REQ-MSG-01 | C11 Message System | TST-MSG-01 |
| n8 | message system | REQ-MSG-02 | C11 Message System | TST-MSG-02 |
| n8 | message system | REQ-MSG-03 | C11 Message System | TST-MSG-03 |
| n9 | DECISION ENGINE | REQ-DEC-01 | C12 Decision Engine | TST-DEC-01 |
| n10 | DECISION VALIDATOR | REQ-DEC-02 | C13 Decision Validator | TST-DEC-02 |
| n14::n10 | Position Size | REQ-RSK-01 | C14 Risk Engine | TST-RSK-01 |
| n14::n11 | Max Daily Loss | REQ-RSK-02 | C14 Risk Engine | TST-RSK-02 |
| n14::n12 | Max Drawdown | REQ-RSK-03 | C14 Risk Engine | TST-RSK-03 |
| n14::n13 | Exposure Limit | REQ-RSK-04 | C14 Risk Engine | TST-RSK-04 |
| n14::n14 | Leverage Limit | REQ-RSK-05 | C14 Risk Engine | TST-RSK-05 |
| n14::n15 | Stop Loss Validation | REQ-RSK-06 | C14 Risk Engine | TST-RSK-06 |
| n14::n16 | Take Profit Validation | REQ-RSK-07 | C14 Risk Engine | TST-RSK-07 |
| n14::n17 | Correlation Exposure | REQ-RSK-08 | C14 Risk Engine | TST-RSK-08 |
| n14::n18 | Portfolio Exposure | REQ-RSK-09 | C14 Risk Engine | TST-RSK-09 |
| n14::n19 | Trading Session Rules | REQ-RSK-10 | C14 Risk Engine | TST-RSK-10 |
| n14::n20 | Emergency Kill Switch | REQ-RSK-11 | C14 Risk Engine | TST-RSK-11 |
| n14 | Risk Engine | REQ-RSK-12 | C14 Risk Engine | TST-RSK-12 |
| n11 | RISK ENGINE | REQ-RSK-12 | C14 Risk Engine | TST-RSK-12 |
| n12 | EXECUTION GUARD | REQ-EG-01 | C15 Execution Guard | TST-EG-01 |
| n13 | BROKER / EXCHANGE | REQ-BRK-01 | C16 Broker/Exchange | TST-BRK-01 |
| n5 | final tools | REQ-FT-01 | C17 Final Tools | TST-FT-01 |
| n2::n9 | Observability | REQ-OBS-01 | C18 Observability | TST-OBS-01 |
| n3::n9 | Observability | REQ-OBS-01 | C18 Observability | TST-OBS-01 |
| n4::n9 | Observability | REQ-OBS-01 | C18 Observability | TST-OBS-01 |
| n5::n3 | Observability | REQ-OBS-01 | C18 Observability | TST-OBS-01 |
| n14::n20 | Emergency Kill Switch | REQ-KS-01 | C19 Kill Switch | TST-KS-01 |

## گروه‌های سطح‌بالای بدون نگاشت مستقیم
ندارد
