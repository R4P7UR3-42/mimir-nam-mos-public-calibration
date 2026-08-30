# GFS MOS station rolling Wilson-90 result

- Decision: **passes the frozen forecast-calibration screen**
- Run: [33283454597](https://github.com/R4P7UR3-42/mimir-nam-mos-public-calibration/actions/runs/33283454597)
- Exact main: `c0680ff7eb0425686d442c3ad204b4b4324662e6`
- Predeclaration SHA-256: `a8e918940041513a14219b88ac3e92a17577a0b14d22538f37d302f0eb6586d0`
- Capture SHA-256: `224cd2725dbf52cef3b468da300993267103f4f75e18530db7fbaa672ff13754`
- Evaluation SHA-256: `344370d883129f58797eb27ff43c6e2d266ce29acf12db0d348da3f0394d0721`
- Artifact `SHA256SUMS` SHA-256: `9a329cd6ccc024f635e1ee748d4e44ea352ac52e3ae43d4da3bd9fc35ebd2dd3`

## Source result

The first and only frozen run completed all 23 requests without retry: 20 IEM GFS MOS station captures, one NOAA ISD
identity capture, and two NOAA NCEI `TMAX` captures. It bound 7,900 complete station/date rows across the 145-date
calibration prefix and 250-date evaluation. All 20 station sources contained the five required semantic fields. The
optional `snw` field was absent at KLAX, KMIA, and KSFO, confirming the predeclared reason to record optional schema by
station while requiring semantic identity globally. No duplicate selected row was present.

No production database, credential, recommendation, order, or historical market price was accessed.

## Independent evaluation

The frozen model emitted 13,071 selections on all 250 evaluation dates and all 20 stations:

| Metric | Result |
|---|---:|
| Mean score | `0.951853` |
| Observed success | `0.965726` |
| Model Brier | `0.033089` |
| Frozen-reference Brier | `0.036218` |
| Brier skill | `+0.086392` |
| Whole-date 90% lower observed-minus-score | `+0.008795` |
| Whole-date 95% lower observed-minus-score | `+0.007188` |
| Maximum station share | `0.076505` |
| Maximum date share | `0.004896` |

Every frozen reliability band passed:

| Score band | Rows | Dates | Mean score | Observed | Absolute error |
|---|---:|---:|---:|---:|---:|
| `[0.90,0.93)` | 3,392 | 250 | `0.919446` | `0.946639` | `0.027193` |
| `[0.93,0.96)` | 3,294 | 250 | `0.943872` | `0.955677` | `0.011805` |
| `[0.96,1.0001]` | 6,385 | 250 | `0.973186` | `0.981049` | `0.007864` |

All 20 leave-one-station-out whole-date 95% lower margins remained positive. The weakest was KSEA at `+0.005283`.
Every station contributed at least 126 independent dates, above the frozen 30-date floor. Consequently all nine frozen
gates passed.

## Decision boundary

This is independent forecast-calibration evidence, not an executable-profit result. It does not establish current
contract support, displayed depth, fill probability, fee-adjusted EV, capital sizing, a production adapter, a cohort,
or trading authority. The only permitted next step is a separately frozen current-market support and exact-fee
execution evaluation using this unchanged model identity. Historical market prices remain uninspected for this family.
