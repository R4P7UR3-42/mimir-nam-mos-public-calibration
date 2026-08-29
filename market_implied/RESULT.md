# Terminal Result: Frozen Pagination-Capacity Rejection

- Decision: **REJECTED — no OOS, calibration, executable-fill, or profitability credit**
- Public run: [`33229217549`](https://github.com/R4P7UR3-42/mimir-nam-mos-public-calibration/actions/runs/33229217549)
- Run head: `35619dbe43a833240130e62d420ce8e7d4b55027`
- Frozen runner tag: `market-implied-public-runner-v3`
- Predeclaration SHA-256: `4ffe4303b7e93af8f58fe1b0c79aae44982222cf04b2e8e37b01c65956cd94e3`
- Run artifact `SHA256SUMS` SHA-256: `9b291d905d92ec411b5a26a4ba2ecd3736cecad900fa703ccd65a43a8c1aacc4`
- Terminal log SHA-256: `619abdc2dce482e03da95e9509f27a6cf7ca006cbb72355eecb8bd03566f2ef2`

The runner's nine frozen tests passed and the public hosted runner started normally. Training acquisition then stopped
after 93 bounded public requests while discovering `KXHIGHNY` markets. Two pages of 1,000 historical market rows did
not exhaust the provider cursor. The frozen predeclaration required a terminal empty cursor within two pages, so the
runner correctly raised:

```text
ValueError: Historical market pagination exceeded two pages for KXHIGHNY.
```

The immutable artifact contains the run manifest, the responses and headers acquired before the stop, and verified
portable checksums. It contains no `training.json` or `report.json` because the training phase did not complete.
No evaluation-series market, candle, trade, or result was requested, and no production system, credential, database,
recommendation, capital, cohort, or order capability was accessed or changed.

This is a frozen acquisition-capacity rejection, not evidence for or against the strategy's economics. The two-page
assumption was false for the provider's strike-level series history. The predeclaration made that bound an exact source
condition and made every source failure terminal. Therefore this family receives no OOS, calibration, fill, Brier,
reliability, EV, P&L, drawdown, concentration, capital, recommendation, readiness, cohort, or trading authority.
There will be no retry, pagination relaxation, threshold change, or reuse of the untouched evaluation split for this
family. Progress must move to a materially distinct, independently predeclared hypothesis.
