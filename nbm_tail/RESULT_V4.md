# Completed Offered-Tail V4 Development Result

- Identity: `noaa_nbm_v5_station_robust_offered_tail_no_split_development_v4`
- Frozen commit: `edecf91492659e1594fd46b033ea1301db038739`
- Annotated tag: `noaa-nbm-tail-development-v4`
- Sole run: `33234273924`, attempt 1, success
- Evaluation SHA-256: `5ded664ad6df95d17a16e2d0d5d52ed68748bc5dcf3b9f3171f795af21a17b87`
- Portable artifact `SHA256SUMS` SHA-256: `7e95f9a1e2d3841a4a5f1d1f0bb80a5ddb11f28d2351faf1a5ad94bba2020fd5`
- Workflow log SHA-256: `c23e7caba2a83bc24b548937434ec9eed97093c8e4122fb421b627abf7b9c3d3`

V4 correctly parsed both candle schemas and completed 1,327 bounded public requests. The held-out support funnel contained
1,960 offered tails, 1,172 training-qualified tails, 449 nonempty candles, 444 displayed prices, 63 eligible quotes,
and 35 deterministic independent-date selections across 15 stations. Ten selections had exact public NO-taker fills.

The model failed economically and statistically. Exact-fee realized P&L was `-$0.4668`, maximum drawdown `$0.7342`,
and the whole-date clustered one-sided-90 mean return was `-$0.05290857`. Mean conservative score `0.94114571` compared
with observed success `0.77142857`, a `0.16971714` reliability error; Brier skill versus displayed price was
`-0.30347895`. Every represented leave-one-station-out return bound was negative. There is no `$100` projection,
independent OOS credit, cohort, capital, production, recommendation, or order authority.

Reject the pooled offered-tail residual model. Do not retime, reprice, lower its edge, or promote a selected subgroup on
these consumed dates. A successor requires a new station-specific or otherwise causally recalibrated model and a new
independent date window. The parser and exact provider-settlement corrections remain valid source lessons.
