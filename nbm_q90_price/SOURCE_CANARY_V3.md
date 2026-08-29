# V3 Candle And Trade Partition Canary

- Captured: 2026-08-29 UTC, after terminal v2 and before freezing v3
- Exact market: `KXHIGHTATL-26JUL11-T94`
- Exact decision window: `2026-07-10T14:30:00Z` through exclusive `14:35:00Z`
- Request count: three, with no retry
- Portable `SHA256SUMS` SHA-256: `ad6884b8a709894258bb55bc7e571792880c01f0b26a652501ad9e1b657e0d20`

The current-partition candle endpoint returned HTTP 200 with the exact ticker and an empty one-minute candle list;
payload SHA-256 `1713501ccaf3c7ae12cb9305db9a4c482ed8167fde9bca41b0c2f05705f0b934`. Both current
`/markets/trades` and archived `/historical/trades` returned HTTP 200 with the same empty terminal trade schema; each
payload hashes to `ce91679332b1b83d2574366e4cc72f6d41bf656ccc2fa9cf574ee4f9ac6809e7`.

Together with the exact cutoff payload already captured for v2, this proves that candle routing follows the selected
market partition and trade routing can follow `trades_created_ts`. It does not establish a quote, fill, profitability,
or future-support result.
