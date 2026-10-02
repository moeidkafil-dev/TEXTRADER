> پروژه: TRADER / textrader — مالک و مخترع: معید کفیل الناس (Moeid Kafilonas) — برند: XIR (اکسیر)
> تاریخ سند: 2026-09-22 (۱۴۰۵/۰۶/۳۱) — منبع حقیقت: `textrader.graphml` (SHA-256: 4eed88d72144592d)


# دیتابیس و API

## جداول اصلی
| جدول | فیلدهای کلیدی |
|---|---|
| cycles | cycle_id, started_at, status, reeval_count |
| data_bundles | id, cycle_id, source, ts, quality, payload, hash |
| contexts | context_id, cycle_id, hash, sections |
| decisions | id, cycle_id, agent(1/2/3), type, payload, ts |
| failure_paths | id, cycle_id, category(F1..F9), severity, text |
| orders | order_id, idempotency_key, side, instrument, size, sl, tp, status |
| risk_results | order_id, rule, pass, reason, ts |
| veto_events | order_id, notified_at, response(OK/REJECT/STOP/SILENCE), ts |
| memory_items | id, memory_type(1..28), agent_id?, content, meta, ts |
| audit_log | append-only |
| observability_events | component, level, trace_id, ts, data |

## API داخلی (REST/gRPC)
`POST /context`, `POST /agent/{1|2|3}/run`, `POST /decision/execute`, `POST /risk/check`, `POST /guard/submit`, `POST /killswitch/activate`, `POST /user/message`, `GET /cycles/{id}`.
