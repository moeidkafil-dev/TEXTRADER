> پروژه: TRADER / textrader — مالک و مخترع: معید کفیل الناس (Moeid Kafilonas) — برند: XIR (اکسیر)
> تاریخ سند: 2026-09-22 (۱۴۰۵/۰۶/۳۱) — منبع حقیقت: `textrader.graphml` (SHA-256: 4eed88d72144592d)

# کاتالوگ اجزا (استخراج خودکار از GraphML)

### data reader (`n0`) — 3 زیرگره

data reader، context maker، context sender

### memory / database (`n1`) — 2 زیرگره

database، memory

### agent 1 (`n2`) — 10 زیرگره
توضیح گراف: انالیز داده ها و تصمیم گیری اولیه
llm، context compiler، decision system، planner، schduler، tool manager، tool executer، hidden memory، database، Observability

### agent 2 (`n3`) — 10 زیرگره
توضیح گراف: تصمیم اولیه رو دریبافت میکنه و تمام تلاششو میکنه تمام راه های شکست رو پیدا کنه
llm، context compiler، decision system، planner، schduler، tool manager، tool executer، hidden memory، database، Observability

### agent 3 (`n4`) — 10 زیرگره
توضیح گراف: تصمیم اولیه و راه های شکست رو دو ایجنت قبلی میگیره و تصمیم نهایی رو میگیره که ایا دوباره تصمیم گیری بشه و یا خرید و یا فروش و یا صبر
llm، context compiler، decision system، planner، schduler، tool manager، tool executer، hidden memory، database، Observability

### final tools (`n5`) — 4 زیرگره

sell system، buy system، skip، Observability

### memory (`n6`) — 42 زیرگره

memory architecture، memory manager

### DB manager agent architecture (`n7`) — 12 زیرگره

massgaes reciver، massages compile، massages reader، massages analyser، executer، DB analyser، DB Situation analyser، DB log maker، result maker، log maker، result sender، log sender

### message system (`n8`) — 10 زیرگره
توضیح گراف: هرکاری که تصمیم نهایی برای انجامش گرفته بشه جدا از لاگ شدن توی دیتابیس برای کاربر هم ارسال میشه و اگر طی ۲ دقیقه پاسخی نداده یا اوکی داد تصمیم انجام میشه ولی اگر کاربر تصمیم رو رد کرد انجام نمیشه
user`s emaile، user`s telegram، email sender، telegram message  sender، message maker، message send  manager، message reciver، message analyser، context maker، sender to agent

### DECISION ENGINE (`n9`) — 10 زیرگره

Observability، database، hidden memory، tool executer، tool manager، schduler، planner، decision system، context compiler، llm

### DECISION VALIDATOR (`n10`) — 10 زیرگره

Observability، database، hidden memory، tool executer، tool manager، schduler، planner، decision system، context compiler، llm

### RISK ENGINE (`n11`) — 10 زیرگره

Observability، database، hidden memory، tool executer، tool manager، schduler، planner، decision system، context compiler، llm

### EXECUTION GUARD (`n12`) — 10 زیرگره

Observability، database، hidden memory، tool executer، tool manager، schduler، planner، decision system، context compiler، llm

### BROKER / EXCHANGE (`n13`) — 10 زیرگره

Observability، database، hidden memory، tool executer، tool manager، schduler، planner، decision system، context compiler، llm

### Risk Engine (`n14`) — 21 زیرگره

Observability، database، hidden memory، tool executer، tool manager، schduler، planner، decision system، context compiler، llm، Position Size، Max Daily Loss، Max Drawdown، Exposure Limit، Leverage Limit، Stop Loss Validation، Take Profit Validation، Correlation Exposure، Portfolio Exposure، Trading Session Rules، Emergency Kill Switch
