# Terminal Result: Source-Schema Rejection

- Decision: **REJECTED — no calibration or profitability credit**
- Public run: [`33228343826`](https://github.com/R4P7UR3-42/mimir-nam-mos-public-calibration/actions/runs/33228343826)
- Run head: `bd4b52e17a8fe0a1ca259c8487969afed6c1a838`
- Frozen runner tag: `nam-mos-public-runner-v1`
- Predeclaration SHA-256: `d5e958578155c5b7ef3a2b2d59477b256cda5a936249abb4e1ca219cbd74b442`
- Run artifact `SHA256SUMS` SHA-256: `88abfa84f3049230fba86e1643b46d452b711953b949e49469781ec3cf19d4b7`
- Terminal log SHA-256: `981788978030bdc250b23f6b8b9ac3a1533ccd2ef39f9466b0eed18748dc3233`

The runner's 13 frozen tests passed. Acquisition then stopped on the ninth and final performed network request, before
NOAA outcomes, historical market prices, fees, or production state were accessed. The first eight station responses
shared an exact CSV schema containing the optional `snw` field. The ninth response, for `KLAX`, omitted `snw` while
retaining the selected `n_x` field. The frozen capture correctly raised:

```text
ValueError: IEM MOS bulk schemas conflict at KLAX.
```

The immutable artifact contains the nine raw response bodies, response headers, run manifest, and verified portable
checksums. The `KATL` and `KLAX` header identities that prove the terminal conflict are:

```text
KATL: runtime,ftime,model,n_x,tmp,dpt,cld,wdr,wsp,p06,p12,q06,q12,t06_1,t06_2,t12_2,snw,cig,vis,obv,poz,pos,typ,station,t06
KLAX: runtime,ftime,model,n_x,tmp,dpt,cld,wdr,wsp,p06,p12,q06,q12,t06_1,t06_2,t12_2,cig,vis,obv,poz,pos,typ,station,t06
```

This contradicts the source-canary assumption that the complete station schemas agreed. The predeclaration explicitly
made schema agreement a pass condition, so the family receives no outcome, calibration, executable-price, EV,
recommendation, cohort, readiness, capital, or order authority. There will be no retry, parser relaxation, threshold
change, or reuse of these dates for this family. Progress must move to a materially distinct predeclared hypothesis.
