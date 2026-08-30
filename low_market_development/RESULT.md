# Daily Low-Temperature Market Development V1 — Terminal Rejection

## Decision

The frozen training-only family is rejected. No cell passed the predeclared exact-fee, whole-date clustered,
multiple-testing, coverage, concentration, and station-holdout gates. The reserved evaluation inventory remains
untouched and must not be queried for this identity.

This is evidence against the exact prior-day 18:00 UTC extreme-contract NO family. It is not a profitability claim for
another side, clock, price band, settlement variable, or model, and it creates no successor, policy, capital, cohort,
recommendation, or order authority.

## Immutable execution

- Public workflow run: [`33286871481`](https://github.com/R4P7UR3-42/mimir-nam-mos-public-calibration/actions/runs/33286871481)
- Exact main SHA: `a8c5575e92bb16694e4c6f311ea092b783209ecc`
- Run interval: 2026-08-30 01:58:13Z–02:02:52Z
- Development freeze SHA-256: `2081e79a2606d7417d26c1eb5f93a717b30a4def73b29480d560c3c9580b4df3`
- Training inventory SHA-256: `65cff9a375c81967b2d6177401b11ae9527f85ff1de2db0f42f862ef179f0a21`
- Reserved inventory SHA-256: `4a407d82e30e8a60aa2d3ff3d3cd587d464d8645156d9bcfbd8861404fe367b6`
- `development.json` SHA-256: `7f6a308dc7692530f4a429c5869f81268d685f580bc290b4bfa3baa7a1fd272d`
- Artifact `SHA256SUMS` SHA-256: `d2705ee7a7e3ef3ba34e4f365e5468d920469cc8a5613cd7aa6089bdd206ad4b`

All artifact checksums passed. The run used 911 of 5,000 bounded public requests with no retry. It captured 870 upper
and lower extreme rows across 109 market dates and four available training series; 458 rows fell in the eight exact
price cells. `evaluation_series_accessed=false`, `production_database_accessed=false`, and
`active_trading_capability_changed=false` are checksum-bound in the report. Raw artifact labels contain no reserved
series ticker.

## Cell results

The primary result is the 1.25th-percentile whole-date clustered exact-fee return after the fixed eight-cell Bonferroni
correction. Edge evaluates the same clustered outcome floor at the cell's conservative maximum price and exact fee.

| Cell | Rows / dates / series | Wins | Primary lower return | Conservative edge | Decision |
| --- | ---: | ---: | ---: | ---: | --- |
| Upper `$0.70–<0.80` | 52 / 41 / 4 | 41 | `-$0.11172909` | `-$0.15813878` | Reject |
| Upper `$0.80–<0.90` | 78 / 54 / 4 | 68 | `-$0.06998750` | `-$0.12148987` | Reject |
| Upper `$0.90–<0.95` | 61 / 46 / 4 | 56 | `-$0.11175345` | `-$0.14377619` | Reject |
| Upper `$0.95–$0.97` | 77 / 59 / 4 | 74 | `-$0.05780460` | `-$0.06300909` | Reject |
| Lower `$0.70–<0.80` | 15 / 15 / 2 | 10 | `-$0.37213333` | `-$0.41120000` | Reject |
| Lower `$0.80–<0.90` | 20 / 19 / 4 | 16 | `-$0.28896316` | `-$0.32735263` | Reject |
| Lower `$0.90–<0.95` | 38 / 30 / 4 | 32 | `-$0.24267812` | `-$0.26758571` | Reject |
| Lower `$0.95–$0.97` | 117 / 67 / 4 | 113 | `-$0.04425192` | `-$0.04617407` | Reject |

The apparent 113/117 accuracy in the final row is not value: price plus exact fee exceeds its conservative outcome
rate. It also fails eight-series coverage, 20% station concentration, and leave-one-series-out robustness. None of the
other cells reaches both the minimum sample and economic gates.

## Prior failed attempt

Run `33286776767` stopped before any training candle on a real provider schema mismatch: Boston's valid event date was
encoded in its ticker while non-causal `occurrence_datetime` reflected a later administrative timestamp. PR #23 made
only the bounded parser correction, retained the ticker date and every frozen economic/OOS gate, and added the adjacent
prior-date rejection. Its preserved artifact accessed only training series and receives no statistical credit.

## Disposition

- Do not run the reserved evaluation workflow for this identity.
- Do not widen dates, pool high-temperature outcomes, lower the fee/edge floor, choose a cell post hoc, or reinterpret
  scalar events.
- A future weather family must have a materially distinct causal hypothesis and a new untouched evidence commitment.
