# V2 Moving-Partition Source Canary

- Captured: 2026-08-29 UTC, after terminal v1 and before freezing v2
- Scope: public Austin inventory schema only; no candles or trades
- Request count: two, with no retry
- Portable `SHA256SUMS` SHA-256: `1c28134f4e3ac0b8d77bfe2981a844978d500b1dd463e5b4c028cc2ea0f13310`

The public historical cutoff returned `market_settled_ts=2026-06-29T00:00:00Z` with payload SHA-256
`5cd5fdab9b9fb78c6a152a750fa8785703c82c83620768b92685d269a062cae4`. The bounded current `/markets` request used
the exact Austin series, close-time interval `2026-05-08T00:00:00Z` through exclusive `2026-08-16T00:00:00Z`, limit
1,000, and `mve_filter=exclude`. It returned 330 rows, an empty terminal cursor, only the `KXHIGHAUS` prefix, and
complete daily event inventory from June 21 through August 14; its payload SHA-256 is
`56c64b963989b639eefde57cd0861873e8c0728b116e18813c6f81545699bec6`.

Combined with v1's archived Austin artifact, this proves the source is intentionally split: archived pages contain the
older portion plus legacy pre-window aliases, while the current endpoint contains the recent settled portion. It does
not prove a Q90 candidate, quote, fill, profitability, or future support result.
