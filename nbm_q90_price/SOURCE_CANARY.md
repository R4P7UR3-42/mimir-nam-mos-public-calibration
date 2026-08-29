# Excluded-Date Public Source Canary

- Captured: 2026-08-29 UTC, before freezing the 99-date development window
- Excluded market date: `2026-05-07`
- Scope: 20 exact station/series identities from `station_series.json`
- Provider access: public historical market and one-minute candle reads only
- Credentials, orders, production data, and trading capability: none

The bounded canary requested each exact May 7 historical event inventory. It found all 20 event identities, three exact
Q90 `greater` contracts, three one-minute candle responses, one candle with a displayed YES bid, and zero quotes passing
the later-frozen Q90 NO price-and-edge rule. The only displayed quote was Los Angeles: YES bid `$0.04`, implied NO limit
`$0.96`, and negative conservative edge. No historical trade request was made. The entire May 7 date is excluded from
the development audit; it receives no calibration, economic, fill, or OOS credit.

The create-once canary bundle contained the 20 event-market payloads, the three exact-Q90 candle payloads, and the frozen
station/Q90 inventory. Its sorted portable `SHA256SUMS` file hashes to
`0796f65031205ffdbb3fdb715f0bcf9cfcec870ff63bebdd0127a8d44bad1e46`. Representative source hashes are:

- KATL markets: `2e001ae638838b47405bd85cd2640904ebc59b1febdb28ee02340ab634f842ef`
- KATL candle: `828f4d4f223c09590650300ed6205a2970f9cef553bdcd2cca1421aa7756f645`
- KLAX markets: `dfa74f83e63f0bae3869801003d0f40effd8acb2a6ce0f65863a9c60bc96f442`
- KLAX candle: `97b5d7970ec5af4f90652004f67c3c770dcefc33a85da6254a0260003af9dfde`
- KMIA markets: `cec48662bdcbe25620740a74e3f14905b178320ce78e33b10c5b25045f64cafb`
- KMIA candle: `3bcb0656f06606566496214f1b6f2fd6a5755969f3c3311f756ecaad04710d64`
- station/Q90 inventory: `b6102ef471ded3596a23311695e0717e2f282089480942c16a47d6233e873730`

This canary proves only the public schema and one excluded-date source path. It does not prove joint support across the
99 development dates, executable fills, profitability, or future reachability.
