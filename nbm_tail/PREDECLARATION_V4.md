# NBM Residual Offered-Tail NO Split Development Audit V4

- Frozen: 2026-08-29 UTC, after completed v3 run `33233636192`
- Identity: `noaa_nbm_v5_station_robust_offered_tail_no_split_development_v4`
- Economic/model identity: unchanged from v1/v2/v3
- Production, credential, capital, recommendation, cohort, readiness, and order access: prohibited

## Sole Candle-Schema Correction

V3's 449 nonempty candles split exactly into 12 archived legacy rows with `yes_bid.close`, 437 current rows with
`yes_bid.close_dollars`, and zero rows with both. The inherited parser recognized only the legacy field and mislabeled
current quotes as missing. A sealed-evidence parser-only replay found 432 nonboundary displayed bids and 62 eligible
rows over 34 dates and 19 stations; this is reachability evidence, not fill or outcome evidence.

V4 accepts exactly one non-null close field. Legacy `close` retains its existing decimal parsing. Current
`close_dollars` must be a string matching exact dollars precision `^[01]\\.[0-9]{4}$`; parse it as the same Decimal
price. Both fields non-null, malformed dollars, boundary price, non-cent-derived NO limit, ticker/timestamp drift, or
unknown candle shape fails closed. Neither field remains a noncandidate missing bid. Persist the exact per-market raw
artifact identity from v2. Test legacy, current, both-field, malformed, boundary, and distinct-tail cases.

## Unchanged Frozen Decision

Retain v3's exact provider-result reconciliation and every rule in the original predeclaration: frozen Q50/training;
station-robust scores; exact 0.9000 floor; offered tails; prior 14:30Z decision; `$0.55`–`$0.97` displayed NO price;
exact quadratic fee and `$0.0150` edge; one deterministic selection per date; five-minute public NO-taker fill; every
sample, calibration, Brier, P&L, drawdown, clustered, holdout, concentration, and projection gate; bounded transport;
and all non-authorizing labels.

V4 receives one public hosted run. A pass remains development support only and creates no independent OOS credit,
cohort, capital, production, recommendation, or order authority.
