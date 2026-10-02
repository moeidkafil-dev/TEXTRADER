# TEXTRADER X 4.0.2 — Final Release Certificate

## Release state

This archive is the final **Bitget public-data / read-only / decision-only** release candidate for TEXTRADER X 4.0.2.
It is intended for paper analysis, backtesting, public market-data analysis, manual snapshot ingestion, and local web administration.

It does **not** authorize real Bitget order submission. The Bitget source is read-only and the execution boundary contains a decision-only interlock.

## Verified fixes

- Agent 1 accepts OHLCV when it is embedded in a market bundle payload, including `bitget://rest/market`.
- Agent 2 F4 validates the instrument from the OHLCV payload instead of relying only on a source-name suffix.
- Agent 2 F9 treats a valid bid+ask book as an explicit low-severity status (`no execution impossibility detected`) rather than a false execution failure.
- Agent 2 still emits F9 as `blocking` when a usable order book is missing or one side is empty.
- Agent 3's F9-blocking `RE-EVALUATE` contract remains covered by regression tests.
- Decision-only mode is enforced at the final execution boundary.

## Validation

- Full pytest suite: **108 passed** in the release build environment.
- Python compile check: **PASS**.
- CLI version/help smoke tests: **PASS** (`textrader 4.0.2`).
- Decision-only interlock tests: **PASS**.
- Web control-plane tests: **PASS**.
- Editable package build/install validation with `--no-build-isolation`: **PASS**.
- ZIP integrity: verified after archive creation.

## Real-market validation

The release was also exercised by the user's Kali environment against Bitget public market data.
Observed validation included:

- `BTC/USDT` public ticker/order book retrieval.
- 1-minute OHLCV retrieval.
- `textrader analyze BTC/USDT --source bitget --mode paper`.
- Correct `initial.instrument = BTC/USDT`.
- No `errors` in the real Bitget analysis cycle.
- The previous F4 false-positive disappeared.
- The previous F9 false-positive (`order book has liquidity both sides`) disappeared.

## Environment note

A global `pip check` in the isolated build container reports an unrelated pre-existing `moviepy`/`Pillow` mismatch outside TEXTRADER's declared dependency set. It is not used as a release failure criterion. The user's project virtual environment previously reported `No broken requirements found`.

## Scope boundary

"Final" here means the tested 4.0.2 read-only/decision-only product surface. It does not mean that trading profitability, market edge, or future upstream API availability is guaranteed. Real-money deployment requires a separately reviewed broker/execution release and operational controls.
