# QuoteGuard frozen later-session evaluation — BINANCE PUBLIC CAPTURE

Model artifact: `e75939fd3dedbbd1b0029b4a84f8f1febb57138ee708d3cde5a007bb1d8ac91e`.
Training input SHA-256: `190c6cd8887d9a2cf3169039f7ab2bdee4de0831a70fe420407320a1b9a42089`.
Test input SHA-256: `2376c64cac7d0241e41216247eb65cad7cf4eed64c8fd294a33c0e4e6b42dd58`.

New capture: 2026-10-26T17:42:06.122438000Z to 2026-10-26T17:52:05.307209000Z (599.18s), 60,582 raw records; 45,495 quotes and 15,087 trades.
The new recording starts 7963.65s after the training recording ends.

## Frozen protocol and findings

Every model coefficient, feature mean/scale and training-mean baseline was fixed in a fingerprinted JSON artifact before this capture. There is no test-session refit, normalization or parameter selection. Source, symbol and strict temporal separation are validated. The quality thresholds were fixed in SESSION_PROTOCOL.md before inspecting these outcomes.

- 1s: combined RMSE 0.269235 bps; zero baseline 0.260491 bps; imbalance-only 0.278802 bps. Nonflat targets: 90/597; directional accuracy is conditional on those nonflat targets.
- 5s: combined RMSE 0.738618 bps; zero baseline 0.716083 bps; imbalance-only 0.704549 bps. Nonflat targets: 277/593; directional accuracy is conditional on those nonflat targets.

**Transport timing gate: PASS.** The gate checks trade receipt-gap p99 <=1s and at least 80% of grid snapshots without a flagged trade in their previous 1s window. Passing does not establish synchronized clocks or exchange-time quote sequencing. Failing weakens timing inference; it does not hide or replace the primary results.

This is a separate later recording on the same day. It does not establish independent-day or regime robustness.

## Forecast metrics

| scope | horizon_s | model | n | nonflat_targets | rmse_bps | mae_bps | correlation | nonflat_directional_accuracy |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| all_eligible | 1 | book | 597 | 90 | 0.265794 | 0.183949 | 0.331422 | 0.933333 |
| all_eligible | 1 | combined | 597 | 90 | 0.269235 | 0.187854 | 0.330872 | 0.933333 |
| all_eligible | 1 | imbalance | 597 | 90 | 0.278802 | 0.206965 | 0.314126 | 0.933333 |
| all_eligible | 1 | lag_persistence | 597 | 90 | 0.333699 | 0.111468 | 0.17462 | 0.311111 |
| all_eligible | 1 | trade | 597 | 90 | 0.254327 | 0.113124 | 0.22995 | 0.7 |
| all_eligible | 1 | train_mean | 597 | 90 | 0.259974 | 0.0945665 | NA | 0.633333 |
| all_eligible | 1 | zero | 597 | 90 | 0.260491 | 0.0694815 | NA | 0 |
| all_eligible | 5 | book | 593 | 277 | 0.726876 | 0.559693 | 0.363189 | 0.873646 |
| all_eligible | 5 | combined | 593 | 277 | 0.738618 | 0.561558 | 0.345796 | 0.877256 |
| all_eligible | 5 | imbalance | 593 | 277 | 0.704549 | 0.525391 | 0.372702 | 0.873646 |
| all_eligible | 5 | lag_persistence | 593 | 277 | 0.718243 | 0.352414 | 0.165929 | 0.187726 |
| all_eligible | 5 | trade | 593 | 277 | 0.702187 | 0.424799 | 0.185228 | 0.649819 |
| all_eligible | 5 | train_mean | 593 | 277 | 0.709376 | 0.399032 | NA | 0.588448 |
| all_eligible | 5 | zero | 593 | 277 | 0.716083 | 0.341229 | NA | 0 |
| feature_quality_subset | 1 | book | 597 | 90 | 0.265794 | 0.183949 | 0.331422 | 0.933333 |
| feature_quality_subset | 1 | combined | 597 | 90 | 0.269235 | 0.187854 | 0.330872 | 0.933333 |
| feature_quality_subset | 1 | imbalance | 597 | 90 | 0.278802 | 0.206965 | 0.314126 | 0.933333 |
| feature_quality_subset | 1 | lag_persistence | 597 | 90 | 0.333699 | 0.111468 | 0.17462 | 0.311111 |
| feature_quality_subset | 1 | trade | 597 | 90 | 0.254327 | 0.113124 | 0.22995 | 0.7 |
| feature_quality_subset | 1 | train_mean | 597 | 90 | 0.259974 | 0.0945665 | NA | 0.633333 |
| feature_quality_subset | 1 | zero | 597 | 90 | 0.260491 | 0.0694815 | NA | 0 |
| feature_quality_subset | 5 | book | 593 | 277 | 0.726876 | 0.559693 | 0.363189 | 0.873646 |
| feature_quality_subset | 5 | combined | 593 | 277 | 0.738618 | 0.561558 | 0.345796 | 0.877256 |
| feature_quality_subset | 5 | imbalance | 593 | 277 | 0.704549 | 0.525391 | 0.372702 | 0.873646 |
| feature_quality_subset | 5 | lag_persistence | 593 | 277 | 0.718243 | 0.352414 | 0.165929 | 0.187726 |
| feature_quality_subset | 5 | trade | 593 | 277 | 0.702187 | 0.424799 | 0.185228 | 0.649819 |
| feature_quality_subset | 5 | train_mean | 593 | 277 | 0.709376 | 0.399032 | NA | 0.588448 |
| feature_quality_subset | 5 | zero | 593 | 277 | 0.716083 | 0.341229 | NA | 0 |

