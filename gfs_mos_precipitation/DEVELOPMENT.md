# GFS MOS daily-precipitation development freeze

- Identity: `gfs_mos_local_day_precipitation_jeffreys_wilson95_development_v4`
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
checksum-bound IANA time zone. This normally selects four or five intervals. Collapse only exact semantic duplicates.
An entirely absent exact 12Z runtime may exclude that market date only when the missing-date set is identical at all 20
stations and at least 99% of the frozen 693 history/development dates remain complete. Exclude such a date globally from
forecast rows and later model history/targets. A station-specific missing runtime, partial runtime, null selected `p06`,
conflicting duplicate, wrong station/model/runtime, non-six-hour clock, out-of-range value, or incomplete local-day
coverage within an existing runtime fails closed. Never substitute 00Z, 06Z, 18Z, or another date.

Use ISD history only to bind the exact ICAO/WBAN-to-GHCN identity and coordinates. Do not use the aviation-history `END`
field as an availability claim for another NOAA dataset. Independently require the freshly captured authoritative GHCN
Daily element inventory to contain exactly one mapped `PRCP` row for every station, matching coordinates within 0.2
degrees, beginning no later than the history year, and ending no earlier than the development year.

Use exact NOAA NCEI Daily Summaries `PRCP` under that doubly checked identity. A nonzero value is rain. A zero value whose
measurement flag is `T` is also rain; it must never be relabeled no-rain. A row with both `PRCP` and `PRCP_ATTRIBUTES`
absent is an unavailable label: persist its exact station/date, never impute or relabel it, and exclude it from model
history, scoring, calibration, and economic results. Require available labels on at least 99% of dates independently for
every station in both the history and development phases. Exact 99% passes and an immediately smaller ratio fails.
Reject a row containing only one of those fields, malformed attributes, nonblank quality flags, unsafe measurement
flags, impossible values, duplicate identity, missing station/date identity, or sub-99% station/phase coverage. NCEI is
a model label proxy, not the Weather Company settlement source; even a positive result cannot establish exchange outcome
agreement without later prospective official Kalshi settlements.

The acquisition is credential-free, has exactly 24 requests (20 IEM, one ISD identity, one GHCN element inventory, and
two NCEI outcome requests), has no retry, stops on HTTP 429, and refuses a production Mimir host. Persist raw response
bytes, headers, URLs, hashes, the complete station/date rows, and a portable checksum manifest.

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
dates before the target. Require at least 358 globally complete station dates and at least 30 same-band labels. The
probability estimate is the Jeffreys posterior mean
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

## Source-contract correction

The first v1 exact-main run `33287841384` stopped before NOAA outcomes after KATL proved that the 2025-05-29 12Z GFS MOS
runtime is entirely absent while all other 692 requested KATL runtimes are present. V2 made only the global-outage rule
above explicit. Exact-main v2 run `33287970484` then captured all 20 MOS sources and stopped before outcomes because the
KATL ISD aviation-history segment ended on 2025-08-27. NOAA's distinct GHCN element inventory, checksum
`a5fb1dfd2e9667d53925e53161acfe0e363079a9cc0b72c83984aacb4375e76a`, reports exact `PRCP` coverage through 2026 for
all 20 mapped GHCN stations. V3 replaces only that cross-dataset availability inference with the authoritative inventory
contract above. Neither correction inspects an outcome, changes a model or gate, selects the observed date by name,
substitutes a forecast, or accesses the reserved evaluation window. V1 and v2 remain terminal source-contract artifacts
and receive no statistical credit.

Exact-main v3 run `33288268894` then reached all 7,320 expected history identities with no duplicates or unsafe
attributes, but exact KDCA 2024-05-26 and KSEA 2024-04-24/25 rows had neither `PRCP` nor `PRCP_ATTRIBUTES`; it stopped
before requesting development outcomes. V4 predeclares only the non-imputed high-coverage missing-label rule above.
It does not inspect a development outcome, change the forecast model or any statistical/economic gate, or access the
reserved evaluation window. V3 remains terminal and receives no statistical credit.
