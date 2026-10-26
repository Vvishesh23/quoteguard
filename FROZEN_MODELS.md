# Frozen models and later-session evaluation

The original `study` command expands and refits training folds inside one recording.
The `fit`/`holdout` workflow adds an explicit boundary between training and a later
recording. No held-out observation or label can update the saved model.

```sh
python -m quoteguard fit --input data/btcusdt-research-01.jsonl --out models/pilot-frozen.json
python -m quoteguard holdout --model models/pilot-frozen.json --input data/btcusdt-research-02.jsonl --out reports/frozen-holdout
python -m quoteguard audit --model models/pilot-frozen.json --input data/btcusdt-research-02.jsonl --report reports/frozen-holdout --out reports/frozen-holdout/audit.json
```

The provided training artifact already exists; exclusive creation prevents accidental
replacement. Use a new filename to fit another model. To reproduce its training
state, fit the same input with unchanged parameters into a new artifact and inspect
the saved numerical state. The software-version field may differ across releases.

## A fully offline demonstration

```sh
python -m quoteguard session-demo --out reports/session-demo
```

This generates two explicitly **SYNTHETIC** recordings with separate timestamps,
trains on the first, freezes JSON state, evaluates the second without fitting, then
audits the saved forecasts. Repeating the command reuses the unchanged model and
produces identical artifacts in the same runtime. It never relabels synthetic data
as an exchange capture.

## Artifact contract

`model.json` contains a versioned JSON payload and its SHA-256 fingerprint. The
payload records source/symbol, training input hash, training recording boundaries,
parameters, label counts, four ridge feature sets for each horizon, and fixed
training-mean baselines. Each fitted model stores ordered feature names, training
means/scales, coefficients and an intercept. No executable serialization is used.

Loading rejects a changed fingerprint, unsupported schema/parameters, extra or
missing models, wrong feature order, invalid vector shapes, nonfinite state and
nonpositive scales. A fingerprint detects accidental changes; it is not a digital
signature, authentication mechanism or proof of capture provenance.

Held-out input must match source and symbol and start strictly after the training
recording ends plus a 1s embargo. All seven model/baseline comparisons use the same
eligible rows per horizon. Forecasting applies saved scaling and coefficients;
it does not call the fitting routine. Tests replace fitting with a function that
raises, confirming that held-out inference does not invoke it.

## Data quality and drift

The predeclared primary result uses all eligible rows under the unchanged sampling
protocol. A separately labeled sensitivity excludes a snapshot when a trade already
received in its preceding 1s window has receipt-minus-event time >1s or <-100ms.
The filter uses information available at feature observation, not future outcomes.
It does not recalibrate model coefficients or claim to repair unknown quote timing.

The transport timing gate requires a trade receipt-gap p99 <=1s and at least 80%
of all grid snapshots without a flagged preceding-window trade. No-trade windows
have no observed flagged trade; they do not prove fresh exchange-time quotes. A
recording without trades cannot pass the global timing gate. Thresholds were fixed
in SESSION_PROTOCOL.md before viewing the new outcomes. The gate is diagnostic:
failed runs retain all raw data, forecasts and primary results.

Feature drift compares later-session values with the combined model's frozen
training means/scales. Reported quantities are mean standardized shift, relative
standard deviation and the fraction beyond three training standard deviations.
A mean shift above one standard deviation is a descriptive flag, not a significance
test. A constant training feature uses the model's unit-scale fallback.

## Transport telemetry

New captures include event-loop scheduling-lag samples, maximum lag and count above
100ms, plus total/maximum raw-record serialization/write duration. The timer is
cancelled on termination. These measurements can help distinguish local blocking
from broader delivery/clock issues, but cannot identify the cause of upstream delay
or establish an exchange latency benchmark. Persistence failure is fatal rather
than being mislabeled as a reconnectable network failure.

## Reproducibility and interpretation

`audit --model` reloads raw features, verifies strict recording separation and
fingerprints, recomputes frozen scoring, checks saved actual targets and masks, then
recomputes metrics. It does not invoke the held-out evaluator or any fitting routine.
Saved predictions remain available for independent inspection.

The primary and feature-quality subset contain different observations; their RMSEs
must not be interpreted as a controlled improvement from filtering. Pointwise
30s block-bootstrap intervals and 10s/60s alternatives remain exploratory. A later
same-day recording is a stronger separation than within-session folds, but does
not establish independent-day or market-regime robustness. No execution or P&L
model is introduced.
