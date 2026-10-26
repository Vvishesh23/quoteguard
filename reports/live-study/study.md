# QuoteGuard — chronological research study (BINANCE PUBLIC CAPTURE)

Symbol: **BTCUSDT**. Source: `binance_public`. Input SHA-256: `190c6cd8887d9a2cf3169039f7ab2bdee4de0831a70fe420407320a1b9a42089`.

UTC window: 2026-10-26T15:19:23.615103000Z to 2026-10-26T15:29:22.474981000Z (598.86s). Valid records: 144,788/144,788; quotes: 109,635; trades: 35,153.

## Findings

- At 1s, the combined model's OOS RMSE was 0.891946 bps versus 0.660875 bps for zero return (higher error). This is a single-session comparison, not evidence of durable predictability.
- At 5s, the combined model's OOS RMSE was 1.533865 bps versus 1.604741 bps for zero return (lower error). This is a single-session comparison, not evidence of durable predictability.
- 6 of 6 paired forecast-improvement intervals include zero; the reported comparisons are exploratory and provide no confirmatory improvement claim.
- Delivery/clock quality is a material limitation: the 99th-percentile trade receipt-minus-exchange-event difference is 19.47s. Features and labels describe local arrival order; apparent relationships cannot be interpreted as exchange-time predictability.

The model penalty, feature sets, split fractions and sensitivity grid were fixed in RESEARCH_PROTOCOL.md before inspecting the session outcomes. No best-performing sensitivity configuration was substituted for the baseline protocol.

## Method

Regular 1s receive-time grid; last available quote <=1s old. Past 1s best-quote OFI, signed aggressive volume, count, quantity imbalance, microprice edge, spread and lagged return. Future targets select the first quote at/after 1s or 5s, at most .5s late. Known reconnect boundaries invalidate carried features and targets.

Three expanding chronological folds train on the initial 40%, 60%, and 80% of the timeline. Each tests the following 20%. Training labels must be realized strictly before test start minus a 1s embargo. Means/scales and ridge coefficients use training rows only. Alpha=10 is fixed; no shuffled split, test-time fitting or hyperparameter search is used.

## Out-of-sample metrics

| horizon_s | model | n | rmse_bps | mae_bps | correlation | nonflat_directional_accuracy |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | book | 359 | 0.97612 | 0.433901 | 0.259452 | 0.834711 |
| 1 | combined | 359 | 0.891946 | 0.427814 | 0.270569 | 0.834711 |
| 1 | imbalance | 359 | 0.656148 | 0.402413 | 0.275939 | 0.834711 |
| 1 | lag_persistence | 359 | 0.879561 | 0.396766 | 0.113317 | 0.38843 |
| 1 | trade | 359 | 0.66148 | 0.298221 | 0.0849323 | 0.661157 |
| 1 | train_mean | 359 | 0.661081 | 0.27038 | -0.0206786 | 0.595041 |
| 1 | zero | 359 | 0.660875 | 0.248138 | NA | 0 |
| 5 | book | 355 | 1.53319 | 1.05812 | 0.319358 | 0.734043 |
| 5 | combined | 355 | 1.53386 | 1.06314 | 0.322705 | 0.716312 |
| 5 | imbalance | 355 | 1.5242 | 1.02622 | 0.316686 | 0.741135 |
| 5 | lag_persistence | 355 | 1.74886 | 1.07558 | -0.0224239 | 0.248227 |
| 5 | trade | 355 | 1.61707 | 1.04652 | -0.0562946 | 0.464539 |
| 5 | train_mean | 355 | 1.60229 | 1.02771 | -0.0586513 | 0.570922 |
| 5 | zero | 355 | 1.60474 | 1.01969 | NA | 0 |

Directional accuracy excludes flat targets; neutral predictions count as incorrect. Models are compared on the same eligible rows per horizon. These are return forecasts, without spreads, fees, inventory or execution assumptions.

## Paired error comparison

Positive values mean the combined model has lower squared error than the named baseline. Intervals use 1,000 bootstrap resamples of 30s time blocks. Intervals are suppressed below 8 blocks, and fewer than 20 blocks are flagged as especially unstable.

