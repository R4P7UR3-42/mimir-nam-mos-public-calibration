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

The next materially distinct family is a [training-only daily low-temperature market calibration](low_market_development/DEVELOPMENT.md).
It precommits disjoint training/evaluation stations and eight exact tail/price cells, applies whole-date clustered and
multiple-testing-adjusted exact-fee gates, and cannot query its reserved evaluation inventory. A passing development
artifact would permit only a second frozen OOS workflow; it is not profitability, capital, policy, or order authority.
