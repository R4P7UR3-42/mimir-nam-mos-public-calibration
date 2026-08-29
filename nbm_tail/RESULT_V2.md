# Terminal Offered-Tail V2 Source Result

- Identity: `noaa_nbm_v5_station_robust_offered_tail_no_split_development_v2`
- Frozen commit: `4253310dc78c646e305dbe2a7b38225bf407b520`
- Annotated tag: `noaa-nbm-tail-development-v2`
- Sole run: `33233123149`, attempt 1, terminal failure
- Portable artifact `SHA256SUMS` SHA-256: `8994d439358a6a0eff02b0c915a72763d35e7ca7c3aa18b2cc9894401b47562a`
- Workflow log SHA-256: `51f6beec372edc94e650af926fa47dae4fcfa3734a180d8f6b2374daac61a4a7`

V2 proved the per-ticker artifact correction and acquired 604 exact tail candles before stopping on a settlement-source
conflict. The frozen NOAA/NCEI row for KMIA on 2026-07-07 says `0°F`; finalized market
`KXHIGHMIA-26JUL07-T88` settled NO for `87°F or below`, requiring at least 88°F. A complete order-free reconciliation
of the already-acquired 49-date inventory found this as the sole conflict among 1,960 offered tails. The other 1,959
agree exactly. The impossible zero is also the only zero among the 1,980 frozen parent rows.

V2 is terminal and has no completed report or strategy result. A successor may keep the physically valid 1,000-row
training half, use finalized provider settlement for held-out outcome/P&L, and require the exact single known NCEI
conflict with no additional mismatch. It cannot change the model, clock, thresholds, fees, ranking, fill, or gates.
