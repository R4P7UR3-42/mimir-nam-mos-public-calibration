# Rolling ECMWF station-calibration OOS result

## Decision

`tomorrow_station_residual_wilson95_rolling120_lag2_piecewise004_020_cap096_v1_ecmwf_open_data_native_3h_v1`
is **rejected**.

The single frozen primary successor failed its mandatory positive-Brier-skill gate on the untouched 250-date final
window. Positive calibration margins and a high observed hit rate do not override that failure.

## Exact evidence

- Original credential-free capture run: [33138279314](https://github.com/R4P7UR3-42/Mimir/actions/runs/33138279314)
- Capture-a SHA-256: `d2cf3911c226c86016ccc0a9028c8e552f2d435ff1df33f9b110f36734e211f6`
- Capture-b SHA-256: `5e2d3250a17ea7fe392788adf8af173029ba016a48d4dcdfd8153559d0fc16f7`
- Final capture-c SHA-256: `da1403ce129a39167ca88a4846ec627ea30151b28c4dcbfd7922592c4deb7dd8`
- Corrected reviewed evaluator source: Mimir `16db7a58df916980d37d9e77c73b80f7016bf331`
- Evaluator SHA-256: `15c661cd434add757c04d6f8dfb91d9e34f77b25605d2e2c88eb1f72fbdf362d`
- Evaluator-test SHA-256: `fabddbf0c31f79a4012df2200ef094fa6bbf29a9ff035d6c4883ea85a3cc09a1`
- Evaluation JSON SHA-256: `40ad737a036e4654b3635b0ca7fcaedeaaa675d1a7d8f26be351ec65fe2fc8a2`
- Production database, credentials, paid provider, and order capability used: no

Run `33138279314` completed the exact v4 capture but its older evaluator rejected that reviewed schema before computing
predictions. Mimir PR #554 corrected only the schema-family allowlist. The final evaluation used that reviewed
correction against the three immutable captures, made no network request, and retained every frozen model choice and
gate.

## Frozen final metrics

| Measure | Result |
| --- | ---: |
| Predictions / dates / stations | `4,627 / 250 / 18` |
| Successes / failures | `4,396 / 231` |
| Observed success rate / mean score | `0.950076 / 0.926310` |
| Observed minus score | `+0.023765` |
| One-sided 90% / 95% whole-date lower margin | `+0.018465 / +0.016843` |
| Brier score / climatology Brier | `0.047912 / 0.047432` |
| Brier skill versus evaluation climatology | **`-0.010121`** |
| Maximum station / date share | `0.1351 / 0.0063` |
| Weakest leave-one-station-out clustered 95% margin | `+0.012968` |

Both reliability bands, both clustered calibration margins, concentration limits, all 18 leave-one-station-out checks,
and the 100-/250-date sample gates passed. The `positive_brier_skill` gate alone failed, making
`archive_calibration_diagnostic_pass=false`.

## Boundary

There will be no gate waiver, haircut adjustment, station/date subgroup, score-band cherry-pick, or re-evaluation of
this exact family on these dates. The result supplies no executable quote, fee, fill, P&L, capital, production, or
trading authority. A successor must be materially distinct and frozen before inspecting its evaluation values or
outcomes.
