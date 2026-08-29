# 18Z Barbell Market-Implied NO Result

- Decision: **rejected before OOS evaluation**
- Public run: [33241922426](https://github.com/R4P7UR3-42/mimir-nam-mos-public-calibration/actions/runs/33241922426)
- Exact head: `5b588fc267fdd99c40fe5e859cd255d14743570a`
- Predeclaration SHA-256: `b6274946a3687fb0b62a8bb5b60202a25c2197d7515dc8a4780b9c56dc3d1bc8`
- Artifact `SHA256SUMS`: `5ab028bbea705c26ebc4b789fe6c05a2d2a10b59044c4305529d951a87cb2354`
- Report SHA-256: `271a2aa3819c8a416d846bf340454eae780263e059573ef79107642e1b6662ee`
- Training SHA-256: `444a42dc2ea19ef82c463619dc7da8d831171ae5e915dd2388879a1176a2d1f8`
- Run-manifest SHA-256: `a361679cdcb02ab5823ea273f9030e1e9e6c6928ad16575c087c241f2c69f5f2`

The free public runner passed its frozen identity checks and focused tests, made 761 paced public requests, and
checksum-validated the complete artifact. It accessed no evaluation series, production database, credential, capital,
recommendation, cohort, or order capability.

Neither frozen price band passed its predeclared training gate. The `[0.8500,0.9000)` band had 19 rows over 15 dates,
18 wins, a `0.9474` observed score, a `0.83942738` one-sided 90% Wilson lower probability, and `-$0.06687262`
conservative exact-fee edge at its frozen maximum price. It also missed the minimum 25 rows and 20 dates.

The `[0.9500,0.9700]` band had 183 rows over 37 dates and 182 wins. Its observed score was `0.9945`, but its
one-sided 90% Wilson lower probability was `0.98190927`; after the frozen `$0.9700` maximum price and `$0.0021` exact
fee, conservative edge was only `+$0.00980927`, below the frozen `+$0.0150` minimum.

The runner therefore stopped at `training_rejection` exactly as declared. This creates no calibration, executable-fill,
P&L, capital, readiness, deployment, or trading authority. This exact 18Z barbell family is terminal: its gates may not
be relaxed, its bands may not be retuned, and its untouched evaluation set may not be reused to rescue the hypothesis.
