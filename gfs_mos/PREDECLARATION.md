# GFS MOS station rolling Wilson-90 predeclaration

- Frozen: 2026-08-30 UTC, before any GFS MOS evaluation outcome or market-price acquisition
- Identity: `gfs_mos_station_rolling_wilson90_v1`
- Purpose: independent forecast-calibration screening only
- Production, database, credential, capital, recommendation, cohort, and order access: prohibited

## Materially distinct source contract

Use Iowa State University's public IEM archive of NOAA GFS Model Output Statistics. This is a different numerical
model and MOS system from the terminal NAM source family. For every exact station and market date, request only model
`GFS` and the prior calendar date's exact 12:00:00Z runtime; select the non-null `n_x` row whose forecast time is
00:00:00Z on the calendar day after the market date; and use 20:00:00Z on the initialization date as the conservative
causal availability clock.

Require the semantic columns `runtime`, `ftime`, `model`, `n_x`, and `station` at every station. Record the complete
station-specific CSV schema, but do not require unrelated optional columns to be globally identical: the terminal NAM
run proved that optional `snw` presence varies by station without changing the selected maximum-temperature identity.
Collapse repeated selected rows only when all five semantic columns agree exactly; a conflict, missing required field,
null guidance, wrong station/model/runtime/forecast time, malformed maximum, missing station/date, or HTTP 429 fails
closed. Persist every source URL, header map, raw body, hash, optional schema, and duplicate count. Make exactly 20 MOS,
one ISD-history, and two NCEI outcome requests with no retry.

Use exact NOAA NCEI Daily Summaries `TMAX` under the checksum-bound 20-station ICAO/WBAN-to-GHCN mapping. Require one
finite outcome per station/date and exact metadata. No imputation, substitution, partial date, or dropped station/date
is permitted.

## Frozen split and model

Use exactly 145 consecutive calibration/history dates from 2021-02-15 through 2021-07-09 and an untouched 250-date
evaluation from 2021-07-10 through 2022-03-16. These GFS values and evaluation outcomes have not been inspected for
this hypothesis. Do not read market prices until the complete source capture passes.

For every evaluation station/date, use exactly the most recent 120 complete same-station residuals no newer than target
minus two calendar days. For each half-degree above boundary at distance `[4.0°F,8.0°F)`, score above-temperature NO as
the one-sided 90% Wilson lower bound of residuals at or below the boundary, with `z=1.2815515655446004`, rounded once to
four decimals. Exact score `0.9000` passes and `0.8999` fails. The frozen Brier baseline is the calibration-prefix
empirical success rate in exact one-degree distance bins.

## One-shot decision

Require complete 7,900-row source identity and selections on all 250 evaluation dates; strictly positive Brier skill;
at least 30 dates and absolute reliability error at most `0.05` in each score band `[0.90,0.93)`, `[0.93,0.96)`, and
`[0.96,1.0001]`; nonnegative whole-date-clustered 90% and 95% observed-minus-score lower means; nonnegative clustered
95% margin after excluding each station; at least 30 dates per station; maximum station share `0.10`; and maximum date
share `0.02`.

Any failed source, coverage, calibration, robustness, or concentration gate rejects this exact GFS family without
rerun, score remapping, station/season/distance selection, or evaluation reuse. A pass permits only a separate current
market support and exact-fee execution decision. It creates no policy, cohort, capital, recommendation, readiness,
deployment, or order authority.
