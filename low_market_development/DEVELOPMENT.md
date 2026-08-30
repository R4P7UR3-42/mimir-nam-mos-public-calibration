# Daily Low-Temperature Market Calibration Development V1

## Decision

This is a one-shot, training-only development test of whether an exact prior-day 18:00 UTC market price contains
conservative net value in either extreme contract of daily United States low-temperature events. It creates no trading
authority and cannot access the reserved evaluation series.

The family is materially distinct from the terminal high-temperature market-implied families: the settlement variable
is daily minimum temperature, the series universe is `KXLOWT*`, and no outcome before this freeze in the development
window was inspected by Mimir. The earlier low-temperature support audit inspected only 2026-07-30 through 2026-08-05;
those dates are excluded.

## Frozen data boundary

- Training market dates: 2025-12-13 through 2026-03-31 inclusive.
- Training stations: exact SHA-256-bound `training_series.json`.
- Reserved evaluation stations: exact SHA-256-bound `reserved_evaluation_series.json`.
- The two inventories begin from the alphabetically sorted public US `KXLOWT*` inventory split by alternating index.
  Because NYC and Atlanta were used for the pre-freeze source canary, both are assigned to training; the never-requested
  alphabetically last training member, Teterboro, is swapped into reserve to preserve 12/11 counts. The inventories are
  disjoint and cannot be changed after this commit.
- Training may query only the training inventory. It may read the reserved inventory locally to prove disjointness, but
  `evaluation_series_accessed` remains false and any evaluation-series URL is a terminal defect.
- Public source: unauthenticated Kalshi historical market/candlestick surfaces. No environment, credential, production
  database, private API, order endpoint, or provider mutation is allowed.
- Every training series must retain the exact public `Climate and Weather`, quadratic-fee, multiplier-one identity and
  an empty historical fee-change timeline.
- Historical market pages are cursor-exhausted at most ten pages per series, with at most 1,000 rows per page. Duplicate,
  malformed, cross-series, unsupported, provisional, or fee-waived rows fail closed. A market `occurrence_datetime`,
  when present, must be exactly the following UTC date because low-temperature events publish on the next-day report
  cycle. An exact finalized `result=scalar`, empty expiration value, and finite four-decimal settlement value inside
  `$0.0000`–`$1.0000` causes the entire series/date event to be excluded with no outcome credit; any adjacent scalar
  identity fails closed. Fractional range settlements are never reinterpreted as binary outcomes.
- Acquisition is capped at exactly 5,000 requests, at most four request starts per second, with no retry and terminal
  HTTP 429 behavior. Raw bodies and response headers are create-once and checksum-bound in the artifact.

The 2026-08-30 public source canary used training-only series requests. `KXLOWTATL` returned 522 terminal historical
markets and exact quadratic fee identity. `KXLOWTNYC` was queried to validate pagination and is therefore permanently
assigned to training: its two pages covered 1,188 markets and 199 event dates from 2025-12-13 through 2026-06-28.
The reserved inventory was never requested. The exact canary
body SHA-256 values were `9268e6469fe50215e70b637932ea77cb9344869b4d4ec4dbcfb3e4c520a798a2` for cutoff,
`1fa41e2ba4706768c199f7fdac3a0a5e69738a05b4d885c73b006530ac544c05` for Atlanta markets,
`8f757200a42e7ea43a55331280480e968c9363d0367c8b1983d5aaa313359d02` for NYC page one, and
`19eb821827863cd9b4f5e3598c93ad1e8a390baddf4d8b60657b62ebcd00bc77` for NYC page two.

## Exact candidate cells

For every exact series/date event in the frozen window, select only:

- `upper/greater`: the unique binary contract with `strike_type=greater`, a floor and no cap. A NO outcome means the
  daily minimum did not exceed the high-tail boundary.
- `lower/less`: the unique binary contract with `strike_type=less`, a cap and no floor. A NO outcome means the daily
  minimum did not fall below the low-tail boundary.

At exactly 18:00 UTC on the preceding date, read the exact 60-minute candle ending at that timestamp. The one-contract
NO decision limit is `1 - YES bid close`. Missing candles/bids and boundary prices are recorded as non-candidates.
Evaluate only these eight predeclared cells:

1. upper `[0.70,0.80)`
2. upper `[0.80,0.90)`
3. upper `[0.90,0.95)`
4. upper `[0.95,0.97]`
5. lower `[0.70,0.80)`
6. lower `[0.80,0.90)`
7. lower `[0.90,0.95)`
8. lower `[0.95,0.97]`

Exact `$0.70` and `$0.97` pass. `$0.6999` and `$0.9701` fail. The conservative maximums are `$0.7999`, `$0.8999`,
`$0.9499`, and `$0.9700`. Exact one-contract taker fees use `ceil($0.07 * p * (1-p), $0.0001)`.

## Training decision

For each cell, compute the exact-fee return at the decision limit and resample whole market dates with a fixed
deterministic sampler. Because eight cells are inspected, the primary lower bound uses a predeclared one-sided
Bonferroni tail of `0.10 / 8 = 0.0125`. A cell is admissible only when all conditions hold:

- at least 100 rows, 60 independent market dates, and eight training series;
- at most 20% of rows from one series and at most 5% from one date;
- the 1.25th-percentile whole-date clustered mean exact-fee return is at least `$0.015`;
- every leave-one-series-out 10th-percentile whole-date clustered mean return is nonnegative;
- the same 1.25th-percentile clustered outcome probability, evaluated at the cell's conservative maximum price and
  exact fee, has edge at least `$0.015`.

The frozen score is the Jeffreys posterior mean `(wins + 0.5) / (rows + 1)`, rounded to eight decimals. It is a research
score, not a calibrated probability or profit claim. If multiple cells pass, select the cell with the greatest primary
clustered lower return, then the fixed menu order above. If none pass, terminate the family. No thresholds, dates,
stations, price cells, clock, fee rule, or selector may be changed after seeing this result.

## Successor boundary

Training never supplies OOS, execution, capital, cohort, recommendation, or order authority. A passing result permits
only a second reviewed commit that hard-codes the exact selected cell, score, training probability floor, artifact
hashes, and untouched reserved inventory before querying it. That successor must retain one selection per date, exact
five-minute public trade evidence, exact fees, Brier skill versus the displayed decision price, reliability, whole-date
clustered 90%/95% bounds, leave-one-station-out results, drawdown, concentration, at least 30 executable settled dates,
at least 100 independent OOS dates for live evidence, and at least 250 for scale evidence. `$100` remains a non-guaranteed
projection until separate capital-risk authority, protected deployment, clean reconciliation, and real autonomous fills.
