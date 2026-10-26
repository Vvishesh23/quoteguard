# Frozen later-session validation protocol

This extension is fixed before inspecting the new session's outcomes.

- Train on the previously captured BTCUSDT pilot only, with the existing 1s grid,
  1s trailing windows, 1s quote age, .5s target tolerance and ridge alpha=10.
- Serialize all training means/scales, coefficients, intercepts, training-mean
  baselines, source/symbol, input hash and last training receipt time in plain JSON.
- Freeze and fingerprint the artifact before starting the new capture. No held-out
  rows or labels may refit or normalize the model. Evaluate all seven comparisons.
- Require the new capture to start strictly after the training recording ends plus
  a 1s embargo. Reject overlap, source mismatch, symbol mismatch and model corruption.
- Record a bounded ten-minute later session with the same public streams. This is
  a later session on the same day, not an independent-day validation.
- Use the original complete eligible-row protocol as the primary comparison;
  do not tune parameters or select a winning model on held-out outcomes.
- Report RMSE/MAE, 30s paired-block intervals, sample coverage and train-to-test
  feature drift measured in frozen training-standard-deviation units.
- Report an observable-at-receipt feature-quality sensitivity: exclude a snapshot
  if a trade received in its preceding 1s window differs from its exchange event
  timestamp by more than 1s, or by less than -100ms. These are clock/delivery flags,
  not calibrated latency measurements. Apply the same frozen model, without refit.
- Declare the capture transport quality unsuitable for strong timing inference if
  p99 receipt-minus-event gap exceeds 1s, or fewer than 80% of regular snapshots
  pass the observable feature-quality mask. This gate never suppresses raw outputs
  and is not a test-time parameter search.
- Report 10s/30s/60s block sensitivity. Pointwise intervals remain exploratory;
  no multiple-testing correction, production execution or profitability inference.

All results, including worse-than-baseline forecasts and failed quality gates,
remain in the report. Transport health and model generalization are distinct questions.
