# NBM Q90 Pre-Observation Liquidity Split Development Audit V2

- Frozen: 2026-08-29 UTC, after terminal v1 transport failure and before any v2 source request
- Identity: `noaa_nbm_v5_q90_pre_observation_liquidity_split_development_v2`
- Economic, split, clock, and model identity: unchanged from v1
- Parent Q90 price v3 evaluation SHA-256: `e12f0c642d5f7228d1ce7f5a584d6656cc9ce175c9f8b4d0efebe13068e16bde`
- Production, credential, capital, recommendation, cohort, readiness, and order access: prohibited

V1 is terminal after a remote TLS reset on request 31. V2 changes only transport recovery. Each logical public GET may
make at most three total attempts. Retry only `URLError`/socket/timeout failures or HTTP 5xx, after fixed one-second and
two-second delays. Count every attempt against the unchanged 3,000 ceiling and four-starts-per-second rate, and persist
attempt number, global request index, URL, error type/status, headers/body hash when present, and sanitized diagnostic.
HTTP 429, every other 4xx, malformed successful JSON, source identity failure, and the third transient failure are
terminal without retry. A later success must still satisfy create-once raw body, URL, header, and checksum rules.

Retain verbatim v1's five clocks, 50-date May 8–June 26 selection window, 49-date June 27–August 14 held-out window,
clock qualification/rank, exact Q90 model/contract/NO arithmetic, price, edge, fee, date rank, public trade fill,
bootstrap, reliability, P&L, drawdown, concentration, `$100` projection, and non-authorizing gates. No acquired v1
market/candle/trade result exists to pool or credit.

V2 receives exactly one public hosted run. Any source or diagnostic failure is terminal without another v2 run. A pass
is development support only and permits only a separately frozen future prospective identity; it creates no OOS credit,
cohort, capital, production, recommendation, or order authority.
