# Predeclared pilot research protocol

This protocol was fixed before inspecting the new recorded session's outcomes.
The capture is a single bounded ten-minute BTCUSDT Binance Spot session. Its
purpose is a reproducible pilot and an engineering/research demonstration.

## Questions

1. Does level-1 quantity imbalance predict subsequent receive-time midprice returns?
2. Does adding best-quote order-flow imbalance and aggressive trade flow improve
   chronological out-of-sample squared error relative to zero/mean baselines?
3. How sensitive are measured relationships to sampling and freshness choices?
4. How do aggressive buy/sell trade-conditioned markouts differ, with uncertainty
   estimated using time blocks rather than treating every trade as independent?

## Frozen analysis choices

- Sample the last available quote on a regular 1-second grid; quote age <=1 second.
- Look back 1 second for aggressive volume imbalance, trade count and level-1 OFI.
- Label 1s/5s returns using the first eligible quote at/after each target, tolerance .5s.
- Do not carry features or labels across recorded connection boundaries.
- Expanding training splits: first 40%, then 60%, then 80%; each following 20% is test.
- Remove training labels realized at or after test-start minus a 1-second embargo.
- Train-only feature standardization; fixed ridge penalty alpha=10, no tuning.
- Models: zero return, training mean, lag-return persistence, imbalance alone,
  book features, trade features, and their combination including lag return.
- Report RMSE, MAE, correlation and nonflat-target directional accuracy. Neutral
  predictions count as incorrect on nonflat targets. No trading or fee interpretation.
- Paired OOS squared-error improvements use 1,000 resamples of nonoverlapping
  30-second time blocks, seed 17. Suppress intervals below 8 blocks; warn below 20.
- Block-length sensitivity: also show 10s and 60s paired-error intervals alongside
  the fixed 30s primary intervals; do not choose a preferred result after seeing it.
- Trade-conditioned mean markouts use the same time-block bootstrap separately by side.
- Sensitivity: sample interval {1s,2s}, quote age {.25s,1s}, tolerance {.1s,.5s}.
  Report the full grid; do not select the best configuration for the headline result.

The first valid feature row follows a full lookback window. All feature sets share
identical eligible rows within each horizon/configuration. Missing targets and
warmup rows are omitted explicitly with coverage counts. Splits are made on the
regular sampled timeline before dropping rows, so missingness cannot move dates.

Nonoverlapping time blocks are a simple dependence-aware approximation, not proof
of independent blocks. Folds share expanding training history. A single ten-minute
session, many model comparisons, and threshold sensitivity cannot establish durable
alpha. Bootstrap intervals are pointwise and exploratory, without multiple-testing
correction or an independent-day replication. Negative results must be reported.
