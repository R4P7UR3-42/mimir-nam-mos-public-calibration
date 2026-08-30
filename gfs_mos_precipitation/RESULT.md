# GFS MOS daily-precipitation v4 result

Exact-main run [`33288536561`](https://github.com/R4P7UR3-42/mimir-nam-mos-public-calibration/actions/runs/33288536561)
bound head `3d724bbc54592142602b3fc8027374db16e0dac1`, the frozen development document checksum
`c5f44f308db1e3d579bb4a99dd528636e0f6d2aee19a6bb10c64baf4f1863edc`, and artifact
`gfs-mos-precipitation-development-33288536561` (artifact zip SHA-256
`c954230d6b52bb04cbe359f530c6d37a83fb8dbba6f7803a2ab628fc8e909872`). It completed the exact 24-request budget,
preserved every raw response, and stopped at the predeclared source gate before model development.

KMSY had only 321 available labels over the 327 development dates (`0.9816513761…`), below the exact `0.99` floor.
The six rows with both `PRCP` and `PRCP_ATTRIBUTES` absent were 2025-02-16, 2025-02-20, 2025-02-25, 2025-03-03,
2025-08-31, and 2025-10-07. The archived NOAA development response checksum is
`692504af59fb33ef11f732b3c7b2e43e39b0442b15b037ae01e2b48348f47ddb`. A bounded read-only check of NOAA's raw
`USW00012916.dly` record independently returned the missing sentinel `-9999` for every one of those dates, so the
Daily Summaries result is not an API field-omission defect.

V4 is terminal. It receives no statistical, economic, calibration, execution, recommendation, cohort, capital, or
trading credit. The reserved 2025-11-24 through 2026-07-31 evaluation window remains untouched and must not be opened
for this identity. Any successor must predeclare a distinct, authoritative label source or strategy question; it may
not lower the 99% gate, impute these outcomes, or retune against this inspected development result.
