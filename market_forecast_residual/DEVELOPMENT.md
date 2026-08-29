# Market-plus-forecast residual development freeze

- Frozen before the first combined training request: 2026-08-29 UTC
- Development identity: `daily_high_top_tail_market_ecmwf_residual_18z_development_v1`
- Scope: training-only; evaluation inventory and dates are forbidden
- Production, database, credential, capital, recommendation, cohort, and order access: prohibited

## Causal inputs

Use the ten exact station/series rows in `training_stations.json` on 2026-02-11 through 2026-03-19. At 18:00:00Z
on the prior day, capture the top `greater` contract's displayed NO limit as one minus the exact hourly YES-bid close.
Use only the exact Open-Meteo Single Runs `ecmwf_ifs` run initialized at 06:00:00Z on that prior day. The six-hour
publication buffer is fixed. Compute the forecast maximum from its hourly Fahrenheit values whose UTC timestamps map
to the contract's exact local calendar date. Persist request URLs, response headers, raw bodies, and hashes.

The Open-Meteo free endpoint is used only for this evaluation/prototyping capture and is prohibited as a production
dependency. Any successor must separately reproduce its exact forecast feature through Mimir's direct ECMWF open-data
ingest, under the ECMWF data licence, before it can become a cohort or receive trading authority. A research pass may
not introduce an Open-Meteo subscription, API key, or commercial runtime dependency.

Training rows require a displayed NO limit in `[0.5000,0.9700]`, a finite top threshold, an exact final outcome, and
complete forecast coverage. One-contract taker fee is `ceil_0.0001(0.07*p*(1-p))`. This is model development, not
calibration, executable evidence, or profit evidence. Stop on HTTP 429 without retry, pace all sources at no more than
four requests per second, and enforce an exact 5,000-request ceiling.

## Frozen model menu and selection

Fit exactly three ridge-logistic candidates with lambda `0.1`, an unpenalized intercept, forecast distance scaled by
five Fahrenheit degrees, deterministic Newton updates, and scores clipped to `[0.001,0.999]`:

1. `market_offset`: fixed displayed-price logit offset plus fitted intercept and forecast distance;
2. `market_free`: fitted intercept, displayed-price logit coefficient, and forecast distance;
3. `forecast_only`: fitted intercept and forecast distance.

Generate out-of-fold predictions by leaving out one whole market date at a time. A candidate is development-admissible
only with at least 100 rows, 30 dates, and eight stations; positive OOF Brier skill and log-loss improvement versus the
displayed NO limit; absolute mean calibration error at most `0.03`; and a positive forecast-distance coefficient in
every leave-one-station-out fit. `market_free` additionally requires a positive market-logit coefficient in every such
fit. Choose the lowest OOF Brier among admissible candidates, breaking an exact tie by the order above, and refit it on
all training rows.

The output may freeze one successor hypothesis only after its exact coefficients and score boundaries are published
before any evaluation request. If none is admissible, terminate this model family. Never use this development run as
OOS, fill, P&L, capital, readiness, deployment, or trading authority.
