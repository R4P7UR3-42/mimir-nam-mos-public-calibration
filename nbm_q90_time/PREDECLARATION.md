# NBM Q90 Pre-Observation Liquidity Split Development Audit

- Frozen: 2026-08-29 UTC, after terminal Q90 price v3 and before any new time-surface candle request
- Identity: `noaa_nbm_v5_q90_pre_observation_liquidity_split_development_v1`
- Parent Q90 price v3 evaluation SHA-256: `e12f0c642d5f7228d1ce7f5a584d6656cc9ce175c9f8b4d0efebe13068e16bde`
- Production, credential, capital, recommendation, cohort, readiness, and order access: prohibited

## Causal Design

Retain the exact checksum-bound NBM inputs, 20 station/series map, Q90 `greater` contract, `0.933000` conservative NO
probability, `$0.55`–`$0.97` limit, `$0.0150` exact quadratic-fee edge, one contract, public taker-fill rule, market and
candle partition routing, trade cutoff routing, no retry, and all source identity checks from the completed v3 audit.
The source forecast was available by prior-day 14:15Z.

Measure exactly five UTC decision clocks, all before 04:00Z on the market date and therefore before the earliest US
station's local calendar observation date begins:

1. prior day `14:30Z`;
2. prior day `18:00Z`;
3. prior day `21:00Z`;
4. market date `00:00Z`; and
5. market date `03:00Z`.

For every exact Q90 contract, request one exact one-minute candle at every clock. Use only `1 - yes_bid.close`, the same
price/fee/edge eligibility, and the same descending-edge/lower-limit/ticker rank to retain at most one candidate per
date and clock. Empty or missing-sided candles are noncandidates. No later observation, midpoint, last trade, imputation,
fallback, or alternate model is allowed.

## Fixed Split And Time Selection

The 99 already-consumed development dates are not OOS. Use May 8 through June 26 (50 dates) only to select a clock and
June 27 through August 14 (49 dates) only for the held-out development diagnostic.

For every clock's training candidates, query the exact public five-minute trade window and report exact-fee P&L, but do
not rank on outcomes or P&L. A clock qualifies for selection only with at least ten selected training dates, five exact
public fills on five dates, and five stations. Rank qualified clocks by more fills, then more selected dates, then more
stations, then the earlier frozen clock order. If no clock qualifies, stop with no held-out trade queries and reject the
identity.

Evaluate only the selected clock on the 49 held-out dates. It passes development support only if every source check and
all of these gates pass:

1. at least 15 selected independent dates and five stations;
2. reliability error versus `0.933000` at most `0.07` and strictly positive Brier skill versus displayed NO limit;
3. at least ten qualifying public taker fills on ten dates;
4. positive exact-fee realized P&L, drawdown at most `$5`, and strictly positive whole-date clustered-90 mean submission
   return, with nonfills retained as zero;
5. every represented leave-one-station-out clustered-90 mean nonnegative;
6. maximum station share at most `0.25` and exactly one selection per date; and
7. a non-guaranteed `$100` contracts/turnover projection only from the positive clustered lower mean.

Use 10,000 fixed-seed whole-date bootstrap samples. The public request ceiling remains exactly 3,000 with at most four
starts per second, no retry, and terminal HTTP 429. Persist raw bodies, headers, request URLs/hashes, complete clock
rows, training diagnostics, selected-clock identity, held-out selections/trades, exact fees, and portable checksums.

Any source or diagnostic failure is terminal without rerun, clock changes, threshold changes, or subgroup slicing. A
pass is still development support only. It permits a separately reviewed prospective identity beginning after this
result, but creates no independent OOS credit, cohort, capital, production, recommendation, or order authority. Future
live evidence still requires at least 100 independent dates, 30 settled provider fills on 30 dates, exact-fee positive
conservative EV, bounded drawdown/concentration, explicit capital authority, protected deployment, clean reconciliation,
and verified autonomous real-money outcomes. The 250-date clustered-95 scale gate remains false.
