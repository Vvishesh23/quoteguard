# Later-session validation: freezing the model exposed the generalization limit

## What changed

The first pilot evaluated expanding folds inside one recording. This extension
freezes the entire training state, then evaluates a separately captured later
session without fitting or normalizing on test data. It adds an explicit model
artifact boundary, source/symbol/overlap guards, drift diagnostics and a predeclared
transport gate. A deterministic synthetic session demo exercises the same workflow.

## Experiment

The training recording contains 144,788 public Binance Spot BTCUSDT events. Its
eligible 1s/5s labels train four ridge feature sets with fixed alpha=10, alongside
zero, frozen training-mean and lag-return baselines. All feature parameters remain
unchanged. The JSON artifact and protocol manifest were saved before collecting
the later session. The artifact ID begins `e75939fd3dedbbd1`.

The new ten-minute recording starts 7,963.65s after the training recording ends.
It contains **60,582 events: 45,495 quotes and 15,087 trades**, over **599.18s**.
There was **one connection and no recorded disconnect**. Both recordings are from
the same day; this is not independent-day validation.

## Frozen-model result

| Horizon | Later-session observations | Zero RMSE | Combined RMSE |
|---|---:|---:|---:|
| 1s | 597 | 0.260491 bps | 0.269235 bps |
| 5s | 593 | 0.716083 bps | 0.738618 bps |

The frozen combined model has higher squared forecast error than the zero baseline
at both horizons. Its paired 30s-block improvement intervals versus zero include
zero: **[-0.016119, 0.008854] bps²** at 1s and **[-0.133088, 0.072208] bps²** at 5s.
Each primary comparison uses twenty time blocks and remains exploratory.

The trade-only model has lower point RMSE than zero in this session, but it was one
of several predeclared comparisons. It is not substituted for the combined model
as a newly selected headline strategy. No durable edge or profitability is claimed.

## Why the high directional hit rate is misleading on its own

The combined model's 1s nonflat-target directional accuracy is **93.33%**, yet its
RMSE is worse than zero return. Only **90 of 597** targets are nonflat. That hit rate
is conditional on this small moving-price subset; it does not measure execution,
fees or magnitude accuracy. A strong-looking conditional metric can coexist with
poor unconditional error, so the project exports both the denominator and errors.

## Transport quality and drift

The new session passes the fixed timing gate: trade receipt-minus-event p99 is
**560.76ms**, with no trades above 1s or below -100ms, and every grid window passes
the observable feature-quality mask. Primary and subset metrics therefore match.
The pilot's p99 was ~19.47s and failed the same gate. Different market/network
conditions prevent attributing this difference to a software performance improvement.
Neither gate result establishes synchronized exchange quote timestamps.

Recorder telemetry in the later capture recorded 5,924 scheduling observations,
maximum scheduling lag **16.90ms**, and no observations above 100ms. Mean raw-record
serialization/write time was **0.06016ms**, maximum **12.96ms**. These are measurements
of this recorder/run, not venue latency or portable performance benchmarks.

Feature distributions also changed: the 1s eligible log trade-count mean shifted
about **-0.80 training standard deviations**. Microprice-edge and spread variation
were substantially lower than in training. These observations describe a quieter
later sample, not a causal explanation of forecast performance.

## Evidence and next step

The independent audit recomputes raw features and frozen scoring for **8,330 saved
forecast rows**, checking model/input fingerprints, recording separation, target
values, quality masks and error metrics. It passes. The suite has **77 passing tests**,
including no-refit enforcement, corruption/duplicate detection and deterministic
model/report replay.

Across both captures, the project now retains **205,370 real events**. The empirical
conclusion remains restrained: this fixed feature/model combination did not beat
the zero baseline in the later session. The next experiment should use independent
later days with the same frozen state and stable collection, without tuning to the
held-out results. No execution simulator, maker fills or trading P&L is inferred.

See the [complete held-out report](reports/frozen-holdout/holdout.md),
[frozen-model contract](FROZEN_MODELS.md) and [experiment protocol](SESSION_PROTOCOL.md).
