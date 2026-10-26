# Presenting QuoteGuard for crypto roles

## Project positioning

**QuoteGuard — Crypto Market Microstructure Research**

A public-feed research pipeline studying level-1 order flow and trade-conditioned
adverse selection. It combines market-data engineering, causal time alignment and
an auditable chronological evaluation. Its strongest evidence is a reproducible
real-data pilot and explicit negative findings, rather than a trading-performance claim.

For junior quant research/trading roles, lead with experimental design and what
failed. For quant developer roles, lead with event validation, receive clocks,
reconnect boundaries, deterministic replay and tested data-processing invariants.

## Two-minute walkthrough

1. Open `reports/live-study/study.md`: show the real source, input fingerprint,
   recording window, model comparison and uncertainty intervals.
2. Explain why 1s/5s targets use the first quote at/after the horizon and why trade
   features use only the latest previously received quote.
3. Open `reports/live-study/splits.csv`: each training-label timestamp is strictly
   before the next test period minus the embargo. Show a leakage regression test.
4. Explain why the combined model's 1s error is worse than the zero baseline, and
   why the lower 5s error does not establish improvement when intervals include zero.
5. Discuss the transport problem: three reconnects and a roughly 19.5s p99 receipt
   gap. Local arrival-time findings cannot be promoted to exchange-time alpha.

## Questions to be ready for

**Why regular sampling?** Event-weighted averages overrepresent busy quote bursts.
A regular grid reduces that weighting, but does not eliminate dependent labels,
missing intervals, transport distortions or repeated stale information.

**Why ridge rather than a complex model?** The dataset is small and the baseline
question matters more than model capacity. Imbalance and microprice edge can be
highly collinear; a fixed ridge penalty keeps the experiment simple. Alpha=10 was
not selected using the test results.

**What is OFI here?** A signed sum of best-bid/ask price/quantity transitions over
the preceding second, divided by currently observed total best-quote depth.
This adapts the level-1 OFI construction; it does not identify every individual
limit order or cancellation and does not reconstruct a full order book.

**Why purging?** A feature observed before the split can still have a forward label
that is realized inside the test period. Splitting on feature timestamps alone
would allow the training process to use future test-period information.

**Why time blocks?** Nearby trades and overlapping horizons are dependent. Individual
trade resampling would overstate the number of independent observations. Even
30-second blocks yield only twelve OOS blocks in this pilot, so uncertainty remains
large; 10s/60s block-length sensitivity is also reported.

**Why not turn markouts into market-maker P&L?** Public trades do not tell us which
orders would fill, queue position, inventory, fees or own-order impact. These are
aggressor-signed future midprice movements, not execution outcomes.

**What would improve the research next?** Collect independently scheduled sessions
across days on a stable low-buffering connection; audit timestamp/clock behavior;
freeze the model and evaluate entire later sessions; assess longer block lengths,
market regimes and feature stability. A second high-capacity model is lower priority.

## Publishing checklist

The source, synthetic fixture and small real-data report artifacts are ready for a
repository. Large raw captures and event-level CSV files are ignored by default.
The downloadable project bundle includes the actual recorded data so the pilot can
be rerun. Review venue data redistribution terms before public hosting of raw data.
There is no repository URL, deployed service or remotely executed CI claim yet.
The included CI workflow is configured, but has only been exercised through its
local commands; it has not run on a hosted runner.

Use the measured bullets in RESUME_BULLETS.md. Avoid adding profitability,
production trading, low-latency performance or durable predictive-alpha claims.


## Frozen-session extension

The `fit`/`holdout` pipeline persists the trained coefficients and scaling state in
JSON, validates strict recording separation, and evaluates a later session without
refitting. `session-demo` exercises this boundary offline. Tests deliberately make
fitting raise during inference and corrupt saved state/predictions to verify the
boundary and audit. Explain why this differs from expanding folds within one file.
See FROZEN_MODELS.md and the recorded frozen-holdout report for executed evidence.
