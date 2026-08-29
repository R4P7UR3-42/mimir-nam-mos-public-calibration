# Terminal V1 Source Result

- Identity: `noaa_nbm_v5_q90_exact_threshold_no_development_v1`
- Frozen commit: `5176ad36236a642fce8e3da2f4fe24b28509793b`
- Annotated tag: `noaa-nbm-q90-price-development-v1`
- Sole run: `33230439903`, attempt 1
- Outcome: terminal source-scope rejection before economic evaluation
- Portable artifact `SHA256SUMS` SHA-256: `44488cc8a1cf83734a7dd807c719223ef7e9841b80b67490e44ebe81996dfcd3`
- Workflow log SHA-256: `4ef9642bd7bb599d2c1095b2591158275d5b2f40950287af324525b1a55bfa63`

The public runner passed every frozen hash and all nine structural tests. It then made exactly 60 of the allowed 3,000
public requests and stopped without retry. The source parser rejected Austin's archived series because the provider's
complete `series_ticker=KXHIGHAUS` history contains 3,165 legacy `HIGHAUS-*` rows from 2023-05-11 through 2024-10-23
alongside 3,672 current `KXHIGHAUS-*` rows. V1 validated the current prefix before applying its 2026-05-08 through
2026-08-14 study window, so irrelevant legacy history produced `Historical market identity drifted for KXHIGHAUS`.

The failure happened after the 40 fee-identity requests, Atlanta's archived inventory and 12 exact-Q90 candle reads,
and Austin's seven archived pages. It produced no report, selections, trade queries, fill result, P&L, OOS evidence,
capital authority, cohort, recommendation, production change, or order. The uploaded raw bodies, headers, request URLs,
and body hashes pass their portable checksum manifest.

V1 is terminal and must not be rerun. A separate v2 may correct only the demonstrated source boundary: merge the
provider's moving live and archived market partitions and apply tolerant date-suffix parsing only to discard rows
outside the already-frozen development window. Every in-window row must retain the exact current series/event identity,
and every economic, fee, selection, fill, statistical, concentration, drawdown, and authority rule remains unchanged.
