# GFS MOS daily-precipitation development freeze

- Identity: `gfs_mos_local_day_precipitation_jeffreys_wilson95_development_v1`
- State: training/development only; no trading or production authority
- Frozen history: 2024-01-01 through 2024-12-31
- Frozen development targets: 2025-01-01 through 2025-11-23
- Reserved independent evaluation: exactly 2025-11-24 through 2026-07-31 (250 dates)

## Question and sources

Test whether public NOAA GFS Model Output Statistics can produce a causal, conservatively scored daily no-rain
hypothesis for the 20 U.S. city/station identities in the checksum-bound root `stations.json`. This phase may read only
the history and development dates above. It must never request, derive, inspect, or report a forecast or precipitation
outcome on a reserved evaluation date.

Use the Iowa Environmental Mesonet public NWS MOS archive with exact model `GFS` and the prior calendar date's exact
12:00:00Z runtime. `p06` is the NOAA six-hour probability of at least 0.01 inch liquid-equivalent precipitation and is
valid for the six-hour interval ending at `ftime`. Require the semantic fields `runtime`, `ftime`, `model`, `p06`, and
`station`. For each local calendar date, select every six-hour interval that intersects `[00:00,24:00)` in the station's
checksum-bound IANA time zone. This normally selects four or five intervals. Collapse only exact semantic duplicates;
missing, conflicting, wrong-station/model/runtime, non-six-hour-clock, out-of-range, or incomplete local-day coverage
fails closed.

Use exact NOAA NCEI Daily Summaries `PRCP` under a freshly captured ICAO/WBAN-to-GHCN identity. A nonzero value is rain.
A zero value whose measurement flag is `T` is also rain; it must never be relabeled no-rain. Reject malformed attributes,
nonblank quality flags, unsafe measurement flags, impossible values, duplicate identity, or incomplete coverage. NCEI is
a model label proxy, not the Weather Company settlement source; even a positive result cannot establish exchange outcome
agreement without later prospective official Kalshi settlements.

The acquisition is credential-free, has exactly 23 requests (20 IEM, one ISD identity, and two NCEI outcome requests),
has no retry, stops on HTTP 429, and refuses a production Mimir host. Persist raw response bytes, headers, URLs, hashes,
the complete station/date rows, and a portable checksum manifest.

## Frozen model

For a station/date, define the raw local-day no-rain proxy as the product of `(1 - p06 / 100)` across all selected
intersecting six-hour intervals. This is a feature only; interval independence is not asserted.

Assign the proxy to exactly one fixed band:

1. `[0.00,0.50)`
2. `[0.50,0.70)`
3. `[0.70,0.80)`
4. `[0.80,0.90)`
5. `[0.90,0.95)`
6. `[0.95,1.0001)`

For every development target, use only complete same-station/same-band labels in the 365 calendar dates ending two
dates before the target. Require at least 30 labels. The probability estimate is the Jeffreys posterior mean
`(no + 0.5)/(n + 1)`. The conservative score is the one-sided 95% Wilson lower bound. Compute a causal same-station
365-date Jeffreys climatology as a benchmark. No threshold, band, window, station, date, price, or side may be selected
after observing development results.

An economic screen is allowed only at the fixed hypothetical one-contract NO ask `$0.70`. Use the exact quadratic
taker fee `0.07 * price * (1 - price)` at four-decimal precision and require conservative edge at least `$0.015`.
Realized screen return is `$1 - price - fee` for no-rain and `-$price - fee` for rain. This is price-ceiling support, not
historical quote availability, fill evidence, or a profit claim.

Rank at most one eligible row per market date by higher conservative score, then station ID. Resample whole market dates
with the fixed full-state deterministic sampler; never resample rows independently.

## Development gates

All must pass before an unchanged 250-date evaluation workflow may be frozen:

- at least 100 selected independent dates and at least 10 selected stations;
- maximum selected station share at most `0.20` and maximum date share at most `0.01`;
- Jeffreys-model Brier score strictly below both the raw proxy and causal station-climatology Brier scores;
- at least two populated fixed score bands, each with at least 30 independent dates and absolute reliability error at
  most `0.05`;
- the one-sided 95% date-clustered lower mean of `outcome_no - conservative_score` is nonnegative;
- the one-sided 95% date-clustered lower mean fixed-price exact-fee return is strictly positive;
- every leave-one-station-out mean fixed-price return is strictly positive; and
- maximum sequential drawdown of the one-per-date fixed-price screen is at most `$10`.

Passing permits only a checksum-bound successor freeze. It does not permit evaluation-date access in this workflow,
recommendations, a cohort, capital, orders, deployment, live-ready, scale-ready, or a `$100` projection. Failure is
terminal for this identity: do not inspect the reserved dates or retune against development.
