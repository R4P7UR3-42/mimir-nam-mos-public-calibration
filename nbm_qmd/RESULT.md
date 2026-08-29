# Terminal Result: Multi-Level Reliability Rejection

- Decision: **REJECTED — no model, economic, cohort, capital, or trading authority**
- Public run: [`33229648911`](https://github.com/R4P7UR3-42/mimir-nam-mos-public-calibration/actions/runs/33229648911)
- Run head: `98d0e52516179d30631016f927aa936872305942`
- Frozen evaluator tag: `noaa-nbm-qmd-public-evaluator-v1`
- Private source SHA: `11151cddfb49ffc7319ecf15cbbc8d1f881df274`
- Predeclaration SHA-256: `22a5b0245bf78d960f1443e4fb786cdbbc77bced5746871e5383f1e225380536`
- Evaluation SHA-256: `8b1baa59900d28542ba176bf81548178ed9bee72129e536b72a42ab5bdc393d5`
- Artifact `SHA256SUMS` SHA-256: `40606c7a59bb94c75265ec6bb0b7fe1032d84bc905cf0862c568b500675aaa99`
- Terminal log SHA-256: `7379361ca030a5d2e9c3acb29870045867bed7ceea54dec85ab715e792dcdc11`

The exact frozen evaluator ran once without provider-network permission. All source, packaging, workflow-isolation,
input, and portable artifact checksums passed. Coverage was exactly 10,000 predictions over 100 contiguous independent
market dates, 20 stations, and five published percentile levels.

## Frozen result

| Measure | Result |
| --- | ---: |
| Brier / evaluation-climatology Brier | `0.160850 / 0.245308` |
| Brier skill | `+0.344293` |
| Q10 observed / margin | `0.141500 / +0.041500` |
| Q25 observed / margin | `0.331000 / +0.081000` |
| Q50 observed / margin | `0.596000 / +0.096000` |
| Q75 observed / margin | `0.832500 / +0.082500` |
| Q90 observed / margin | `0.941500 / +0.041500` |
| Q90 clustered 90% / 95% lower margin | `+0.035000 / +0.033000` |
| Maximum station / date share | `0.0500 / 0.0100` |
| Passing Q90 station holdouts | `20 / 20` |
| Weakest Q90 holdout clustered-95 margin | `+0.030000` excluding `KMSP` |

Coverage, Brier skill, Q90 clustered calibration, concentration, and every Q90 station holdout passed. The exact
all-level reliability gate failed because Q25, Q50, and Q75 were underconfident by `0.081000`, `0.096000`, and
`0.082500`, above the frozen maximum absolute error of `0.05`. The overall diagnostic therefore reports
`passes=false`.

The positive Q90 result does not override the predeclared conjunction. There will be no rerun, probability remapping,
subgroup selection, gate removal, or promotion of this family. These dates are now inspected development evidence.
Any Q90-only successor must use a new durable identity, predeclare its price/fill/economic rules before price access,
keep the result separate, and begin independent prospective credit on later dates. This result supplies no quote,
depth, fee, fill, P&L, recommendation, capital, readiness, cohort, or order evidence.
