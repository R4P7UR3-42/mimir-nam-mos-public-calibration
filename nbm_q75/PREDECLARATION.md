# NBM Q75 Station-Robust Midnight Split Development Audit

- Frozen: 2026-08-29 UTC, after terminal Q90 timing evidence and before any Q75 candle/trade request
- Identity: `noaa_nbm_v5_q75_station_robust_midnight_split_development_v1`
- Parent NBM QMD evaluation SHA-256: `8b1baa59900d28542ba176bf81548178ed9bee72129e536b72a42ab5bdc393d5`
- Production, credential, capital, recommendation, cohort, readiness, and order access: prohibited

## Distinct Hypothesis

The exact Q90 family had broad contract inventory but no held-out executable quotes. Q75 is a distinct, more central
forecast event with potentially deeper pricing. The parent full-window diagnostic observed `0.832500` success at nominal
`0.75`, but nominal Q75 failed calibration and that inspected aggregate cannot be used as the score.

Use only May 8 through June 26 (50 dates × 20 stations) to derive a conservative Q75 NO score. For each station/date,
success is observed high less than or equal to exact integer Q75. Compute the fixed-seed 10,000-sample whole-date
clustered one-sided-90 lower success mean globally and after excluding each station. The frozen score is the minimum of
the global and all 20 leave-one-station-out lower means, rounded down to `0.0001`. Require complete coverage and score at
least exact `0.7500`; otherwise stop before market acquisition. The score is a development estimate, not calibrated OOS
probability.

Evaluate only June 27 through August 14 (49 dates), which are already-consumed development dates but untouched by this
Q75 price/fill hypothesis. Select the exact binary `greater` contract with floor strike equal to Q75, null cap, subtitle
`${Q75 + 1}° or above`, finalized result agreeing with observed-high arithmetic, and exact current series/event identity.
Use the moving market/candle/trade partitions and bounded transport recovery already frozen by the Q90 successors.

The sole decision clock is market-date `00:00Z`, selected by the prior Q90 training-only liquidity result and still
before the earliest US station's local observation date. Use only `1 - yes_bid.close`. Require exact one-cent NO limit
`$0.50` through `$0.85` and conservative edge `score - limit - ceil_0.0001(0.07*limit*(1-limit))` at least `$0.0150`.
Rank one candidate per date by descending edge, lower limit, then ticker. Query one exact public NO-taker trade window
`[00:00Z,00:05Z)`, require count at least one and price no greater than limit, and select earliest/lower-price/trade-ID.
Nonfills return zero and cannot retry, extend, or infer execution.

## Frozen Development Decision

Held-out development support passes only with every source check and:

1. at least 15 selected independent dates and five stations;
2. observed success within `0.07` of the frozen score and positive Brier skill versus displayed NO limit;
3. at least ten public fills on ten dates;
4. positive exact-fee P&L, drawdown at most `$5`, and strictly positive whole-date clustered-90 mean submission return;
5. every represented leave-one-station-out clustered-90 mean nonnegative;
6. station share at most `0.25` and exactly one selection per date; and
7. a non-guaranteed `$100` contracts/turnover projection only from the positive clustered lower mean.

Retain exact 20-series quadratic fee/no-history identity, 3,000 total attempts, four starts/second, at most three attempts
only for transport/5xx with 1s/2s delays, terminal 429/other 4xx/malformed identity, raw attempt evidence, and portable
checksums. This identity receives one public hosted run and no rerun or subgroup/threshold tuning.

A pass remains development support only. It permits a separately frozen future prospective identity beginning after
this result, but creates no independent OOS credit, cohort, capital, production, recommendation, or order authority.
Live progression still requires at least 100 future dates, 30 settled provider fills on 30 dates, exact-fee positive
conservative EV, bounded drawdown/concentration, explicit capital authority, protected deployment, clean reconciliation,
and verified autonomous real-money outcomes. Scale remains gated at 250 future dates and clustered 95% evidence.
