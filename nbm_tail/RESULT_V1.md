# Terminal Offered-Tail V1 Source Result

- Identity: `noaa_nbm_v5_station_robust_offered_tail_no_split_development_v1`
- Frozen commit: `59a770fd46cf6c7e3ba7bd6eab36e8ab13771670`
- Annotated tag: `noaa-nbm-tail-development-v1`
- Sole run: `33232781137`, attempt 1, terminal failure
- Portable artifact `SHA256SUMS` SHA-256: `ee87609e56b006576db56c84db4411c6a6a9d05dc83f971785b0d15b9ef56990`
- Workflow log SHA-256: `387f1091640e09ceab933f49ef226858f182af1d6e8b4508a3cc71d88c4d1902`

V1 completed source discovery and conservative score derivation, then captured three exact KATL candles. It stopped when
the second qualified tail contract for KATL on 2026-06-29 reused the station/date/clock create-once filename belonging
to the first tail contract. The differing response correctly raised `Create-once source changed`. The artifact seals
and verifies but contains no report, economic result, or strategy evidence. V1 is terminal and cannot be rerun.

A successor may change only the raw candle artifact label to include the exact market ticker. It must preserve the
frozen model, sample, clock, price, edge, fee, selection, fill, statistical, concentration, projection, and authority
contract.
