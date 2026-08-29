# 18Z Top-Tail Market-Implied NO Predeclaration

- Frozen: 2026-08-29 UTC, before any in-window evaluation-series request
- Identity: `daily_high_top_tail_market_implied_no_18z_v1`
- Training inventory SHA-256: `8779adc163f93e086ee866d89254cb99afa69da40c743631c74db9efbe4d6726`
- Evaluation inventory SHA-256: `50b20f576354bafae06ab34b98c3980536a3248017e58a4142c339c1bdd144dc`
- Production, database, credential, capital, recommendation, cohort, and order access: prohibited

## Distinct hypothesis and untouched split

Test whether the displayed market price at exactly 18:00Z on the calendar day before settlement contains a portable,
conservative edge in the top `greater` contract of Kalshi daily-high weather events. This is a different decision
horizon from the terminal 20Z v3 family. It uses a different exact quote and five-minute execution window, a different
market-date split, and an event-scoped acquisition contract. No v3 threshold, result, or failed source assumption is
reinterpreted.

Use only the five development series in `training_series.json` from 2026-02-11 through 2026-03-19 to estimate the
frozen price-bin calibration. Those station identities and outcomes are development data because the terminal v3
series-wide responses exposed their market metadata. Their 18Z quotes were not used by v3. Use only the 15 disjoint
series in `evaluation_series.json` on exactly 100 later market dates from 2026-03-21 through 2026-06-28 for the final
decision. No successful request for any evaluation-series event, market, candle, trade, or outcome inside this exact
window occurred before this freeze. The earlier KXHIGHTDC 2026-03-20 source canary is outside the split and receives
no credit. Resample whole market dates throughout. Any in-window evaluation request before the commit containing this
predeclaration invalidates the family.

## Public source and exact event acquisition

Use only Kalshi's public REST API. For each exact series/date, construct the zero-padded event ticker and request
`GET /historical/markets?event_ticker=...&limit=1000`. The official endpoint documents `event_ticker` as a mutually
exclusive exact filter. Require exactly one response, an empty terminal cursor, one event identity, and only markets
whose ticker prefix and event ticker agree. Do not use the failed series-wide pagination path. Missing, duplicate,
multi-page, wrong-series, or ambiguous event inventory fails the run.

Before any market request, fetch `GET /historical/cutoff` once. Require both `market_settled_ts` and
`trades_created_ts` to be exact UTC timestamps strictly after the complete evaluation market/fill window. This binds
all selected markets, candles, and public trades to the historical tier and forbids silently mixing live and archived
partitions. The 2026-08-29 source canary reported both cutoffs at `2026-06-30T00:00:00Z`, later than the last possible
2026-06-28 market settlement and the final 2026-06-27 18:05Z fill-window boundary.

Admit exactly one binary market per event with `strike_type=greater`, finite `floor_strike`, null `cap_strike`, and
final result `yes` or `no`. If present, require `occurrence_datetime` to agree with the market date,
`is_provisional=false`, null/empty MVE identity, and null fee waiver. Duplicate, provisional, MVE, ambiguous,
unsettled, or differently shaped events fail closed. Require complete coverage for every training and evaluation
series/date; there is no partial-credit path.

For the top contract request one 60-minute historical candle whose `end_period_ts` is exactly 18:00:00Z on the prior
calendar date. The decision quote is the finite exact `yes_bid.close`; the submitted NO limit is
`1 - yes_bid.close`, without midpoint, ask, or last-trade substitution. Empty candles and null/boundary bids are
noncandidates, never imputed. Persist every URL, header, raw response hash, parsed identity, and absence reason.

Fetch each exact series plus its complete `show_historical=true` fee-change history before evaluating its rows. Require
the unchanged standard quadratic direct-taker schedule: provider `fee_type=quadratic`, multiplier `1`, no maker fee,
no waiver, and `$0.0001` precision. Compute one-contract fees as
`ceil_0.0001(0.07 * price * (1 - price))`. Any fee identity drift fails the run.

Pace requests at no more than four per second, cap the whole run at exactly 4,000 requests, stop immediately on HTTP
429, and never retry. The event-scoped design projects 3,511 requests before explicit noncandidate reductions: one
cutoff request, 40 fee identity requests, 185 training event requests, at most 185 training candles, 1,500 evaluation
event requests, at most 1,500 evaluation candles, and at most 100 selected trade requests.

## Frozen training calibration

Partition decision NO limits into exactly `[0.7000,0.8000)`, `[0.8000,0.9000)`, and `[0.9000,0.9700]`. For each bin,
use every candidate development station/date. Success is the top contract settling NO. The display score is the
observed training frequency rounded once to four decimals. The conservative probability is the one-sided 90% lower
mean from 10,000 deterministic full-state bootstrap draws resampling whole market dates.

A bin is admissible only with at least 50 rows, at least 30 independent dates, and conservative probability minus the
bin's maximum price minus its exact fee at that price at least `$0.0150`. Exact boundaries pass; an adjacent lower
count, date count, or edge fails. If no bin is admissible, stop before any evaluation request and reject the family.
No bin, price, station, date, score, fee, edge, or selection boundary may change after this freeze.

## Frozen final evaluation and public executable-fill join

For each of the 100 evaluation dates, admit candidates in a training-admissible bin whose conservative probability
minus actual decision limit and exact fee is at least `$0.0150`. Rank by descending conservative net edge, lower NO
limit, then ticker. Select exactly one research-only counterfactual per date; no candidate on a date fails the complete
100-date gate but does not permit substitution.

For each selected ticker, query public historical trades only for `[18:00:00Z,18:05:00Z)` on the prior calendar date.
An executable fill requires a provider trade with `taker_outcome_side=no`, count at least one, and exact NO price no
greater than the submitted limit. Select earliest time, lower price, then trade ID. A nonfill earns zero submission
return and cannot be replaced, retried, extended, or inferred from volume. A filled win returns
`1 - fill_price - exact_fee`; a filled loss returns `-fill_price - exact_fee`.

The family passes initial evidence only if all conditions hold:

1. every source, split, market, candle, fee, result, trade, checksum, and 100-date selection identity is exact;
2. all 100 dates have one selection and at least ten evaluation stations are represented;
3. the frozen score has strictly positive Brier skill versus the displayed decision NO limit;
4. every selected bin has at least 30 evaluation dates and absolute observed-minus-score error at most `0.05`;
5. at least 30 provider-confirmed qualifying public fills occur across at least 30 dates;
6. realized exact-fee net P&L is positive, maximum drawdown is at most `$5.00`, and the one-sided whole-date-clustered
   90% lower mean submission return is strictly positive;
7. every represented leave-one-station-out clustered 90% lower mean is nonnegative;
8. maximum station share is at most `0.15`, maximum date share is exactly `0.01`, and no station has two selections on
   one date; and
9. projected contracts to `$100`, `ceil(100 / lower_90_mean)`, and gross turnover at maximum observed all-in cost are
   reported as non-guaranteed research projections only.

The 250-date clustered-95 scale gate is necessarily false. A pass permits only a separate reviewed Stage 1 cohort and
capital-risk decision. It creates no recommendation, capital, deployment, order, Stage 2, scale, or profit authority.
Any source or statistical failure is terminal: publish it without retry, retuning, subgroup reinterpretation, or reuse
of these evaluation dates for this hypothesis.
