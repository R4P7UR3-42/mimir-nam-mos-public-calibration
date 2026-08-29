# Completed V3 Development Result

- Identity: `noaa_nbm_v5_q90_exact_threshold_no_development_v3`
- Frozen commit: `b5ef5cf`
- Annotated tag: `noaa-nbm-q90-price-development-v3`
- Sole run: `33230929714`, attempt 1, success
- Evaluation SHA-256: `e12f0c642d5f7228d1ce7f5a584d6656cc9ce175c9f8b4d0efebe13068e16bde`
- Portable artifact `SHA256SUMS` SHA-256: `da08c6401a0b6712e62073da72393fff9d60daf73b7ec64f60c97c899a44de2e`
- Workflow log SHA-256: `a33eb1f28d4b83e93a68d3848335101919dda3c2b9736480ea24dfa5ab1aae98`

The exact 99-date × 20-station audit completed in 432 public requests with no retry or HTTP 429. The source funnel had
1,980 parent station/dates, 306 exact Q90 contracts across 95 dates and all 20 stations, 113 nonempty candles, 49
displayed NO prices, seven eligible quotes across six dates, and one qualifying public taker trade.

The selected sample was six dates and six stations with observed success `0.83333333`, reliability error `0.09966667`,
and positive displayed-price Brier skill `0.02910297`. The one executable fill won for exact-fee net `+$0.1031`, but
the whole-date clustered-90 lower mean was exactly zero. Sample size, station count, reliability, fill count, clustered
return, and concentration all failed. There is no `$100` projection, OOS credit, capital authority, prospective cohort,
production activation, recommendation, or order authority.

The exact-contract inventory itself is broadly reachable—95 of 99 dates—but the prior-day 14:30Z quote is not. A
distinct development successor may measure a predeclared later pre-observation liquidity surface while retaining the
same Q90 model, economic boundaries, exact fee, and fill rules. V3 is terminal and must not be rerun or threshold-tuned.
