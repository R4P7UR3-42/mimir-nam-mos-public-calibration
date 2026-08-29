# GEFSv12 dispersion hypothesis result

## Decision

`noaa_gefs_v12_five_member_station_z_wilson95_rolling120_lag2_v1` is **rejected**.

The frozen evaluation did not reach outcome acquisition or probability evaluation. Its exact NOAA retrospective source
contract failed closed, so the predeclared rule makes this family terminal on these dates. No partial row, station,
date, member, score band, or operational-canary result may be treated as calibration or profitability evidence.

## Exact evidence

- Public workflow run: [33235986529](https://github.com/R4P7UR3-42/mimir-nam-mos-public-calibration/actions/runs/33235986529)
- Exact evaluated source SHA: `bd3f21a4f58a3f37f3f1455cdfee82d592fb276a`
- Failure: `GEFS range identity changed for 2019-09-10/c00.`
- Failed initialization/member: `2019-09-10 00Z`, control member `c00`
- Checksum-valid rows preserved before failure: 1,289 of 1,850
- Requests reserved before failure: 3,701 of the 3,900 hard ceiling
- Outcome source payloads acquired: 0
- Evaluation report produced: no
- `SHA256SUMS` verification: passed for all 1,292 artifact entries
- `SHA256SUMS` SHA-256: `ede54a016bd7e7ccb2a83b06b3b4abe7d9c75ee0f1d264d65a11ff3478c26756`
- `capture.log` SHA-256: `074eec7b6f521de8d2a3211a671083d81a9dafbcae6ab7b875296547a3c00d8f`
- `run.json` SHA-256: `30909b31aad420f93f16edb8e831ff0ff26cc6601051104494849f5227c1e378`

The workflow's capture step is shown as a successful conclusion in GitHub's summarized API because the step used
`continue-on-error`; its underlying outcome was failure. The evaluation step was therefore skipped and the terminal
guard correctly failed the job.

## Interpretation and next boundary

The separate operational compatibility canary passed for one 2026 cycle. That result establishes only that the current
free operational feed and decoder worked for that cycle; it cannot repair a failed immutable retrospective source
contract or supply historical outcomes.

There will be no retry, resume, source-identity relaxation, same-date remapping, subgroup evaluation, or partial credit
for this exact family. A successor must be materially distinct, frozen before its source values and outcomes are read,
and evaluated on untouched independent market dates.
