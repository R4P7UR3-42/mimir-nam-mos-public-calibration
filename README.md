# Mimir Isolated Public Weather Research

This public repository contains credential-free, order-free weather-strategy calibration experiments. Each strategy
freezes its source, clocks, stations, dates, model, duplicate policy, and decision gates before acquiring its designated
evaluation evidence. Results from rejected families remain visible and are not reused as independent evidence.

Nothing in this repository can access Mimir production data, exchange credentials, capital settings, recommendations,
or order APIs. A passing result would justify only a separate reviewed current-market support and implementation
decision.

The original NAM one-shot run terminated on a frozen source-schema gate before outcomes were acquired. See
[`RESULT.md`](RESULT.md) for that checksum-bound rejection. The materially distinct
[GFS MOS station rolling Wilson-90 calibration](gfs_mos/RESULT.md) passed every frozen gate on 250 independent dates.
Its unchanged [executable-price OOS evaluation](gfs_mos_price/RESULT.md) then failed nine initial gates, with five public
trades, `-$0.4169` exact-fee P&L, adverse Brier skill, and a negative clustered lower return. That family is terminal.

The materially distinct [daily low-temperature market calibration](low_market_development/RESULT.md) also terminated in
training. All eight predeclared tail/price cells had negative multiple-testing-adjusted exact-fee lower returns; its
reserved evaluation stations remain untouched. No OOS workflow or trading authority is permitted for that identity.

The [GFS MOS precipitation development](gfs_mos_precipitation/DEVELOPMENT.md) is a credential-free, training-only
screen of a distinct daily no-rain model. It binds exact prior-day public MOS forecasts to NOAA precipitation outcomes,
treats trace precipitation as rain, and reserves 250 later dates untouched. It creates no trading authority.
