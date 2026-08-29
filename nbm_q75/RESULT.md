# Completed Q75 Midnight Development Result

- Identity: `noaa_nbm_v5_q75_station_robust_midnight_split_development_v1`
- Frozen commit: `480be54db46b1eb2539c214a5162d35a207b13d5`
- Annotated tag: `noaa-nbm-q75-development-v1`
- Sole run: `33232153764`, attempt 1, success
- Evaluation SHA-256: `56832edc07bfe21f6d6f3e7826e011e214e6a8933be19d109e83d3f3db750246`
- Portable artifact `SHA256SUMS` SHA-256: `b38eb0244c3c8e7472c9eaf45b4cb3a37e3663e37160cf5c5dad63fefe3b8e7b`
- Workflow log SHA-256: `1f80e685ede588d510c79801a4a3d929bcc5500208740544a202a2e8a8b72f9d`

The training half produced exact conservative score `0.8189` from 1,000 rows, 50 independent dates, and all 20
leave-one-station-out checks. The 49-date held-out half contained 980 station/dates but only 53 exact Q75 greater-tail
contracts. Those contracts produced 21 nonempty midnight candles, zero displayed prices, zero submissions, and zero
public fills. Every economic and sample gate failed; there is no projection or authority.

The exact-Q75 midnight family is terminal and must not be retimed, repriced, or relabeled. Together with the terminal
Q90 result, it demonstrates that requiring a published forecast quantile to equal an offered tail strike is too sparse
for an execution strategy. A successor must use a separately frozen probability mapping over the offered inventory.
