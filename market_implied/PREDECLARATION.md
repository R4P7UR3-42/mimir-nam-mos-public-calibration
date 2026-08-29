# 18Z Barbell Market-Implied NO Predeclaration

- Frozen: 2026-08-29 UTC before any successor training or evaluation request
- Identity: `daily_high_top_tail_market_implied_barbell_no_18z_v1`
- Training inventory SHA-256: `a8601388f04677a38aa3194a93c45ad77a1ef933a65ae9657e09a1e24f98eab1`
- Evaluation inventory SHA-256: `ac365222dee4f724a98d67fbd002d8130f2785b50e9590485fe62bbec9fa2b0c`
- Production, database, credential, capital, recommendation, cohort, and order access: prohibited

## Distinct development hypothesis and untouched split

The terminal broad-bin 18Z run found a nonmonotone development pattern: every 0.85–0.90 row and every 0.95–0.97 row
won, while losses concentrated below 0.85 and from 0.90 through below 0.95. Freeze exactly those two disjoint price
bands as a new barbell hypothesis. This is deliberately post-development model selection, not profitability evidence;
only the untouched evaluation below can validate it. The broad-bin result cannot be reinterpreted or credited.

Use the ten exact series in `training_series.json` from 2026-02-11 through 2026-03-19. The first five are inspected
development stations; the five added stations have not been requested for these dates and become training data only.
Use the ten disjoint series in `evaluation_series.json` on exactly 100 later dates from 2026-03-21 through 2026-06-28.
No successful in-window request for those ten series occurred before this freeze. Resample whole evaluation dates.
Any pre-commit evaluation access invalidates the family.

## Exact source, quote, fee, and request identity

Use only Kalshi's public REST API at `external-api.kalshi.com`. Fetch `/historical/cutoff` once and require both market
and trade cutoffs strictly after the complete frozen window. For every series/date, construct the zero-padded event
ticker and request `/historical/markets?event_ticker=...&limit=1000`. Require one response, an empty cursor, complete
coverage, one unique binary `greater` contract, finite floor, null cap, final yes/no result, matching event/date/ticker,
and fail-closed optional provisional, MVE, occurrence, and fee-waiver fields.

Request exactly one 60-minute historical candle ending at 18:00:00Z on the prior calendar date. Use only finite
`yes_bid.close`; the NO limit is `1 - yes_bid.close`. Empty or boundary quotes are explicit noncandidates. Fetch and
bind every series' unchanged quadratic fee identity and history. One-contract taker fee is exactly
`ceil_0.0001(0.07 * p * (1-p))`. Persist URLs, headers, raw bodies, hashes, and absence reasons.

Stop on HTTP 429 without retry, pace at no more than four requests per second, and cap the run at 5,000 requests. The
maximum projection is one cutoff, 40 fee requests, 370 training markets, 370 training candles, 1,000 evaluation
markets, 1,000 evaluation candles, and 100 trade requests: 2,881 total before noncandidate reductions.

## Frozen training rule

The only bands are `[0.8500,0.9000)` and `[0.9500,0.9700]`; every adjacent price fails. For each band use every
candidate training row. Compute the one-sided 90% Wilson lower success probability with fixed
`z=1.2815515655446004`. This row-level training statistic is only a frozen score estimator, not independent-date
evidence. A band is admissible only with at least 25 rows, at least 20 market dates, and Wilson lower probability minus
the band maximum price minus exact fee at that maximum at least `$0.0150`. Exact boundaries pass. If neither band is
admissible, stop before evaluation and reject. No price, sample, date, score, edge, fee, or station rule may change.

## Frozen OOS selection and public executable fills

For each evaluation date, candidates must be in an admitted band and have Wilson score minus actual limit minus exact
fee at least `$0.0150`. Rank by descending conservative edge, lower limit, then ticker, selecting at most one. Require
exactly one selection on all 100 dates; a missing date fails and cannot be substituted.

For each selection query public historical trades only in `[18:00:00Z,18:05:00Z)` on the prior date. A fill requires
`taker_outcome_side=no`, count at least one, and NO price at or below the submitted limit. Select earliest time, lower
price, then trade ID. Nonfill return is zero. Filled win return is `1 - fill_price - fee`; filled loss return is
`-fill_price - fee`. There is no retry, extension, replacement, or candle-volume inference.

Initial evidence passes only if every source/checksum identity is exact; all 100 dates select across at least eight of
ten stations; score Brier skill versus displayed NO limit is positive; every selected band spans at least 20 evaluation
dates with absolute calibration error at most 0.05; at least 30 public fills span 30 dates; exact-fee P&L is positive;
maximum drawdown is at most `$5`; whole-date-clustered one-sided 90% lower submission return is positive; every
leave-one-station-out clustered 90% lower return is nonnegative; maximum station share is at most 0.20; and date share
is exactly 0.01. Report non-guaranteed contracts and turnover to `$100` from the lower bound.

The 250-date clustered-95 scale gate remains false. A pass creates no recommendation, capital, deployment, order,
Stage 2, scale, or profit authority; it permits only a separate reviewed Stage 1 and capital-risk decision. Any source,
training, execution, or OOS failure is terminal and must be published without retuning or reuse for this hypothesis.
