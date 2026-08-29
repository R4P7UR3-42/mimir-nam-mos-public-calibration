# NOAA NBM V5 QMD One-Shot Evaluation Predeclaration

- Frozen: 2026-08-29 UTC, before evaluator execution or row-value inspection
- Research identity: `noaa_nbm_v5_qmd_station_max_t_percentiles_v1`
- Private source commit: `11151cddfb49ffc7319ecf15cbbc8d1f881df274`
- Production, credential, capital, recommendation, cohort, readiness, and order access: prohibited

## Already-Frozen Evaluation Contract

Preserve the accepted private ADR and evaluator without model, probability, station, date, outcome, bootstrap, or gate
changes. Evaluate exactly 100 contiguous market dates from `2026-05-07` through `2026-08-14`, all 20 exact stations,
and the published `0.10`, `0.25`, `0.50`, `0.75`, and `0.90` NBM percentile probabilities. The four acquisition
artifacts were captured under the frozen NBM v5 source, availability, station, and NOAA outcome contract before this
public packaging step. Their exact compact capture identities are:

| Private run | Dates | Capture SHA-256 |
| --- | --- | --- |
| `33155927949` | `2026-05-07`–`2026-06-06` | `658b4c8d9a0c4361bb2e91efb1d44eda2d82f37112fcc4f176078811e3501430` |
| `33156510785` | `2026-06-07`–`2026-07-07` | `a759de0e02a095ee38d26b452aa4a922ec09162d1e90552d1b9fafd7147d7f45` |
| `33156512445` | `2026-07-08`–`2026-08-07` | `dceddb96a28c1899f1f6051bc074749b675bb1cf9c4900488994acb2a4d617cd` |
| `33156598208` | `2026-08-08`–`2026-08-14` | `1d5110c2b94be884c70e254866415176109e3b6a26c95592b42cb8df45f22992` |

Each original artifact's `SHA256SUMS` was independently reverified before recording these hashes. The first two
GitHub artifacts were deleted only after checksum-valid local archival; this changes retention, not evidence identity.
The final two remain downloadable from GitHub. Do not reacquire, replace, repair, or reinterpret a capture.

## Frozen Evaluator Identity And Public Packaging

The authoritative private evaluator source has SHA-256
`b9dadfccaf72b0511234af11329d7ccad56da96e0e3cc79c4cc5e8b841a7eb90`. Package it with only a mechanical import
replacement: the four constants imported from the acquisition module are copied into a local constants module with
these exact values:

- capture schema `noaa_nbm_v5_qmd_max_t_capture_v1`;
- model `noaa_nbm_v5_qmd_station_max_t_percentiles_v1`;
- availability upper bound `14:15:00`; and
- ordered percentiles `TXNP1/0.10`, `TXNP2/0.25`, `TXNP5/0.50`, `TXNP7/0.75`, `TXNP9/0.90`.

Retain the exact private core-source identities:

- `server/core/decimal.ts`: `795765828bac85d59ef5e4974eba5471c585e2d3469fa7a6e2bc98251ae13230`;
- `server/core/json.ts`: `f6b0554976e1a6810e4651b8f0c55a8c9484231b8dab12d6ff70371e28683074`;
- `server/core/statistics.ts`: `55298b3f3ca728e8be9858ba243792b0a02441ade1ed43730a948acd86bff860`;
- evaluator tests: `febe03be88af1d4704d8034826619dded4eaf337df140f91eeec0331bd15cc5a` before import-path packaging.

The public workflow must run manually on exact `main`, use a standard GitHub-hosted runner, have read-only contents
permission, receive no secret, have no network-enabled evaluation step, verify every source and capture hash, run the
frozen tests, execute the evaluator exactly once with 10,000 bootstrap samples, upload a portable checksum artifact,
and prohibit any production or provider-write path. A public bundle or mechanically relocated source may change its
file hash only because paths/constants are packaged; the model and decision behavior may not change.

## Terminal Decision

Require every predeclared gate from the accepted private evaluator:

1. exactly 100 independent dates, 20 stations, and all five published probability levels;
2. strictly positive Brier skill versus evaluation climatology;
3. absolute reliability error at most `0.05` at every published level;
4. nonnegative one-sided whole-date-clustered 90% and 95% Q90 calibration margins;
5. maximum station share at most `0.35` and date share at most `0.05`; and
6. every exact leave-one-station-out Q90 aggregate and clustered-95 margin nonnegative.

Any failed identity, schema, coverage, checksum, test, or statistical gate rejects this family without rerun, retuning,
subgroup selection, probability remapping, or reuse of these dates. A pass permits only a separate consumed-date
historical quote/depth/exact-fee support audit. It is not executable-fill, P&L, capital, cohort, recommendation,
readiness, or trading authority.
