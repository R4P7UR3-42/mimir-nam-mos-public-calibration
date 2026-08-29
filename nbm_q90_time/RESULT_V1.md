# Terminal Time-Surface V1 Transport Result

- Identity: `noaa_nbm_v5_q90_pre_observation_liquidity_split_development_v1`
- Frozen commit: `c97f71c`
- Annotated tag: `noaa-nbm-q90-time-development-v1`
- Sole run: `33231325154`, attempt 1
- Outcome: terminal transient transport failure before market/candle acquisition
- Portable artifact `SHA256SUMS` SHA-256: `e683deaff901ccf9a07eef2ad95e39d9cd7000381c5244a676f9863ae00c31ed`
- Workflow log SHA-256: `9df10650fd001dd9e74cfdc9e1bb3c0636773ed0cecd0389e57f6d01a21e28ca`

The runner passed every frozen hash and all six tests, then completed 30 public fee-identity requests. TLS setup for the
next series request was reset by the remote peer and Python surfaced `URLError: [Errno 104] Connection reset by peer`.
The no-retry v1 policy stopped immediately. No market, time-surface candle, trade, selection, outcome diagnostic, P&L,
OOS evidence, cohort, capital, production, recommendation, or order result exists. V1 is terminal and must not rerun.

The failure demonstrates that a multi-thousand-request public research capture needs bounded attempt-level recovery,
not an economic or evidence-gate change. A distinct v2 may retry only transport failures and HTTP 5xx at most twice
after the original request while counting and persisting every attempt; HTTP 429, other 4xx, malformed success, source
identity, and economic failures remain terminal.
