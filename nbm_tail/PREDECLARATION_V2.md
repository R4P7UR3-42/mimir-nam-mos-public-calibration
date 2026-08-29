# NBM Residual Offered-Tail NO Split Development Audit V2

- Frozen: 2026-08-29 UTC, after terminal v1 run `33232781137`
- Identity: `noaa_nbm_v5_station_robust_offered_tail_no_split_development_v2`
- Economic/model identity: unchanged from v1
- Production, credential, capital, recommendation, cohort, readiness, and order access: prohibited

## Sole Source Correction

V1 is terminal and receives no strategy result. Its inherited candle consumer labeled raw evidence only by station,
date, and decision clock. That label is unique for an exact-quantile strategy but collides when both offered tails for
one station/date qualify. V1 correctly stopped create-once at KATL 2026-06-29 when the second ticker returned a different
source body.

V2 changes only the raw candle artifact identity to include the exact market ticker in addition to station, date, and
clock. Preserve the response URL, partition, timestamp, ticker checks, body, headers, request metadata, create-once
behavior, bounded transport recovery, and terminal source semantics. Test two tails for one station/date and require
distinct exact artifact identities. Do not reuse v1 responses and do not rerun v1.

## Unchanged Frozen Decision

Retain every rule in `PREDECLARATION.md`: exact frozen NBM v5 Q50/observed inputs; May 8–June 26 training; June 27–August
14 held-out development; offered binary finalized `less`/`greater` tails and exact arithmetic; 0.920000 empirical
prescreen; fixed-seed 10,000-sample whole-date and 20 station-holdout conservative scores; exact 0.9000 minimum; prior
14:30Z causal candle; displayed NO limit `$0.55`–`$0.97`; exact quadratic fee and `$0.0150` edge; one deterministic
selection per date; exact five-minute public NO-taker fill; 30-date/ten-station/30-fill, reliability, Brier, P&L,
drawdown, clustered, holdout, concentration, and projection gates; 3,000 attempt ceiling; and all non-authorizing labels.

V2 receives one public hosted run. A pass remains development support only and creates no independent OOS credit,
cohort, capital, production, recommendation, or order authority.
