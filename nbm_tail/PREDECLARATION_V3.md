# NBM Residual Offered-Tail NO Split Development Audit V3

- Frozen: 2026-08-29 UTC, after terminal v2 run `33233123149`
- Identity: `noaa_nbm_v5_station_robust_offered_tail_no_split_development_v3`
- Economic/model identity: unchanged from v1/v2
- Production, credential, capital, recommendation, cohort, readiness, and order access: prohibited

## Sole Outcome-Source Correction

V2 is terminal and receives no strategy result. Its exact settlement-arithmetic check exposed one impossible frozen
NOAA/NCEI held-out outcome: KMIA 2026-07-07 is `0°F`, while finalized `KXHIGHMIA-26JUL07-T88` settled NO for `87°F or
below`. Complete reconciliation of the v2 inventory found exactly that one conflict among 1,960 tails; all other 1,959
agree, and the zero is the only zero among 1,980 parent rows.

Require every May 8–June 26 training observed high to be within inclusive `[-50°F,140°F]`; keep all 1,000 training rows
unchanged. For June 27–August 14 only, derive settlement/P&L outcome from the exact finalized provider market `result`,
which is the payable contract outcome and is not used in score, eligibility, price, edge, or rank. Reconcile it against
the frozen NCEI high and require the complete conflict set to be exactly:

`KMIA|2026-07-07|KXHIGHMIA-26JUL07-T88|less|88|0|no`.

Missing that conflict, any additional conflict, a non-finalized result, or any identity drift is terminal. Persist the
full conflict diagnostic. Do not repair, replace, or reinterpret the frozen NCEI row.

## Unchanged Frozen Decision

Retain v2's per-market raw artifact identity and every rule in `PREDECLARATION.md`: frozen Q50 inputs; exact training
and held-out dates; offered tail structures; empirical and clustered station-robust scores; exact 0.9000 floor; causal
prior-14:30Z candle; displayed `$0.55`–`$0.97` NO price; exact fee and `$0.0150` edge; deterministic one-date rank;
five-minute public taker fills; all sample, reliability, Brier, P&L, drawdown, clustered, holdout, concentration, and
projection gates; bounded transport; and every non-authorizing label.

V3 receives one public hosted run. A pass remains development support only and creates no independent OOS credit,
cohort, capital, production, recommendation, or order authority.
