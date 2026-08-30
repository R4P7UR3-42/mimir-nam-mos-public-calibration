# Mimir Isolated Public Weather Research

This public repository contains credential-free, order-free weather-strategy calibration experiments. Each strategy
freezes its source, clocks, stations, dates, model, duplicate policy, and decision gates before acquiring its designated
evaluation evidence. Results from rejected families remain visible and are not reused as independent evidence.

Nothing in this repository can access Mimir production data, exchange credentials, capital settings, recommendations,
or order APIs. A passing result would justify only a separate reviewed current-market support and implementation
decision.

The original NAM one-shot run terminated on a frozen source-schema gate before outcomes were acquired. See
[`RESULT.md`](RESULT.md) for that checksum-bound rejection. The current independent experiment is the materially
distinct [GFS MOS station rolling Wilson-90 calibration](gfs_mos/PREDECLARATION.md); it uses a frozen 250-date
evaluation and does not access historical market prices unless every forecast-calibration gate passes.
