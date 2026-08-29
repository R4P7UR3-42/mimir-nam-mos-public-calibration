# NBM Q90 Exact-Threshold Price-Discrimination Development Audit

- Frozen: 2026-08-29 UTC, before any historical candle or trade request
- Identity: `noaa_nbm_v5_q90_exact_threshold_no_development_v1`
- Station/series inventory SHA-256: `98a46e35e06c485cfcaa2b2632a2559b90cb5012491f718f5a570d13a26cdbbd`
- Parent terminal evaluation SHA-256: `8b1baa59900d28542ba176bf81548178ed9bee72129e536b72a42ab5bdc393d5`
- Production, credential, capital, recommendation, cohort, readiness, and order access: prohibited

## Purpose And Evidence Boundary

Measure whether the predeclared NOAA NBM v5 Q90 probability has historical executable-price support when mapped to the
exact Kalshi daily-high greater contract whose NO settlement event is the same Q90 event. The parent 100-date result
reported Q90 observed success `0.941500`, one-sided whole-date-clustered 95% lower success `0.933000`, and 20/20
passing station holdouts, but its full five-level diagnostic failed. It created no model or trading authority.

This successor freezes `0.933000` as a development-only conservative probability. It does not reinterpret the parent
decision as passing. The May 7 KATL market shape and result were inspected as a source canary before this file; exclude
the entire `2026-05-07` market date. Use the remaining 99 already-consumed development dates from `2026-05-08` through
`2026-08-14`. No row, subgroup, station, price, or outcome from those 99 dates has been inspected for this economic
mapping before this commit.

Historical results are development support only. Independent prospective credit for this exact identity may begin no
earlier than market date `2026-08-30`. A successful development audit permits only a separate prospective ledger and
bounded Stage 1 execution-evidence cohort review; it is not OOS profit, fill, capital, or trading authority.

## Exact Causal Contract And Quote

Use the four checksum-bound parent NBM captures and the 20 exact station/series mappings. For every station/date, select
the published Q90 integer `max_f`. Discover all pages of the exact Kalshi historical series, allowing at most ten pages
per series and requiring a terminal empty cursor. Parse the event date from the exact event ticker. The only eligible
market has:

- `market_type=binary`, `strike_type=greater`, `floor_strike` exactly equal to Q90, and null `cap_strike`;
- one exact series/event identity and final result `yes` or `no`;
- an exact displayed subtitle of `${Q90 + 1}° or above`; and
- `result=no` if and only if the NOAA observed high is less than or equal to Q90.

Missing or differently struck Q90 greater contracts are explicit noncandidates. Duplicate event identities, ambiguous
matching contracts, result disagreement, malformed strikes, provisional/MVE identity when present, or a non-null fee
waiver is terminal.

The causal decision clock is exactly `14:30:00Z` on the prior calendar date, after the frozen NBM `14:15:00Z` source
availability ceiling. Request exactly one one-minute historical candle with `end_period_ts` equal to that clock. The
displayed NO taker limit is `1 - yes_bid.close`; midpoint, last trade, later candle, missing-side imputation, and a
different clock are prohibited. Empty candles and missing or boundary bids are explicit noncandidates.

Require a fresh NO limit from `$0.55` through `$0.97`, at least one cent granularity, and conservative exact-fee edge
`0.933000 - limit - fee(limit)` of at least `$0.0150`. Exact `$0.55`, `$0.97`, and `$0.0150` pass; immediately adjacent
outside values fail. Rank all eligible station rows on a date by descending conservative edge, then lower limit, then
ticker, and retain at most one research submission per date.

## Fee And Executable-Trade Identity

Before price evaluation, require each exact series to report `fee_type=quadratic`, provider `fee_multiplier=1`, and an
empty complete historical fee-change list. For one direct taker contract at price `p`, compute
`ceil_0.0001(0.07 * p * (1 - p))`. A changed, missing, maker, waived, differently rounded, or ambiguous fee identity is
terminal.

For each selected date, query public historical trades only in `[14:30:00Z,14:35:00Z)` for the exact ticker. A fill
exists only for a provider row with `taker_outcome_side=no`, count at least one, and NO price no greater than the frozen
limit. Select the earliest qualifying trade, then lower price and trade ID. Use one contract at the actual trade price
and exact fee. No qualifying trade returns zero submission P&L; it may not be replaced, retried, extended, crossed later,
or inferred from candle volume.

## Frozen Development Decision

The development diagnostic passes only if every source and identity check passes and all of these hold:

1. at least 30 selected independent dates and at least ten represented stations;
2. selected-set observed success differs from `0.933000` by at most `0.05` and its Brier skill versus displayed NO
   limit is strictly positive;
3. at least 30 qualifying public taker trades occur over at least 30 dates;
4. actual-trade realized net P&L is positive, maximum drawdown is at most `$5.00`, and the one-sided whole-date-clustered
   90% lower mean submission return is strictly positive;
5. every represented leave-one-station-out clustered-90 mean is nonnegative;
6. maximum station share is at most `0.15`, maximum date share is one divided by selected dates, and one selection per
   date is exact; and
7. the non-guaranteed contracts-to-`$100` and gross-cost turnover projection are reported from the clustered-90 lower
   mean only.

The network budget is exactly 3,000 public requests at no more than four starts per second. Stop on HTTP 429 without
retry. Persist raw bodies, headers, request URLs, hashes, absence reasons, selections, trades, exact fees, and portable
checksums. Any source or diagnostic failure is terminal for this development identity: publish it without rerun,
retuning, threshold changes, station/date slicing, or evidence pooling.

A pass still requires a new reviewed prospective identity beginning August 30, independent calibration and exact-fee
EV over at least 100 later dates, 30 fully settled provider fills on 30 dates, bounded drawdown/concentration, explicit
capital-risk authority, protected deployment, clean reconciliation, and verified autonomous real-money outcomes before
it can contribute to the `$100` objective. The 250-date clustered-95 scale gate remains false until independently met.