No grid windows were flagged by the feature-quality rule in this recording, so the primary and feature-quality subset metrics are identical.

The feature-quality subset uses only receipt-time information: in the preceding 1s, no received trade may have receipt-minus-event time >1s or <-100ms. No model is refit. Subset and primary metrics have different samples, so differences are not a controlled forecast-improvement comparison. Quote exchange timestamps remain unavailable.

## Paired time-block intervals

| scope | horizon_s | comparison | mean | ci_low | ci_high | blocks | status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| all_eligible | 1 | zero_minus_combined_squared_error | -0.00463218 | -0.016119 | 0.00885448 | 20 | exploratory |
| all_eligible | 1 | train_mean_minus_combined_squared_error | -0.00490121 | -0.0157214 | 0.00767321 | 20 | exploratory |
| all_eligible | 1 | imbalance_minus_combined_squared_error | 0.00524292 | 0.00257032 | 0.00796521 | 20 | exploratory |
| all_eligible | 5 | zero_minus_combined_squared_error | -0.0327806 | -0.133088 | 0.0722078 | 20 | exploratory |
| all_eligible | 5 | train_mean_minus_combined_squared_error | -0.042342 | -0.139002 | 0.0608922 | 20 | exploratory |
| all_eligible | 5 | imbalance_minus_combined_squared_error | -0.0491662 | -0.0773078 | -0.0226542 | 20 | exploratory |
| feature_quality_subset | 1 | zero_minus_combined_squared_error | -0.00463218 | -0.016119 | 0.00885448 | 20 | exploratory |
| feature_quality_subset | 1 | train_mean_minus_combined_squared_error | -0.00490121 | -0.0157214 | 0.00767321 | 20 | exploratory |
| feature_quality_subset | 1 | imbalance_minus_combined_squared_error | 0.00524292 | 0.00257032 | 0.00796521 | 20 | exploratory |
| feature_quality_subset | 5 | zero_minus_combined_squared_error | -0.0327806 | -0.133088 | 0.0722078 | 20 | exploratory |
| feature_quality_subset | 5 | train_mean_minus_combined_squared_error | -0.042342 | -0.139002 | 0.0608922 | 20 | exploratory |
| feature_quality_subset | 5 | imbalance_minus_combined_squared_error | -0.0491662 | -0.0773078 | -0.0226542 | 20 | exploratory |

