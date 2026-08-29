# Top-Tail Market-Implied NO Predeclaration

- Frozen: 2026-08-29 UTC, before any evaluation-series request
- Identity: `daily_high_top_tail_market_implied_no_v3`
- Training inventory SHA-256: `8779adc163f93e086ee866d89254cb99afa69da40c743631c74db9efbe4d6726`
- Evaluation inventory SHA-256: `50b20f576354bafae06ab34b98c3980536a3248017e58a4142c339c1bdd144dc`
- Production, database, credential, capital, recommendation, cohort, and order access: prohibited

## Purpose and untouched split

Test whether the displayed market price itself contains a portable, conservative edge in the top `greater` contract
of Kalshi daily-high weather events. This is not another forecast model. It is a single-contract taker strategy whose
price, fee, five-minute limit window, public fill evidence, and settlement economics are evaluated together.

Use only the five development series in `training_series.json` from `2026-01-12` through `2026-03-19` to estimate the
frozen price-bin calibration. Use only the 15 untouched station series in `evaluation_series.json` on exactly 100
market dates from `2026-03-20` through `2026-06-27` for the final decision. Training and evaluation series are
disjoint; their station identities may not be substituted. Resample whole market dates throughout. The final result is
station-held-out and temporally later than the training prefix. Any request for an evaluation-series market, candle,
trade, or result before this predeclaration commit invalidates the family.

## Public source and causal decision identity

Use only Kalshi's public REST API. Discover every page of each exact series with `GET /historical/markets`, requiring a
terminal empty cursor within two pages and one complete event inventory per frozen date. Parse the market date from the
exact event-ticker suffix and, when `occurrence_datetime` is non-null, require it to agree with that date. Admit exactly
one binary market per event with `strike_type=greater`, a finite `floor_strike`, null `cap_strike`, and final result
`yes` or `no`. The archived-market schema may omit `is_provisional`, `mve_collection_ticker`, and
`fee_waiver_expiration_time`; omission is accepted only because the exact series filter, non-MVE ticker identity,
binary shape, and final settlement result remain present. If any of those optional fields is present, require
`is_provisional=false`, null/empty MVE identity, and null fee waiver. Duplicate, explicitly provisional, MVE,
ambiguous, unsettled, or differently shaped events fail the run.

For that top contract request one 60-minute historical candle whose `end_period_ts` is exactly `20:00:00Z` on the
calendar date before the market date. The decision quote is the exact finite `yes_bid.close`; the submitted NO limit is
`1 - yes_bid.close`, without midpoint or last-trade substitution. An empty candle or null/zero/one/out-of-range bid is
a noncandidate, not permission to impute a quote. Persist every URL, response header, raw body hash, parsed identity,
and absence reason. Stop immediately on HTTP 429 and never retry any request. Pace reads at no more than four per
second and cap the complete run at 2,200 network requests.

Before any candle evaluation, fetch each exact series plus its complete `show_historical=true` fee-change history.
Require the reviewed unchanged standard direct-taker schedule with provider `fee_type=quadratic`, provider
`fee_multiplier=1`, no maker fee, and `$0.0001` balance precision at every decision. The provider multiplier scales
Kalshi's standard quadratic base coefficient `0.07`; it is not itself `0.07`. A fee change, missing history,
future-only evidence, unsupported precision, waiver, or different fee type fails the run. For one contract at price
`p`, compute `ceil_0.0001(0.07 * 1 * p * (1 - p))` exactly with decimal arithmetic.

## Frozen training calibration

Partition decision NO limits into exactly these disjoint bins:

1. `[0.7000, 0.8000)`;
2. `[0.8000, 0.9000)`; and
3. `[0.9000, 0.9700]`.

For each bin, use every eligible development station/date. Success is the top contract settling NO. The bin score is
the observed training success frequency rounded once to four decimal places. The conservative probability is the
one-sided 90% lower mean from 10,000 deterministic full-state bootstrap draws that resample whole market dates and
retain all within-date stations. A bin is frozen as admissible only when it contains at least 50 rows over at least 30
independent dates and its conservative probability minus the bin's maximum entry price minus the exact fee at that
maximum price is at least `$0.0150`. Exact boundaries pass; an immediately lower row/date count or edge fails. If no
bin is admissible, stop before requesting evaluation data and reject the family.

No price boundary, station, date, score, bin, fee, edge, selection, or fill rule may change after this commit.

## Frozen final evaluation and executable-fill join

For every evaluation date, construct candidates from all 15 exact top contracts whose decision limit lies in an
admissible training bin and whose conservative probability minus actual decision limit minus its exact fee is at least
`$0.0150`. Rank by descending conservative net edge, then lower NO limit, then ticker. Submit exactly one research-only
counterfactual per date. Zero or multiple selected rows for a date fails the complete 100-date decision.

For each selected ticker, query public historical trades only for `[20:00:00Z,20:05:00Z)` on the prior calendar date.
An executable fill exists only when the response contains a provider trade with `taker_outcome_side=no`, count at
least one, and exact NO price no greater than the submitted decision limit. Select the earliest qualifying trade, then
lower price and trade ID. Use one contract at that actual price and its exact fee. No qualifying trade produces zero
execution P&L and remains an explicit nonfill; it may not be replaced, retried, extended, crossed later, or inferred
from candle volume. A filled win returns `1 - fill_price - fee`; a filled loss returns `-fill_price - fee`.

The family passes its initial evidence decision only if every condition holds:

1. all source, split, market, candle, fee, result, trade, checksum, and 100-date selection identities are exact;
2. all 100 independent evaluation dates have one selection and at least ten evaluation stations are represented;
3. the frozen score has strictly positive Brier skill versus the displayed decision NO limit;
4. every selected admissible bin has at least 30 evaluation dates and absolute observed-minus-score error at most
   `0.05`;
5. at least 30 provider-confirmed qualifying public fills occur across at least 30 dates;
6. realized net P&L is positive, maximum drawdown is at most `$5.00`, and the one-sided whole-date-clustered 90% lower
   mean submission return is strictly positive;
7. every represented leave-one-station-out clustered 90% lower mean is nonnegative;
8. maximum station share is at most `0.15`, maximum date share is exactly `0.01`, and no station contributes more than
   one selection on a date; and
9. the projected contracts to `$100`, `ceil(100 / lower_90_mean)`, and gross turnover at the maximum observed all-in
   cost are reported as non-guaranteed research projections only.

The earlier `daily_high_top_tail_market_implied_no_v1` draft is superseded before any evaluation-series request because
it mislabeled the provider multiplier as the base coefficient. The v2 draft is likewise superseded before evaluation
because it required three optional current-market fields that the historical-market source omits. Neither receives
data or decision credit.

The 250-date clustered-95 scale gate is necessarily false in this 100-date evaluation and must be reported false. A
pass permits only a separate reviewed Stage 1 cohort and capital-risk decision. It does not authorize a recommendation,
capital, deployment, order, Stage 2, scale, or profit claim. Any source or statistical failure is terminal: publish it,
do not rerun, retune, reuse the evaluation dates, or reinterpret a subgroup.