| horizon_s | comparison | mean | ci_low | ci_high | blocks | status |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | zero_minus_combined_squared_error | -0.358813 | -0.912878 | 0.0124637 | 12 | few_blocks_exploratory |
| 1 | train_mean_minus_combined_squared_error | -0.35854 | -0.913961 | 0.0147899 | 12 | few_blocks_exploratory |
| 1 | imbalance_minus_combined_squared_error | -0.365038 | -0.925203 | 0.0107691 | 12 | few_blocks_exploratory |
| 5 | zero_minus_combined_squared_error | 0.222453 | -0.0777181 | 0.506208 | 12 | few_blocks_exploratory |
| 5 | train_mean_minus_combined_squared_error | 0.214591 | -0.079053 | 0.504196 | 12 | few_blocks_exploratory |
| 5 | imbalance_minus_combined_squared_error | -0.0295531 | -0.115185 | 0.0554774 | 12 | few_blocks_exploratory |

Block-length sensitivity (same paired errors; headline block length remains 30s):

| horizon_s | comparison | block_s | mean | ci_low | ci_high | blocks | status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | zero_minus_combined_squared_error | 10 | -0.358813 | -0.908248 | 0.0192815 | 36 | exploratory |
| 1 | train_mean_minus_combined_squared_error | 10 | -0.35854 | -0.91106 | 0.0214541 | 36 | exploratory |
| 1 | imbalance_minus_combined_squared_error | 10 | -0.365038 | -0.929789 | 0.0115402 | 36 | exploratory |
| 5 | zero_minus_combined_squared_error | 10 | 0.222453 | -0.153768 | 0.616632 | 36 | exploratory |
| 5 | train_mean_minus_combined_squared_error | 10 | 0.214591 | -0.165345 | 0.603015 | 36 | exploratory |
| 5 | imbalance_minus_combined_squared_error | 10 | -0.0295531 | -0.122223 | 0.0872084 | 36 | exploratory |
| 1 | zero_minus_combined_squared_error | 30 | -0.358813 | -0.912878 | 0.0124637 | 12 | few_blocks_exploratory |
| 1 | train_mean_minus_combined_squared_error | 30 | -0.35854 | -0.913961 | 0.0147899 | 12 | few_blocks_exploratory |
| 1 | imbalance_minus_combined_squared_error | 30 | -0.365038 | -0.925203 | 0.0107691 | 12 | few_blocks_exploratory |
| 5 | zero_minus_combined_squared_error | 30 | 0.222453 | -0.0777181 | 0.506208 | 12 | few_blocks_exploratory |
| 5 | train_mean_minus_combined_squared_error | 30 | 0.214591 | -0.079053 | 0.504196 | 12 | few_blocks_exploratory |
| 5 | imbalance_minus_combined_squared_error | 30 | -0.0295531 | -0.115185 | 0.0554774 | 12 | few_blocks_exploratory |
| 1 | zero_minus_combined_squared_error | 60 | -0.358813 | NA | NA | 6 | insufficient_blocks |
| 1 | train_mean_minus_combined_squared_error | 60 | -0.35854 | NA | NA | 6 | insufficient_blocks |
| 1 | imbalance_minus_combined_squared_error | 60 | -0.365038 | NA | NA | 6 | insufficient_blocks |
| 5 | zero_minus_combined_squared_error | 60 | 0.222453 | NA | NA | 6 | insufficient_blocks |
| 5 | train_mean_minus_combined_squared_error | 60 | 0.214591 | NA | NA | 6 | insufficient_blocks |
| 5 | imbalance_minus_combined_squared_error | 60 | -0.0295531 | NA | NA | 6 | insufficient_blocks |

## Trade-conditioned markouts

Positive signed markouts are adverse midprice movement for a hypothetical passive counterparty. Buy/sell means use event weighting; the resampling unit is a time block, not an individual trade.

| side | horizon_s | n | mean | ci_low | ci_high | blocks | status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| sell | 1 | 17321 | 0.617798 | 0.373068 | 0.793046 | 19 | few_blocks_exploratory |
| sell | 5 | 17124 | 0.663714 | -0.0948904 | 1.19944 | 19 | few_blocks_exploratory |
| buy | 1 | 16522 | 0.552807 | 0.312656 | 0.811154 | 20 | exploratory |
| buy | 5 | 16142 | 0.584284 | -0.0779441 | 1.13435 | 20 | exploratory |

![Research study](study.png)

## Purge audit

| horizon_s | fold | train_rows | test_rows | purged_rows | status |
| --- | --- | --- | --- | --- | --- |
| 1 | 1 | 112 | 120 | 2 | ok |
| 1 | 2 | 232 | 120 | 2 | ok |
| 1 | 3 | 352 | 119 | 2 | ok |
| 5 | 1 | 106 | 120 | 6 | ok |
| 5 | 2 | 226 | 120 | 6 | ok |
| 5 | 3 | 346 | 115 | 6 | ok |