Positive paired error differences favor the combined model. Primary 30s blocks, 1,000 resamples, seed 17; 10s/60s alternatives are in block_sensitivity.csv. Few blocks and multiple comparisons make these pointwise intervals exploratory.

## Train-to-test feature drift

| horizon_s | feature | mean_in_train_std | test_std_in_train_std | fraction_abs_z_above_3 | flag_mean_shift |
| --- | --- | --- | --- | --- | --- |
| 1 | imbalance | 0.0928777 | 0.944776 | 0 | False |
| 1 | microprice_edge_bps | 0.0723307 | 0.266153 | 0.00167504 | False |
| 1 | spread_bps | -0.0555907 | 0.196035 | 0.00167504 | False |
| 1 | ofi_depth | 0.0548031 | 0.355312 | 0.00167504 | False |
| 1 | trade_flow_imbalance | 0.212086 | 0.895842 | 0 | False |
| 1 | log_trade_count | -0.801188 | 0.813903 | 0 | False |
| 1 | lag_return_bps | 0.0189187 | 0.367465 | 0.00167504 | False |
| 5 | imbalance | 0.111626 | 0.942216 | 0 | False |
| 5 | microprice_edge_bps | 0.0793612 | 0.13968 | 0 | False |
| 5 | spread_bps | -0.0686879 | 0.101042 | 0 | False |
| 5 | ofi_depth | 0.0431042 | 0.347485 | 0.00168634 | False |
| 5 | trade_flow_imbalance | 0.222313 | 0.891449 | 0 | False |
| 5 | log_trade_count | -0.823281 | 0.825212 | 0 | False |
| 5 | lag_return_bps | 0.0120853 | 0.368083 | 0.00168634 | False |

Drift uses the combined model's frozen training mean and scale. A mean shift above one training standard deviation is flagged descriptively. Constant training columns use the model's unit-scale fallback, so those ratios require care. Drift is not proof of cause.

![Frozen-session research](holdout.png)

## Quality and provenance

Training transport: `{"gap_median_ms": 63.782, "gap_p99_ms": 19470.75848000018, "scope": "observable trailing features only; no quote exchange timestamps exist", "snapshot_quality_fraction": 0.9165275459098498, "thresholds": {"max_p99_ms": 1000, "max_trade_gap_ms": 1000, "min_snapshot_fraction": 0.8, "min_trade_gap_ms": -100}, "timing_gate_passed": false, "trade_count": 35153, "trades_above_1s": 2462, "trades_below_minus_100ms": 0}`.
Test transport: `{"gap_median_ms": 16.14, "gap_p99_ms": 560.76238, "scope": "observable trailing features only; no quote exchange timestamps exist", "snapshot_quality_fraction": 1.0, "thresholds": {"max_p99_ms": 1000, "max_trade_gap_ms": 1000, "min_snapshot_fraction": 0.8, "min_trade_gap_ms": -100}, "timing_gate_passed": true, "trade_count": 15087, "trades_above_1s": 0, "trades_below_minus_100ms": 0}`.
Grid coverage: `{"eligible_features": 598, "grid_observations": 599, "interval_s": 1, "labeled_1s": 597, "labeled_5s": 593, "lookback_s": 1, "stale_s": 1, "tolerance_s": 0.5}`.

Receipt gaps mix clock offset, timestamp semantics, transport buffering and application scheduling. The collector reports event-loop and disk-write telemetry when available, without treating it as a latency benchmark. Raw captures retain reconnect boundaries.

Model IDs detect accidental changes, not malicious tampering or venue authenticity. No order fills, queue position, trading P&L, fees or profitable strategy are inferred. Next validation requires independent later days and stable timestamp/transport behavior.

## Recorder telemetry

| Measurement | Value |
|---|---:|
| Event-loop timer samples | 5924 |
| Maximum observed timer scheduling lag (ms) | 16.895208 |
| Timer observations above 100ms | 0 |
| Raw record writes | 60582 |
| Mean serialization/write duration (ms) | 0.060163 |
| Maximum serialization/write duration (ms) | 12.961417 |

These are measurements from this recorder/run, not portable throughput or venue-latency benchmarks.
