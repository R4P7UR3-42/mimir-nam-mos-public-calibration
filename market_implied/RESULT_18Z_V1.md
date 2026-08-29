# 18Z Top-Tail Market-Implied NO Result

- Decision: **rejected before OOS evaluation**
- Public run: [33241632682](https://github.com/R4P7UR3-42/mimir-nam-mos-public-calibration/actions/runs/33241632682)
- Exact head: `8ca34dd996fe4bc17011af0341ed07e03f417a04`
- Frozen tag: `market-implied-18z-v1-runner-20260829`
- Artifact `SHA256SUMS`: `c57c424d9dbd487ced38b1fb82a018795964f3951f61e921c8b5505f9683bc38`
- Report SHA-256: `03ea6e15ec8187de2c241ecfe278a5cc05e88ff8399242785aaae502068f7f5c`
- Training SHA-256: `f765e471d9cb4c5ce55e5229a0cb3ba21239b42bb9132a755da0b0324e2a20f8`

The free public runner passed all tests and every exact source identity. It collected 185 rows over 37 dates and five
development stations in 381 requests. All 765 artifact files pass the uploaded portable checksum manifest. No
evaluation-series request occurred, and no production database, credential, capital, recommendation, cohort, or order
capability was accessed.

None of the three frozen broad price bins had conservative exact-fee edge. The 0.70–0.80 and 0.80–0.90 bins were both
small and adverse. The 0.90–0.97 bin had 109 rows over all 37 dates, 105 wins, observed success `0.9633`, and clustered
90% lower probability `0.94117647`; against its frozen maximum price `0.9700` and fee `0.0021`, conservative edge was
`-$0.03092353`. It therefore rejected before OOS exactly as predeclared.

This creates no calibration, executable-fill, P&L, capital, readiness, or trading authority. The exact broad-bin 18Z
family is terminal and cannot be retried or widened. Its evaluation series and outcomes remained untouched.
