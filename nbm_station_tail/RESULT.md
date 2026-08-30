# NBM station-specific offered-tail development result

- Decision: **rejected before independent OOS**
- Public run: [`33289346051`](https://github.com/R4P7UR3-42/mimir-nam-mos-public-calibration/actions/runs/33289346051)
- Exact main: `5f0c13d3ad883327bef40e80cf22a779c55d9417`
- Predeclaration SHA-256: `a97b2d3572ccce5df1b03d82537836104001ac7949cc1436e7fc825fe95cfb0c`
- Report SHA-256: `88829e9cfb1094237f1028bc3e03bb01e577d351b78bfee3fa61a12c58ea00bc`
- Portable manifest SHA-256: `cb76a38c150e0ba291b4155d6cc557252cf8b4eb5cc3f06a19302205ef755a6d`
- Artifact zip SHA-256: `2d4b4620643d740b451fb0d19f4c8342eedd53316534750ffd407e365a80c294`

The exact-main job passed all identity and test gates, completed 984 bounded public requests without a terminal source
failure, and checksum-sealed 2,955 artifact files. It reconciled the exact known singleton provider/NCEI outcome
conflict and did not access production, credentials, capital, recommendations, orders, or independent OOS dates.

The station Wilson correction reduced the pooled predecessor's 35 selections to 14 dates across eight stations. It
found 19 eligible displayed quotes and five qualifying public taker trades. Ten of 14 selected outcomes won, but the
mean conservative score was `0.93671429` against observed success `0.71428571`, leaving reliability error
`0.22242857` and displayed-price Brier skill `-0.22926199`.

Exact-fee realized P&L was `-$1.2836`, maximum drawdown was `$1.4806`, and the one-sided date-clustered 90% lower mean
submission return was `-$0.20327857`. Maximum station share was `0.35714286`; every represented leave-one-station-out
lower return was negative. Only the drawdown and one-selection-per-date gates passed. Sample, station coverage,
reliability, Brier skill, fill count, realized P&L, clustered return, holdout, and concentration gates failed.

This identity is terminal. Do not open an OOS window, loosen the station score, select stations or offsets post hoc,
change the clock/price/edge/fill rules, or use these dates as independent evidence. It creates no cohort, capital,
recommendation, production activation, order authority, profit projection, or profitability claim.
