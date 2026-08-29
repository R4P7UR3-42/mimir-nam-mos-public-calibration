# GEFSv12 operational compatibility evidence

## 2026-08-29 result

- Frozen model identity: `noaa_gefs_v12_five_member_station_z_wilson95_rolling120_lag2_v1`
- Public workflow run: [33239085107](https://github.com/R4P7UR3-42/mimir-nam-mos-public-calibration/actions/runs/33239085107)
- Exact merged source: `6fcc2aa4169f94bf3ed3e94f76a3499a6055f454`
- Exact NOAA operational initialization: `2026082800`
- Target market date: `2026-08-29`
- Evidence JSON SHA-256: `20aa0f5ff518c62e9f1d6d9b47a8625c1aa902a58eca16ca62794b78f8e923ae`
- Result: passed in 45 seconds.

The canary performed exactly 110 requests with concurrency ten and zero retries. It verified the exact 2 m temperature
GRIB identity for control member `c00` and perturbed members `p01` through `p04` at all eleven three-hour steps from
27 through 57 hours. All five members produced a stable, valid grid point and sampled-day high for each of the 20
frozen stations. The downloaded artifact's `SHA256SUMS` verified successfully.

This establishes source and decoder compatibility for this one immutable operational cycle. It is research-only and
does not establish calibration, executable economics, profitability, production readiness, or trading authority. The
separate frozen independent OOS evaluation remains the authority for rejecting or advancing the hypothesis.
