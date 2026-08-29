# Forecast-Only Source Canary

- Captured: 2026-08-29 UTC
- Source: Iowa Environmental Mesonet archive of NOAA NAM MOS
- Model: `NAM`, exact prior-calendar-day `12:00Z` runtime
- Candidate window: 2021-02-15 through 2022-03-16
- Inventory: the exact 20 stations in `stations.json`
- Requests: exactly 20 successful station-bulk requests
- Outcome, market, price, fee, and production access: none

The canary found all 7,900 required station/date maximum-temperature rows. Each station response contained exactly one
additional selected row at the same source identity. For every station that duplicate was identical across every
semantic source field and value; the archive row index alone differed. There were no conflicting duplicates, missing
rows, null selected maxima, wrong runtimes, or wrong forecast times. The frozen parser may collapse only completely
identical selected rows and must reject any conflicting duplicate.

| Station | Selected rows | Exact duplicates | Missing | Raw SHA-256 |
| --- | ---: | ---: | ---: | --- |
| KATL | 395 | 1 | 0 | `dbb77a0243629cfdd06aa85866b666fb297a6bca4380a995b5df887e8c910a1e` |
| KAUS | 395 | 1 | 0 | `0bc4632c74c191d07d9d259fc8e3ef578bfe1998d15787240a131b30edd97d12` |
| KBOS | 395 | 1 | 0 | `0fc876b0e9f9051f21d142176a088828275d825b839204b306122d15fb6d84b2` |
| KDCA | 395 | 1 | 0 | `875ef6a9301d45b279740bb2b45437aa482df3051f217de850fef12c7c1a09d8` |
| KDEN | 395 | 1 | 0 | `b0d9d03b3b425f2fa38255cce87225f07562d8fc7bad42d57e6ef89c58e5b2d1` |
| KDFW | 395 | 1 | 0 | `7cde7b4c381e0cef52cbf71e01f2d772706f995616b65424ab8d3a71e70e07c4` |
| KHOU | 395 | 1 | 0 | `7a869c256a87468ee8679831f0cb6c83272d827146b8cdcaec97517264d6200d` |
| KLAS | 395 | 1 | 0 | `b3d43a5d6bcfc8cda6735aeda134ae89b2791fb2e0e2e144deea3dbc8164c926` |
| KLAX | 395 | 1 | 0 | `249a57c7b55adab22431cc00e6b72bc5a87f9e880f0d87a308615082fea9f043` |
| KMDW | 395 | 1 | 0 | `346d8d0e63c02d2876fe13aa25a255aac090731449fc35b64511e41cfb3c807f` |
| KMIA | 395 | 1 | 0 | `61162c032302309fc58183ad50e701820d9872acc485e5646acade4951db950e` |
| KMSP | 395 | 1 | 0 | `8e5eb1efbc645768a1428a38329627734c5dfd0820de41e7ce717607f015d0ce` |
| KMSY | 395 | 1 | 0 | `e343a445561aaebb929bd93c90bed3887fe55a4054238e81fe125f85d54970e3` |
| KNYC | 395 | 1 | 0 | `07350c6ec6bb0debd4482def5644f49e97ade99cea327efd9d070fa847f6e72c` |
| KOKC | 395 | 1 | 0 | `3ae9603158daa0f794ec94add4888efab7db7ab72fcec91c37190463031665ca` |
| KPHL | 395 | 1 | 0 | `605674264c6640c7d1ca5e4aa2f95275a82b740de02ebfec27bd6752eba35a11` |
| KPHX | 395 | 1 | 0 | `4d52a34add4b79efc1f9f95cf81d11039c28ee62f115aa382462efbacdfb75dd` |
| KSAT | 395 | 1 | 0 | `e9cea57562dfeae3fa01342e35b9e97162b63db0e8166a398b5dcd99036b395c` |
| KSEA | 395 | 1 | 0 | `8b7d6665f040be81ee54ab198698aa1c34e3965382cb589f0fdbe23e56f5afb1` |
| KSFO | 395 | 1 | 0 | `c71f493fb43d562ce0485637de7b779b835b2ca12401d1bfc62fdb7e5c5bfc7e` |

An earlier source-only feasibility scan over 2024-01-01 through 2025-01-29 also had complete 7,900-row coverage, but
those dates overlap outcomes already inspected by other Mimir families and receive no evaluation credit here.
