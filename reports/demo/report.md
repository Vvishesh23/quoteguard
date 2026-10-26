# QuoteGuard research report — SYNTHETIC

Source: `synthetic`. Input SHA-256: `9427fa285b477eddca230abcebcb178c1f39b12aec66e68b118bb8328a45da48`.

Recording window: 2026-01-01T00:00:00.000000000Z to 2026-01-01T00:01:59.920000000Z.
Raw records: 2400; valid: 2400 (100.00%); quotes: 1200; trades: 1200.
Trades with eligible prior quote: 1200; stale or unmatched: 0.

Maximum quote age: 1s. Maximum forward sampling delay: 0.5s.
Available forward labels: `{"quote_labels": {"1s": 1190, "5s": 1150}, "trade_labels": {"1s": 1189, "5s": 1149}}`.

## Spread distribution (bps)

| Percentile | Spread |
|---|---:|
| 0% | 0.099964 |
| 25% | 0.099981 |
| 50% | 0.099988 |
| 75% | 0.099999 |
| 95% | 0.100011 |
| 100% | 0.100019 |

## Imbalance buckets

| Bucket | Quotes | 1s count | 1s mean bps | 5s count | 5s mean bps |
|---|---:|---:|---:|---:|---:|
| [-1,-.6] | 134 | 134 | 0.041836 | 128 | 0.161570 |
| (-.6,-.2] | 321 | 320 | 0.038479 | 307 | 0.086573 |
| (-.2,.2] | 348 | 344 | 0.015860 | 334 | 0.162283 |
| (.2,.6] | 287 | 283 | 0.011277 | 276 | 0.105916 |
| (.6,1] | 110 | 109 | 0.058130 | 105 | 0.103327 |

## Trade-conditioned markouts

| Aggressor | Trades | 1s count | 1s mean bps | 5s count | 5s mean bps |
|---|---:|---:|---:|---:|---:|
| Sell | 599 | 592 | 0.001620 | 571 | -0.113376 |
| Buy | 601 | 597 | 0.061760 | 578 | 0.137952 |

![Research charts](research.png)

## Interpretation and limitations

Positive aggressor-signed markouts indicate adverse price movement for a hypothetical passive counterparty. These are trade-conditioned midprice markouts, without inferred fills, queue position, fees, inventory, or P&L.

Features use receive order and the last available quote, including file order to resolve equal timestamps. Forward labels use the first quote at or after receipt time plus the horizon, within tolerance. Unavailable labels remain missing; counts differ by horizon. Standard bookTicker has no comparable exchange event timestamp.

Receive clocks describe local arrival order, not exchange causality. Network delay, buffering, disconnects, clock adjustments and asynchronous streams limit sequencing accuracy. ID gaps are possible; level-1 data is not a synchronized full order book.

Each quote update receives equal weight; this is not a time-weighted estimate. Overlapping horizons and clustered trades make observations dependent. No statistical significance or predictive alpha is established; longer sessions, independent days, held-out evaluation and dependence-aware inference are needed.

Synthetic data is a reproducibility fixture with uncalibrated random price movements, never exchange evidence.

Rejected records: `{}`.