Exact nanosecond cutoff and latest training-label timestamps are in splits.csv; train-only scaling and model coefficients are in coefficients.csv. OOS predictions retain timestamps and folds for independent error recomputation.

## Sensitivity grid

| interval_s | stale_s | tolerance_s | horizon_s | model | n | rmse_bps |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 0.25 | 0.1 | 1 | combined | 311 | 0.832135 |
| 1 | 0.25 | 0.1 | 1 | zero | 311 | 0.68034 |
| 1 | 0.25 | 0.1 | 5 | combined | 308 | 4021.72 |
| 1 | 0.25 | 0.1 | 5 | zero | 308 | 1.63172 |
| 1 | 0.25 | 0.5 | 1 | combined | 353 | 0.874238 |
| 1 | 0.25 | 0.5 | 1 | zero | 353 | 0.661229 |
| 1 | 0.25 | 0.5 | 5 | combined | 349 | 1.55507 |
| 1 | 0.25 | 0.5 | 5 | zero | 349 | 1.60529 |
| 1 | 1 | 0.1 | 1 | combined | 316 | 0.841624 |
| 1 | 1 | 0.1 | 1 | zero | 316 | 0.680668 |
| 1 | 1 | 0.1 | 5 | combined | 314 | 4332.1 |
| 1 | 1 | 0.1 | 5 | zero | 314 | 1.63061 |
| 1 | 1 | 0.5 | 1 | combined | 359 | 0.891946 |
| 1 | 1 | 0.5 | 1 | zero | 359 | 0.660875 |
| 1 | 1 | 0.5 | 5 | combined | 355 | 1.53386 |
| 1 | 1 | 0.5 | 5 | zero | 355 | 1.60474 |
| 2 | 0.25 | 0.1 | 1 | combined | 159 | 1016.13 |
| 2 | 0.25 | 0.1 | 1 | zero | 159 | 0.568052 |
| 2 | 0.25 | 0.1 | 5 | combined | 156 | 5749.71 |
| 2 | 0.25 | 0.1 | 5 | zero | 156 | 1.61924 |
| 2 | 0.25 | 0.5 | 1 | combined | 176 | 1401.72 |
| 2 | 0.25 | 0.5 | 1 | zero | 176 | 0.590981 |
| 2 | 0.25 | 0.5 | 5 | combined | 174 | 1.50356 |
| 2 | 0.25 | 0.5 | 5 | zero | 174 | 1.5953 |
| 2 | 1 | 0.1 | 1 | combined | 161 | 987.911 |
| 2 | 1 | 0.1 | 1 | zero | 161 | 0.570272 |
| 2 | 1 | 0.1 | 5 | combined | 159 | 6273.92 |
| 2 | 1 | 0.1 | 5 | zero | 159 | 1.62196 |
| 2 | 1 | 0.5 | 1 | combined | 179 | 1295.4 |
| 2 | 1 | 0.5 | 1 | zero | 179 | 0.591002 |
| 2 | 1 | 0.5 | 5 | combined | 177 | 1.50043 |
| 2 | 1 | 0.5 | 5 | zero | 177 | 1.59818 |

## Data quality and limits

Sampling coverage: `{"eligible_features": 496, "grid_observations": 599, "interval_s": 1, "labeled_1s": 473, "labeled_5s": 467, "lookback_s": 1, "stale_s": 1, "tolerance_s": 0.5}`.
Quote interarrival gaps (ms): `{"maximum": 9326.444, "median": 0.046, "p99": 92.59075999999995}`.
Receipt-gap diagnostic counts: `{"above_1s": 2462, "above_5s": 1067, "negative": 0}`.
Receipt minus exchange-event time (ms): `{"median": 63.781982421875, "p99": 19470.75851562518}`.

Receipt-minus-exchange differences combine clock offset, venue timestamp semantics, transport and application scheduling; they are not calibrated latency benchmarks. Quote receipt times do not reveal exchange quote event times. Rejected-record counts describe parser validity, not proof that no messages were lost upstream.

Regular sampling reduces update-intensity weighting but does not make observations independent. Overlapping targets, repeated quotes, clustered activity and shared training histories remain. The block bootstrap assumes blocks capture enough short-range dependence; a single session has few blocks and no independent-day replication. Intervals are pointwise, unadjusted for multiple comparisons, and must not be treated as confirmatory significance tests.

Next validation: independent sessions/days, held-out sessions, longer block-length sensitivity, venue/clock diagnostics and stability under changing market regimes. There is no strategy backtest, maker-fill model, queue position, P&L or profitability claim.
