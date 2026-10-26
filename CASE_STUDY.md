# BTCUSDT order-flow pilot: what survived validation?

This is the first pilot. The subsequent [frozen later-session case study](FROZEN_CASE_STUDY.md)
evaluates the saved model on a separately captured recording without refitting.

## Research question

Can best-quote quantity imbalance, best-quote order-flow transitions and aggressive
trade flow improve forecasts of subsequent 1s/5s midprice returns? How do
aggressor-signed markouts describe adverse movement for passive counterparties?

## Data and design

A verified public Binance Spot capture recorded **144,788 events** over **598.86s**:
109,635 level-1 quote updates and 35,153 individual trades. The raw bytes, UTC and
monotonic receive clocks, connection IDs and input fingerprint are retained.

The model experiment was specified before inspecting these session outcomes.
Features use a regular 1s grid and trailing 1s windows; targets use the first quote
at/after each horizon. Three expanding chronological folds purge training labels
that overlap the next test boundary, with a further 1s embargo. Feature scaling is
fit on training data only. Seven baselines/feature sets use the same test rows;
ridge alpha=10 is fixed. The 1s/5s studies have 359/355 OOS observations respectively.

## Results

| Forecast | 1s RMSE (bps) | 5s RMSE (bps) |
|---|---:|---:|
| Zero return | 0.660875 | 1.604741 |
| Training mean | 0.661081 | 1.602290 |
| Imbalance alone | 0.656148 | 1.524201 |
| Combined features | 0.891946 | 1.533865 |

The combined feature set made 1s magnitude forecasts worse. Its lower 5s error was
also worse than imbalance alone. More features did not consistently help.
For the paired zero-baseline-minus-combined squared-error difference, the 30s-block
95% bootstrap intervals were **[-0.912878, 0.012464] bps²** at 1s and
**[-0.077718, 0.506208] bps²** at 5s. Both include zero. There are only twelve OOS
30-second blocks, so these are unstable exploratory intervals, not confirmatory tests.

At 1s, mean signed trade-conditioned markouts were 0.552807 bps after aggressive
buys and 0.617798 bps after aggressive sells. These measure subsequent midprice
movement relative to a prior midprice; they do not estimate order fills or P&L.
The full report includes side-specific block intervals and 5s markouts.

## The data-quality result matters

The collector reconnected three times, producing four recorded connections.
No features or labels are carried across known connection boundaries. Of 599 grid
observations, 496 had usable features, and 473/467 had usable 1s/5s labels.

Median trade receipt-minus-exchange-event time was 63.78ms, but its 99th percentile
was **19.47s**; 2,462 trades exceeded 1s and 1,067 exceeded 5s. These differences
mix clock offset, transport and application buffering. The long tail makes
exchange-time predictive interpretation especially weak. Parser validity was 100%
of persisted records, which does not establish stream completeness.

## Conclusion and next experiment

The pilot demonstrates a reproducible public-data research workflow and reveals
both model and transport weaknesses. It does not validate a durable forecasting edge.
The next experiment is independent later sessions on a stable transport, preserving
the fixed model/protocol and evaluating entire held-out sessions. Capture reliability
and time semantics take priority over adding a more complex model.

The full [study](reports/live-study/study.md) contains every model, the complete
sampling/freshness sweep, 10s/30s/60s block sensitivity and purge audit. Saved OOS
predictions allow independent error recomputation with the `audit` command.
