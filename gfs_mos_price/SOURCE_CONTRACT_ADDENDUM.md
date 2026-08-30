# GFS MOS executable OOS source-contract addendum

- Recorded: 2026-08-30 UTC
- Failed run: [33284182092](https://github.com/R4P7UR3-42/mimir-nam-mos-public-calibration/actions/runs/33284182092)
- Designated Kalshi candles/trades accessed: **none**
- Statistical, economic, station, date, model, clock, score, price, fee, fill, and decision gates changed: **none**

The first source-only attempt completed all ten exact IEM GFS captures, then stopped on the fresh NOAA
`isd-history.csv` catalog because its current ICAO/WBAN rows report `END` dates only from 2025-08-25 through
2025-08-27. The frozen source window begins 2025-09-01. This is a catalog freshness boundary, not a conflicting station
mapping: every exact ICAO, WBAN, name, and coordinate still agrees, and the subsequent NCEI Daily Summaries responses
are the authoritative source that must prove the exact mapped GHCN station has complete `TMAX` data through the full
2026-06-28 window.

The replacement source parser may therefore omit only the ISD-row requirement that `END` reach the evaluation end. It
must still require:

1. exact ICAO identity and one exact non-`99999` WBAN mapping;
2. history `BEGIN` no later than the source-window start;
3. recorded ISD `END` no earlier than exactly `20250825`;
4. station coordinates within the unchanged 0.2-degree tolerance;
5. ten unique GHCN station mappings; and
6. complete, exact, finite NCEI `TMAX` rows for all 3,010 station/dates, which independently proves data continuity
   through the target window.

An ISD `END` of `20250824`, missing or ambiguous ICAO/WBAN, coordinate drift, incomplete NCEI coverage, or any other
source error remains terminal. The replacement run remains price-blind until this complete source contract passes.

## Complete-source serialization correction

Replacement run
[33284302603](https://github.com/R4P7UR3-42/mimir-nam-mos-public-calibration/actions/runs/33284302603)
then completed the corrected 13-request source contract, including all 3,010 rows. The shared capture report serialized
the profile-independent literals `requested_dates=395` and `complete_dates=395` left from the parent 20-station
calibration, so the economic reader rejected the otherwise complete 301-date capture before constructing a Kalshi
client. No fee, market, candle, or trade request occurred.

The bounded correction derives both coverage fields from the exact profile date list. Parent coverage remains 395;
economic coverage becomes 301. It changes no source row, model, score, market window, price, fee, fill, statistical,
economic, or authority rule.

## Exact historical-cutoff boundary correction

Replacement run
[33284399090](https://github.com/R4P7UR3-42/mimir-nam-mos-public-calibration/actions/runs/33284399090)
passed the complete corrected source capture and all ten unchanged fee identities. Kalshi's public cutoff was exactly
`2026-06-30T00:00:00Z`, equal to the frozen June 28 market date plus the conservative two-day settlement boundary. The
reader incorrectly required it to be strictly later and stopped before requesting an event inventory, candle, or
trade.

Exact equality is complete historical coverage and now passes; `2026-06-29T23:59:59.999999Z` and anything earlier fail.
The trade cutoff remains required strictly after the final five-minute decision window. This changes no market date,
contract, score, quote, fee, fill, statistical, economic, or authority rule.
