# GFS MOS executable OOS result

- Identity: `gfs_mos_station_rolling_wilson90_executable_no_oos_v1`
- Exact-main run: [33284813243](https://github.com/R4P7UR3-42/mimir-nam-mos-public-calibration/actions/runs/33284813243)
- Commit: `afe7872f7858d5a1377bf6f6257c24bb76ab4e64`
- Run conclusion: success; the frozen evaluation completed without a source or implementation failure
- Evaluation report SHA-256: `987c82904b88a77aae0966137e5e3a39a56a9825161df2844fdf2a9b3f75d77c`
- Artifact `SHA256SUMS` SHA-256: `478507734916d317071151694bd5827b49252a8f991ec478b70308d698ad54f0`
- Predeclaration SHA-256: `57e0b81fcf181e081dd554bfa04143aae6d26b7a54bbf849039e1114c8af54ea`
- Source-contract addendum SHA-256: `07c901f83ef17c1ea7d1f0a08fa5ef4cedf11ec588b506fdf4ab11bfbd3185fd`
- Source capture SHA-256: `87db043f16eaa6c34cbf3e8b0fcb1702a12ece55b4e0cf822de694d491319dcb`

## Decision

Reject this exact economic policy. It is not eligible for a prospective cohort, capital-risk authority, production
activation, or a profitability claim. The independently successful parent weather calibration did not survive the
predeclared executable-price and public-fill test. Do not retune this identity after observing these results.

## Fixed-window result

The evaluation covered all 1,800 frozen station/dates over 180 independent dates and ten stations. It made 4,180
public requests under the frozen no-retry four-per-second policy. The support funnel was 526 score-eligible contracts,
286 nonempty exact decision candles, 43 eligible quotes, 33 selected one-per-date research submissions, and five
executable public taker trades.

The five executable trades produced four wins and one loss. Exact-fee realized net P&L was `-$0.4169`; maximum
drawdown was `$0.8969`; the one-sided clustered 90% lower mean submission return was `-0.04925455`. The model Brier
score was `0.13795963` and its displayed-price Brier skill was `-0.45732007`. Maximum station share was `0.30303030`
and maximum date share was `0.03030303`.

Nine initial gates failed: 100 selected dates, positive Brier skill, represented reliability bands, 30 executable
fills, positive realized net P&L, positive clustered 90% submission return, leave-one-station-out stability, station
concentration, and date concentration. Only the KSFO-excluded station holdout was positive; the other nine holdouts
were negative. The 250-date scale gate was also unavailable.

The exact executable fills were:

| Date | Station | Contract | NO price | Outcome | Exact-fee return |
| --- | --- | --- | ---: | --- | ---: |
| 2026-02-02 | KSEA | `KXHIGHTSEA-26FEB02-T55` | `$0.91` | win | `+$0.0842` |
| 2026-03-15 | KLAX | `KXHIGHLAX-26MAR15-T79` | `$0.91` | win | `+$0.0842` |
| 2026-04-08 | KLAX | `KXHIGHLAX-26APR08-T76` | `$0.75` | win | `+$0.2368` |
| 2026-06-03 | KMIA | `KXHIGHMIA-26JUN03-T89` | `$0.92` | win | `+$0.0748` |
| 2026-06-11 | KSFO | `KXHIGHTSFO-26JUN11-T89` | `$0.89` | loss | `-$0.8969` |

This research-only run did not access the production database, change active trading capability, place an order, or
grant capital-risk authority.
