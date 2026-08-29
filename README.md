# Mimir NAM MOS Public Calibration

This public repository contains one credential-free, order-free calibration test of archived NOAA NAM Model Output
Statistics maximum-temperature guidance. The exact source, clocks, stations, dates, model, duplicate policy, and
decision gates are frozen in [`PREDECLARATION.md`](PREDECLARATION.md) before any outcome or market-price acquisition.

Nothing in this repository can access Mimir production data, exchange credentials, capital settings, recommendations,
or order APIs. A passing result would justify only a separate reviewed current-market support and implementation
decision.

The one-shot run terminated on a frozen source-schema gate before outcomes were acquired. See
[`RESULT.md`](RESULT.md) for the checksum-bound rejection and no-retry decision.
