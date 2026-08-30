# NBM station-specific offered-tail NO development freeze

- Frozen: 2026-08-30 UTC, after pooled offered-tail v4 completed
- Identity: `noaa_nbm_v5_station_specific_wilson90_offered_tail_no_development_v1`
- State: development only on already-inspected 2026-06-27 through 2026-08-14 dates
- Independent OOS, production, credential, capital, recommendation, cohort, readiness, and order access: prohibited

## Question

The pooled offered-tail model selected 35 dates but overstated success by `0.16971714` and lost `-$0.4668` after exact
fees. Test one causal correction: retain the pooled model as an eligibility ceiling, then shrink each offered-tail score
to an exact station-specific one-sided 90% Wilson lower bound. This tests whether cross-station pooling caused the
overconfidence. It is a single model decision, not a station, price, clock, or outcome subgroup search.

The 49 development dates and every source value on them are already inspected. A pass can justify only a separately
frozen prospective successor beginning after this predeclaration. It cannot create independent OOS credit.

## Frozen model

Reuse the checksum-bound NBM Q50 and official observed-high inputs, exact station identities, and the 50 complete
training dates from 2026-05-08 through 2026-06-26. Reuse the exact two offered tail contracts per station/date and
integer residual arithmetic from pooled offered-tail v4.

For every exact `(station, strike type, integer Q50 offset)`:

1. Require exactly 50 station training outcomes and the unchanged pooled structure score.
2. Require both the unchanged pooled empirical prescreen and the station empirical success rate to be at least
   `0.920000`; exact equality passes.
3. Compute the analytic one-sided 90% Wilson lower success bound with `z = 1.2815515655446004` from the 50 station
   Bernoulli outcomes.
4. Set the conservative probability to the smaller of that station bound and the unchanged pooled conservative score,
   rounded down to four decimals. Require at least `0.9000`; exact equality passes and `0.8999` fails.

This correction can only reduce a pooled score. Missing training identity, a score above its pooled ceiling, a
nonexact offset, or any count other than 50 fails closed.

## Unchanged execution screen

Reuse the already-inspected 2026-06-27 through 2026-08-14 development window solely to decide whether a future
prospective freeze is warranted. Preserve the exact prior-day 14:30 UTC candle, displayed NO price `$0.55` through
`$0.97`, quadratic taker fee, minimum conservative edge `$0.0150`, one deterministic selection per market date, and
five-minute public NO-taker trade attribution. Rank higher conservative edge, then higher conservative probability,
then lower NO price, then ticker.

Preserve finalized provider settlement as the held-out outcome and the exact known singleton
`KMIA|2026-07-07|KXHIGHMIA-26JUL07-T88|less|88|0|no` reconciliation exception. Preserve the bounded three-attempt
transport policy, no retry for HTTP 429 or other 4xx, request ceiling 3,000, raw bodies, hashes, and portable manifest.

## Development gates

Every pooled-v4 gate remains unchanged and all must pass:

- at least 30 selected independent dates and at least ten stations;
- absolute selected reliability error at most `0.05` and positive Brier skill versus displayed NO price;
- at least 30 qualifying public taker fills on 30 dates;
- positive exact-fee realized net P&L, maximum drawdown at most `$5`, and a strictly positive one-sided date-clustered
  90% lower mean submission return;
- nonnegative lower return after excluding each represented station;
- maximum station share at most `0.15`; and
- exactly one selection per date.

Failure is terminal for this identity. Do not change the station floor, price, edge, clock, ranking, fill window, or
gates after observing the result. Passing permits only a new future-date OOS predeclaration; it does not permit a
cohort, capital, recommendations, production activation, orders, or a `$100` profit projection.
