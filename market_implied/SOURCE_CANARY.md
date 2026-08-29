# Market-Implied Source Canary

- Captured: 2026-08-29 UTC, before any evaluation-series request
- Production, account, credential, order, portfolio, and Mimir database access: none
- Provider requests: 19 bounded public reads; no HTTP 429 and no retry loop

Kalshi's public historical market endpoint returned 137 to 167 independent daily-high events for each of five
development-only series. `KXHIGHNY` contains exactly 167 consecutive events from `2026-01-12` through `2026-06-27`.
The other sampled series contain the complete proposed evaluation interval from `2026-03-20` through `2026-06-27`.
Only the five identities in `training_series.json` were requested. None of the 15 identities in
`evaluation_series.json` was requested or otherwise inspected.

One development series and market proved the required public source shapes:

- `GET /series/KXHIGHNY` returned `fee_type=quadratic` and `fee_multiplier=1`;
- its complete `show_historical=true` fee-change response was an empty `series_fee_change_arr`, establishing the
  unchanged provider baseline for this development series;

- exact top contract: `strike_type=greater`, `floor_strike=83`, null `cap_strike`, settled `result=no`;
- `open_time=2026-06-26T14:00:00Z`, one day before its market date;
- an exact 60-minute candle ending `2026-06-26T20:00:00Z` with `yes_bid.close=0.0000`,
  `yes_ask.close=0.0100`, prior trade price `0.0200`, and zero interval volume; and
- public historical market and candle reads required no authentication header.

The canary deliberately did not treat a displayed quote as a fill. The frozen evaluation must separately bind a
qualifying public NO-taker trade inside the prospective five-minute order window before it records executable-fill or
realized-P&L evidence.
