# GFS MOS executable-price OOS predeclaration

- Frozen: 2026-08-30 UTC, before any GFS/market joint row, designated historical candle, or trade request
- Identity: `gfs_mos_station_rolling_wilson90_executable_no_oos_v1`
- Parent model: `gfs_mos_station_rolling_wilson90_v1`
- Parent result SHA-256: `2cdd2079394f6a3da426f90133fd0e69dc26e4015455f0edc355d78e835d0f62`
- Production, database, credential, capital, recommendation, cohort, readiness, and order access: prohibited

## Independent economic window

Keep the passing parent algorithm, score rounding, threshold, and station-specific 120-date/two-day-lag history exact.
Acquire a new complete GFS MOS/NCEI source window from 2025-09-01 through 2026-06-28. The first 121 dates through
2025-12-30 are history only. Evaluate exactly 180 later market dates from 2025-12-31 through 2026-06-28 on the ten
checksum-bound stations. This window, clock, and rule are frozen without inspecting their joint GFS-score/market-price
rows. Prior unrelated market studies do not receive credit and cannot alter this selection.

Use the same IEM GFS prior-calendar-day 12Z `n_x`, conservative 20:00Z availability, required semantic schema,
station-specific optional schema, exact NOAA ISD identity, and NOAA NCEI `TMAX` contracts as the passing parent. Require
3,010 complete station/date rows. Stop on HTTP 429 without retry and make exactly 13 source requests.

## Contract, score, quote, and fee identity

For each exact station/date, request both exact-event live and historical inventories, require each response to be
terminal, merge identical ticker identities, and reject any cross-partition conflict. An eligible contract must
be binary `greater`, have one finite integer `floor_strike`, null cap, exact subtitle `${floor + 1}° or above`, final
YES/NO result agreeing with NOAA (`NO` exactly when observed high is at most floor), and no provisional, MVE, or fee
waiver state. Its losing boundary is `floor + 0.5°F`; require GFS boundary distance `[4.0°F,8.0°F)`. Score it with the
unchanged one-sided Wilson-90 lower bound of the latest 120 same-station residuals no newer than target minus two dates.
Exact `0.9000` passes and `0.8999` fails.

At exactly 20:05:00Z on the prior calendar day, request one exact one-minute candle and define the displayed NO taker
limit as `1 - yes_bid.close`. Empty or boundary quotes are noncandidates. Require exact-cent price from `$0.55` through
`$0.97` and conservative edge `score - limit - fee(limit)` of at least `$0.0150`. Validate unchanged quadratic
multiplier-one fee identity and complete empty fee history for every series. One-contract taker fee is exactly
`ceil_0.0001(0.07 * p * (1-p))`. Rank eligible rows per date by descending edge, lower limit, higher score, then ticker;
submit at most one research order per date.

For each selected date, query public trades only in `[20:05:00Z,20:10:00Z)`. A fill requires
`taker_outcome_side=no`, count at least one, and NO price at or below the submitted limit. Select earliest time, lower
price, then trade ID. Nonfill submission return is zero. Filled win return is `1 - price - fee`; filled loss return is
`-price - fee`. No retry, extension, replacement, later crossing, candle-volume inference, or partial-date substitution
is allowed.

## Frozen decision

Initial economic evidence passes only if all source identities and these gates pass:

1. at least 100 one-per-date selections across at least eight stations;
2. positive Brier skill versus displayed NO price and every represented parent score band has at least 30 dates and
   absolute reliability error at most `0.05`;
3. at least 30 public executable fills on 30 dates;
4. positive exact-fee realized net P&L, drawdown at most `$5`, and strictly positive whole-date-clustered one-sided 90%
   lower submission return;
5. every represented leave-one-station-out clustered-90 lower return is nonnegative;
6. maximum station share at most `0.15` and maximum date share at most `0.01`; and
7. non-guaranteed contracts and gross-cost turnover to `$100` are reported only from the clustered-90 lower mean.

Use 10,000 deterministic whole-date bootstrap samples, at most 12,000 Kalshi requests, no more than four starts per
second, terminal HTTP 429, and one-day artifacts containing raw bodies, headers, URLs, hashes, source rows, quotes,
trades, exact fees, and portable checksums. Any failed source or economic gate rejects this identity without retuning,
window/station/price slicing, or evidence reuse.

A pass is still not trading authority. It permits a current indexed support check and a separate reviewed prospective
Stage 1 cohort/capital decision. Live evidence still requires at least 100 independent prospective dates and 30 settled
provider fills on 30 dates; scale requires at least 250 dates and a positive clustered-95 bound. Protected deployment,
explicit capital-risk authority, clean reconciliation, verified autonomous fills, and `$100` cumulative realized net
profit remain unfulfilled until directly proven.
