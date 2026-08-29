# NBM Q90 Exact-Threshold Price-Discrimination Development Audit V3

- Frozen: 2026-08-29 UTC, after terminal v2 and the bounded v3 candle/trade canary
- Identity: `noaa_nbm_v5_q90_exact_threshold_no_development_v3`
- Economic/model identity: unchanged from v1 and v2
- Parent terminal evaluation SHA-256: `8b1baa59900d28542ba176bf81548178ed9bee72129e536b72a42ab5bdc393d5`
- Production, credential, capital, recommendation, cohort, readiness, and order access: prohibited

## Sole Correction

V1 and v2 are terminal and receive no result. Retain v2's exact current/archived market discovery, legacy-window filter,
cross-partition comparison, and archived preference. Route the exact one-minute candle from that selected market
partition: archived selections use `/historical/markets/{ticker}/candlesticks`; live-only selections use
`/series/{series}/markets/{ticker}/candlesticks`. A missing, conflicting, or unknown partition is terminal. Do not
fallback or retry.

Parse and persist both `market_settled_ts` and `trades_created_ts` from the single exact cutoff payload. A selected
decision window strictly before `trades_created_ts` uses only `/historical/trades`; one at or after the cutoff uses only
`/markets/trades`. Require the same exact terminal cursor, ticker, `[14:30Z,14:35Z)` clock, canonical NO taker side,
count, price, and earliest/lower-price/trade-ID rank. Missing trades remain a zero-return nonfill. Do not merge, fallback,
retry, or query both trade partitions during evaluation.

This changes no model, probability, threshold, date, station, quote, fee, selection, fill, statistical, concentration,
drawdown, or authority rule. Every inspected row remains development evidence and receives no OOS credit.

## Unchanged Frozen Decision

Retain the exact 99 dates, 20 stations, Q90 `greater` contract and NO settlement arithmetic, prior-day 14:30Z candle,
displayed `1 - yes_bid.close` limit, `$0.55`–`$0.97` price, `0.933000` probability, `$0.0150` exact-fee edge, unchanged
quadratic multiplier-one fee, one EV-ranked submission per date, one contract, and the exact v1/v2 development gates.
Those gates still require at least 30 selected dates, ten stations, reliability error at most `0.05`, positive Brier
skill over displayed price, 30 public executable fills on 30 dates, positive exact-fee P&L, drawdown at most `$5`,
positive clustered-90 mean, nonnegative every station holdout, station share at most `0.15`, and one selection per date.

Retain the 3,000-request ceiling, four starts/second, no retry, terminal HTTP 429, raw request URL/body/hash evidence,
portable checksums, non-guaranteed `$100` projection, false 250-date scale gate, and every non-authorizing label. V3
receives exactly one public hosted run. Any failure is terminal without another v3 run. A pass permits only a separately
frozen future prospective identity; it creates no cohort, capital, production, recommendation, or order authority.
