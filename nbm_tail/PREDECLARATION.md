# NBM Residual Offered-Tail NO Split Development Audit

- Frozen: 2026-08-29 UTC, after the terminal Q75 result and before any tail-specific candle or trade request
- Identity: `noaa_nbm_v5_station_robust_offered_tail_no_split_development_v1`
- Parent NBM QMD evaluation SHA-256: `8b1baa59900d28542ba176bf81548178ed9bee72129e536b72a42ab5bdc393d5`
- Production, credential, capital, recommendation, cohort, readiness, and order access: prohibited

## Distinct Causal Model

Use the exact frozen NBM v5 Q50 and observed high for May 8 through June 26 (50 dates by 20 stations) to form integer
residual `observed_high - Q50`. Evaluate only Kalshi's offered lower and upper tail contracts, not an exact forecast
quantile and not any between contract. For a `greater` contract with floor `F`, NO success is residual at most
`F - Q50`. For a `less` contract with cap `C`, NO success is residual at least `C - Q50`. Require binary contract,
integer threshold, exact subtitle (`F+1° or above` or `C-1° or below`), finalized result agreeing with that arithmetic,
and the current exact event/series identity.

For every strike-type/integer-offset key actually present in the held-out offered inventory, first compute its exact
1,000-row training success mean. Keys below `0.920000` cannot qualify. For every remaining key, compute the fixed-seed
10,000-sample whole-date-clustered one-sided-90 lower success mean globally and after excluding each of the 20 stations.
The score is the minimum of all 21 lower means rounded down to `0.0001`; require at least exact `0.9000`. Market
inventory determines only the finite offset keys to calculate. Strike results, candles, prices, and trades cannot alter
the training score. The score is a development estimate, not calibrated OOS probability.

The split held-out window is June 27 through August 14 (49 already-consumed development dates). The sole causal decision
clock is prior-market-date `14:30Z`, after the frozen NBM availability bound `14:15Z` and before every station's target
local date. Query the exact one-minute candle only for training-qualified tail rows. Derive NO limit solely as
`1 - yes_bid.close`; require exact one-cent price `$0.55` through `$0.97` and edge
`score - limit - ceil_0.0001(0.07*limit*(1-limit))` at least `$0.0150`. Rank exactly one submission per date by
descending edge, higher conservative score, lower limit, then ticker.

Query one exact public NO-taker trade window `[14:30Z,14:35Z)` for each selection, require count at least one and price
no greater than limit, and choose earliest, lower price, then trade ID. A nonfill returns zero and cannot retry, extend,
or infer execution.

## Frozen Development Decision

Development support passes only if all source and identity checks pass and the held-out selection has:

1. at least 30 independent selected dates and ten stations;
2. absolute error between mean selected score and observed success at most `0.05`, plus positive Brier skill versus the
   displayed NO limit;
3. at least 30 exact public fills on 30 dates;
4. positive exact-fee realized P&L, drawdown at most `$5`, and strictly positive whole-date clustered-90 mean return;
5. every represented leave-one-station-out clustered-90 mean nonnegative;
6. maximum station share `0.15`, exactly one selection per date, and no outcome-dependent eligibility or rank; and
7. a non-guaranteed `$100` contracts/turnover projection only from a positive clustered lower mean.

Retain exact 20-series quadratic fee/no-history identity, complete current/archive inventory reconciliation, 3,000
total request attempts, four starts/second, at most three attempts only for transport/5xx with 1s/2s delays, terminal
429/other 4xx/malformed identity, raw attempt evidence, portable checksums, and a single public hosted run.

A pass is development support only. It permits a separately frozen future prospective identity but provides no
independent OOS credit, cohort, capital, production, recommendation, or order authority. Live progression still needs
at least 100 future dates, 30 settled provider fills on 30 dates, exact-fee positive conservative EV, bounded drawdown
and concentration, explicit capital authority, protected deployment, clean reconciliation, and verified autonomous
real-money outcomes. Scale remains gated at 250 future dates and clustered 95% evidence.
