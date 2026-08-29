# Terminal V2 Source Result

- Identity: `noaa_nbm_v5_q90_exact_threshold_no_development_v2`
- Frozen commit: `52bc098717ed1afa7a18ad94218acc323dc41886`
- Annotated tag: `noaa-nbm-q90-price-development-v2`
- Sole run: `33230730969`, attempt 1
- Outcome: terminal candle-partition rejection before economic evaluation
- Portable artifact `SHA256SUMS` SHA-256: `544512f9121ee32234dac00be46f65f42ce9071f9287049668eaa1a540ee7993`
- Workflow log SHA-256: `ebf6298a659baa01bd3cca33cd4fc43113ea3137c62818f6d571ec699fc0d6d5`

The public runner passed every frozen hash and all eleven v2 tests. Its market-partition correction then passed the real
source boundary, including complete current/archived discovery and exact in-window identity. It stopped without retry
on request 56: historical candlesticks returned HTTP 404 for current-partition market
`KXHIGHTATL-26JUL11-T94`. The sealed error body hashes to
`73cd6ca91e8273987fdccd966b7548892cc3e7c9596c1033e76244c19ce13d2a`.

V2 produced no report, selections, trade requests, fill result, P&L, OOS evidence, capital authority, cohort,
recommendation, production change, or order. V2 is terminal and must not be rerun. A distinct v3 may select the candle
endpoint from the already-validated market partition and the trade endpoint from the provider's exact
`trades_created_ts` cutoff; no economic rule may change.
