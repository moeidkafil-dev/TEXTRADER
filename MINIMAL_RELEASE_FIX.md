# TEXTRADER X 4.0.2 — Minimal Release Fix

## Fix
The Bitget public market bundle already contained valid `ohlcv` data, but Agent 1 only recognized bundles whose source name ended with `ohlcv`. Bitget uses the stable source name `bitget://rest/market`.

The minimal fix makes Agent 1 recognize a market bundle when its payload explicitly contains an `ohlcv` section, without changing the Bitget source contract or data schema.

## Regression coverage
Added an integration regression proving a `BitgetPublicSource` bundle reaches Agent 1 with the correct instrument and is not treated as `no market data`.

## Safety
Bitget remains public/read-only. No private API key or order endpoint is used by this release path.
