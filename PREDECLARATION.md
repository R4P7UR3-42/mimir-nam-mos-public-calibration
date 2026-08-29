# NAM MOS Station Rolling Wilson-90 Predeclaration

- Frozen: 2026-08-29 UTC, before any outcome or market-price acquisition
- Identity: `nam_mos_v4_station_rolling_wilson90_v1`
- Purpose: independent forecast-calibration screening only
- Production, database, credential, capital, recommendation, and order access: prohibited

## Causal source identity

Use Iowa State University's public Iowa Environmental Mesonet archive of NOAA's station-based North American
Mesoscale Model Output Statistics. NOAA documents NAM MOS as station-specific guidance generated from 00Z and 12Z NAM
output with maximum/minimum temperature guidance through 72 hours. The selected period is after the January 2018 NAM
MOS change and within the operational NAM v4 era.

For each exact station and market date:

1. request only model `NAM` and the prior calendar date's exact `12:00:00Z` runtime;
2. select a non-null `n_x` row whose forecast time is `00:00:00Z` on the calendar day after the market date;
3. require response station, model, runtime, forecast time, schema, and value identity to agree exactly; and
4. use `20:00:00Z` on the initialization date as the conservative causal availability/decision clock.

The source canary found one identical duplicate selected row per station. Collapse duplicates only when every decoded
semantic field and value agrees exactly after removing the archive's row index. A conflicting duplicate, any other
duplicate count, missing or null guidance, wrong model/runtime/forecast time, malformed value, or schema drift fails
the complete capture. Persist the exact URL, response headers, raw body hash, and duplicate identity. Use exactly 20
forecast requests, one per station; stop on HTTP 429 and do not retry it.

Use NOAA NCEI Daily Summaries `TMAX` outcomes under the checksum-bound ICAO/WBAN-to-GHCN mapping for the exact 20
stations in `stations.json`. Require one finite TMAX per station/date and exact station metadata. No imputation,
station substitution, timezone substitution, partial date, or dropped station/date is permitted.

## Frozen dates

- Calibration/history prefix: exactly 145 consecutive market dates from `2021-02-15` through `2021-07-09`.
- Untouched evaluation: exactly 250 consecutive market dates from `2021-07-10` through `2022-03-16`.

The evaluation ends before the earliest HRRRv4 training outcome and is disjoint from all prior Mimir final-evaluation
windows. No evaluation outcome or price may be read until source capture and calibration-prefix coverage are complete
and checksum-valid.

## Frozen model

For each evaluation station/date, form `residual = observed TMAX - NAM MOS n_x`. Use exactly the most recent 120
complete residuals for that station whose market date is no newer than evaluation target minus two calendar dates.
Fewer or more than 120, a date gap, or a station mismatch fails the row. Evaluation outcomes never enter their own or
the immediately following date's score.

Generate each half-degree boundary whose exact distance above `n_x` is in `[4.0°F, 8.0°F)`. For an above-temperature
NO event, success is `observed TMAX <= boundary`. Let `k` be the count of the 120 causal residuals less than or equal
to `boundary - n_x`. The score is the one-sided 90% Wilson lower bound for `k / 120`, using
`z = 1.2815515655446004`, rounded once to four decimal places. Select every row with score at least `0.9000`; exact
`0.9000` passes and `0.8999` fails. No station, season, bias, distance, sample, confidence, or score rule may change
after this predeclaration commit.

The frozen Brier baseline is the pooled calibration-prefix empirical success rate in exact one-degree distance bins
`[4,5)`, `[5,6)`, `[6,7)`, and `[7,8)`, computed without evaluation outcomes.

## One-shot independent decision

Resample whole market dates with the reviewed deterministic full-state clustered sampler. The model passes only if all
of these conditions hold:

1. all 7,900 forecast and outcome identities are complete and all 250 evaluation dates contain a selection;
2. Brier skill against the frozen distance-bin baseline is strictly positive;
3. score bands `[0.90,0.93)`, `[0.93,0.96)`, and `[0.96,1.0001]` each contain at least 30 independent dates and have
   absolute observed-minus-score error no greater than `0.05`;
4. one-sided whole-date-clustered 90% and 95% lower means of `observed - score` are both nonnegative;
5. every one of the 20 leave-one-station-out whole-date-clustered 95% lower means is nonnegative;
6. every station contributes selections on at least 30 independent dates, maximum station share is at most `0.10`,
   and maximum date share is at most `0.02`; and
7. source, operational-era, outcome, station, clock, executable, schema, duplicate, coverage, and checksum identities
   all agree exactly.

Any failure stops this family. Do not inspect historical prices, remap the probability, change a threshold, select a
station/season/distance, rescore the consumed dates, or claim profitability. A pass permits only a separate reviewed
current-market support and implementation decision; it does not create a policy, cohort, capital authority,
recommendation, approval, readiness credit, or order.
