# Predeclaration: GEFSv12 Station Dispersion Calibration

- Identity: `noaa_gefs_v12_five_member_station_z_wilson95_rolling120_lag2_v1`
- Status: frozen before any GEFS temperature value or matching outcome is read
- Scope: public, credential-free, order-free forecast calibration research

## Hypothesis

The spread of a fixed five-member NOAA GEFSv12 ensemble contains useful station/day uncertainty information that the
failed deterministic forecast and pooled-residual families omitted.  A station-specific empirical distribution of
standardized ensemble errors may therefore produce conservative, discriminating probabilities for tomorrow
above-threshold NO outcomes.

This is a new model family.  It does not reuse, repair, subgroup, retime, or reprice the consumed ECMWF, HRRR, NBM,
NAM MOS, or market-implied hypotheses.

## Immutable source identity

- NOAA GEFSv12 reforecast bucket: `https://noaa-gefs-retrospective.s3.amazonaws.com`.
- Exact daily initialization: `00Z`.
- Exact members, in order: `c00`, `p01`, `p02`, `p03`, `p04`.
- Exact product: `Days:1-10/tmp_2m_<YYYYMMDD>00_<member>.grib2` plus its adjacent `.idx`.
- Exact parameter: instantaneous `TMP`, `2 m above ground`, regular latitude/longitude grid, three-hour forecast steps.
- The frozen source canary is `2019-08-29/c00`.  Its index SHA-256 is
  `853fa5fcf71ecc705df245f0203458cc0760a9b0c63d701c6e5549feef22f619`, full-object ETag is
  `fff7e6bf2e3669e063b7840ad8763550`, and full-object length is `34,727,288` bytes.
- Only the contiguous byte range beginning at exact step 27 and ending immediately before exact step 60 may be
  downloaded.  The decoder must find steps `27,30,33,36,39,42,45,48,51,54,57` exactly once and reject any identity,
  grid, member, step, coordinate, or finite-value drift.
- The existing 20-station `../stations.json` is frozen by SHA-256
  `297e7cdf081c38212c3a1298d09921dfcb79fff9f3fa3bae6ccafc3b8ed09d12`.
- NOAA ISD history must map each ICAO to one exact WBAN-backed GHCN station, within 0.2 degrees of the frozen
  coordinate, and cover the evidence interval.  NOAA Daily Summaries must return one finalized `TMAX` per exact
  station/date in standard units.  Missing, duplicate, malformed, conflicting, or changed identity is terminal.
- HTTP 429 is terminal and is never retried.  Other source failures receive no immediate retry.  The complete capture
  may perform at most 3,900 requests and must be create-once, resumable only from checksum-valid exact-identity rows.

The reforecast is a retrospective simulation initialized from information at its named cycle, not proof that an
operational forecast was delivered historically.  A passing result still requires a separate current operational
GEFS compatibility canary before any prospective strategy decision.

## Frozen calendar and feature

- Required forecast/outcome targets: `2018-12-27` through `2019-12-31`, inclusive.
- Untouched evaluation dates: exactly the 250 contiguous market dates from `2019-04-26` through `2019-12-31`.
- For target date `D`, use only the `00Z` initialization on `D-1`.
- Settlement-style days use local **standard** time, never daylight time: UTC-5 Eastern, UTC-6 Central, UTC-7
  Mountain/Phoenix, and UTC-8 Pacific.
- For each station/member, the feature is the maximum of the exact three-hour samples whose valid times fall inside
  `[D 00:00 local-standard, D+1 00:00 local-standard)`.
- Convert Kelvin to Fahrenheit without intermediate rounding.  The ensemble center is the arithmetic mean of the five
  member highs.  Dispersion is their sample standard deviation with an exact floor of `0.5°F`.
- A historical standardized error is `(final TMAX - ensemble center) / dispersion`.

## Frozen probability model

For each evaluation station/date, use only outcomes from target minus 120 calendar days through target minus two
calendar days, inclusive.  The two-day lag prevents an incomplete immediately preceding settlement day from entering
the model.  No other station contributes to that station's empirical distribution.

Generate four integer above thresholds: `ceil(current ensemble center + d)` for exact `d` in `4,5,6,7`.  This yields
threshold distances in `[4°F,8°F)`.  An above-threshold NO wins exactly when finalized TMAX is less than or equal to the
integer threshold.  For each threshold, count prior standardized errors less than or equal to
`(threshold - current center) / current dispersion`; the score is the one-sided 95% Wilson lower bound on that
binomial proportion.  Emit only scores at least `0.90`.

There is no haircut, cap, smoothing parameter, station pooling, selected distance, price, time, or subgroup search.
Exact score bands are `[0.90,0.93)`, `[0.93,0.96)`, and `[0.96,1.00]`.

## Frozen evaluation and decision

Nested thresholds from one station/date are dependent.  All confidence bounds resample whole market dates with the
repository's deterministic full-state clustered bootstrap.  The report must expose every raw prediction and source
hash plus:

- emitted predictions, successes, stations, and 250 independent dates;
- observed rate, mean score, observed-minus-score, Brier score, and evaluation-climatology Brier skill;
- one-sided 90% and 95% whole-date lower calibration margins;
- band reliability and date counts;
- maximum station/date concentration; and
- every leave-one-station-out aggregate and clustered-95% calibration margin.

The hypothesis passes only if all of the following are true:

1. all 250 dates and at least ten stations are represented by at least 500 emitted predictions;
2. at least two score bands are populated and every populated band spans at least 30 independent dates;
3. aggregate Brier skill versus evaluation climatology is strictly positive;
4. aggregate one-sided 90% and 95% clustered observed-minus-score lower bounds are nonnegative;
5. every populated band's absolute reliability error is at most `0.05` and clustered-90% lower margin is nonnegative;
6. maximum station share is at most `0.20` and maximum date share is at most `0.02`; and
7. every leave-one-station-out aggregate and clustered-95% calibration margin is nonnegative.

Any failed source condition or gate rejects this exact family permanently on these dates.  There is no same-date
retry, model remapping, threshold change, selected subgroup, or partial credit.

## Authority boundary

The run must not access private Mimir state, credentials, account data, nonpublic Kalshi data, recommendations, or
orders.  A pass would establish only independent forecast-calibration evidence.  It supplies no executable quote,
fee, fill, P&L, `$100` projection, cohort, capital-risk, production, or trading authority.  Those require a separate
predeclared current-model compatibility and prospective executable-economics decision.
