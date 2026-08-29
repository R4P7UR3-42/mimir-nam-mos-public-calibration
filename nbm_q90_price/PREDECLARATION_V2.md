# NBM Q90 Exact-Threshold Price-Discrimination Development Audit V2

- Frozen: 2026-08-29 UTC, after terminal v1 source rejection and the bounded v2 source canary
- Identity: `noaa_nbm_v5_q90_exact_threshold_no_development_v2`
- Economic/model identity: unchanged from v1
- Parent terminal evaluation SHA-256: `8b1baa59900d28542ba176bf81548178ed9bee72129e536b72a42ab5bdc393d5`
- Production, credential, capital, recommendation, cohort, readiness, and order access: prohibited

## Sole Correction

V1 is terminal and receives no result. V2 corrects only its demonstrated source-scope defect. Query and persist the
public historical cutoff once. For each exact series, exhaust at most ten pages from both:

1. current `/markets`, bounded to close times `2026-05-08T00:00:00Z` through exclusive
   `2026-08-16T00:00:00Z`, with limit 1,000 and `mve_filter=exclude`; and
2. archived `/historical/markets`, with exact `series_ticker` and limit 1,000.

Require terminal nonrepeating cursors. Parse a syntactically exact date suffix from every event. Rows outside the fixed
May 8–August 14 development window may use a provider-returned legacy prefix and are ignored before current-identity
validation. Every in-window row must use the exact current series, event, and market prefix. Merge identical tickers
across partitions only when event, market type, strike type, strikes, result, subtitle, status, and optional
provisional/MVE/fee-waiver identity agree exactly; prefer the archived representation after agreement. Conflicting or
duplicate in-window identity is terminal.

This is not a threshold, model, probability, date, station, price, fee, side, ranking, fill, statistical, or authority
change. The already-inspected Atlanta candle payloads remain development evidence; no v2 result is OOS evidence.

## Unchanged Frozen Decision

Retain the exact 99 dates, 20 stations, Q90 `greater` contract and NO settlement arithmetic, prior-day 14:30Z candle,
displayed `1 - yes_bid.close` limit, `$0.55`–`$0.97` price, `0.933000` conservative probability, `$0.0150` exact-fee
edge, quadratic multiplier-one fee with no history, one EV-ranked selection per date, and public NO-taker trade in
`[14:30Z,14:35Z)` at or below the limit. Retain the exact v1 request-rate/3,000 ceiling, no retry, HTTP-429 stop, raw
evidence, and portable checksum requirements.

V2 passes only with every v1 development gate: at least 30 independent selected dates, ten stations, reliability error
at most `0.05`, positive Brier skill over displayed price, 30 public executable fills on 30 dates, positive exact-fee
P&L, drawdown at most `$5`, strictly positive whole-date clustered-90 mean, nonnegative every leave-one-station-out
clustered-90 mean, station share at most `0.15`, and exact one-per-date concentration. Report the non-guaranteed `$100`
projection from that conservative lower mean. Scale remains false.

This distinct v2 receives exactly one public hosted run. Source or diagnostic failure is terminal without another v2
run. A pass permits only a separate prospective identity beginning after this result; it creates no OOS credit, cohort,
capital, production, recommendation, or order authority.
