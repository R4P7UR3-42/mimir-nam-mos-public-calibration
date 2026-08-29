# Terminal Offered-Tail V3 Parser Result

- Identity: `noaa_nbm_v5_station_robust_offered_tail_no_split_development_v3`
- Frozen commit: `9e4341c227754032f3a9a557904cf70b561c102e`
- Annotated tag: `noaa-nbm-tail-development-v3`
- Sole run: `33233636192`, attempt 1, success
- Evaluation SHA-256: `e7aa697961c43f4a037eadd37cb723b53e53e4beb441883328e867c3c84b3f60`
- Portable artifact `SHA256SUMS` SHA-256: `8d9a7ba70b570d0ccf3d7190e31c497b33f871f22e75f9927d86c9abc1f85344`
- Workflow log SHA-256: `bb774f50f45e2e71cc22c54d939aa7e078980218e55273247b04b766db29713a`

V3 completed and reconciled exactly the known singleton NCEI conflict. It found 1,172 training-qualified offered tails
and 449 nonempty candles, but the inherited parser read only legacy `yes_bid.close`. Exactly 12 archived candles use
that field; 437 current candles use only `yes_bid.close_dollars`; none contain both. V3 therefore reported only 12
prices, one eligible row, and zero fills. Those economics are a parser artifact and cannot evaluate the strategy.

An order-free replay of only the exact schema normalization over sealed v3 evidence found 432 nonboundary displayed
bids and 62 eligible rows across 34 dates and 19 stations. V3 is terminal. A successor may parse exactly one of the two
documented close fields while preserving every model, selection, economic, evidence, and authority rule.
