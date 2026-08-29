# Completed Time-Surface V2 Development Result

- Identity: `noaa_nbm_v5_q90_pre_observation_liquidity_split_development_v2`
- Frozen commit: `4b14c6c`
- Annotated tag: `noaa-nbm-q90-time-development-v2`
- Sole run: `33231486677`, attempt 1, success
- Evaluation SHA-256: `b9524d22dde36150964f746b756baf7146458b969ef68a77c2a2241d37d09622`
- Portable artifact `SHA256SUMS` SHA-256: `1ef6d4120d2241c2ce1e1572a6ccf4c3e9912daf5549c1a92b42c93752735de3`
- Workflow log SHA-256: `26930db3929fd1afc544447ca8e0c629212e27a7abd45026157e46d362110060`

The split audit completed 1,688 public requests with no retry needed. Midnight UTC was the sole clock qualifying in the
50-date training half: 11 selected dates, seven stations, five public fills, and `+$0.8215` exact-fee P&L. The frozen
rank therefore selected `market_0000z`.

On the untouched 49-date half, that clock had 96 empty exact-Q90 candles, 47 nonempty candles missing a YES bid, zero
displayed prices, zero eligible submissions, and zero fills. Every sample, reliability, Brier, fill, P&L, clustered,
holdout, and concentration gate consequently failed. There is no `$100` projection, OOS credit, cohort, capital,
production, recommendation, or order authority.

The Q90 exact-threshold family is rejected for prospective execution under these clocks and economic boundaries. Do not
retune its time, price, edge, or sample. A distinct quantile or all-strike distribution hypothesis is required.
