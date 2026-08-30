# Market-plus-ECMWF residual development result

- Decision: **rejected before OOS evaluation**
- Public run: [33281703530](https://github.com/R4P7UR3-42/mimir-nam-mos-public-calibration/actions/runs/33281703530)
- Exact head: `2f315d6d82caf079304153dc3778a1c13b0aceb2`
- Development freeze SHA-256: `4592eee33eb1366863bee3deb81469b42564ffca9dec2d689f70db29f4690d39`
- Artifact `SHA256SUMS`: `97aabdf729926573832954b93c74daed1f4701ee74944f346d3e932a2e3e3f82`
- Development report SHA-256: `1da4e34d395a3d12d4c77116ec444488ed4895d49f393acfef5b93948257d29a`
- Run-manifest SHA-256: `a3eff39c547db3ca5c302460c62523f24b6ac3a9b5ebfdd2c9605e6261504ca3`

The free public runner passed eight focused tests, recovered from the prior run's pre-response TLS failure through the
reviewed batched transport path, and checksum-validated its complete artifact. It made 811 paced requests and captured
370 training rows. The exact `[0.5000,0.9700]` price range yielded 272 eligible rows over all 37 dates and ten stations.
No evaluation series, production database, credential, capital, recommendation, cohort, or order capability was
accessed.

None of the three frozen candidates was development-admissible. `market_offset` had OOF Brier skill `-0.0206949587`
and log-loss improvement `-0.0015176397` versus displayed NO price. `forecast_only` had OOF Brier skill
`-0.2349551059` and log-loss improvement `-0.0574696741`.

`market_free` improved OOF Brier skill to `+0.0434588985`, improved log loss by `+0.0142154749`, and had mean
calibration error `0.0004536152`. It nevertheless failed the frozen leave-one-station-out coefficient-sign gate:
excluding `KXHIGHTBOS` changed the scaled forecast-distance coefficient to `-0.0422705128`. The all-training fit's
coefficients were intercept `-2.9740604491`, displayed-price logit `+2.2487992788`, and scaled forecast distance
`+0.3048157395`; those post-result values cannot be used to waive the robustness failure.

The development freeze therefore selected no successor and forbids opening the untouched OOS split. This creates no
calibration, executable-fill, P&L, capital, readiness, deployment, or trading authority. The exact market-plus-ECMWF
18Z residual family is terminal and may not be rescued by deleting Boston, changing the sign gate, or retuning the
model menu after this result.
