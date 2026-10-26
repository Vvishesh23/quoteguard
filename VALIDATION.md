# Latest validation — frozen later-session extension

The current source passes **77 tests in 37.00s**. The second bounded public capture
and frozen-model evaluation are complete. The original 0.2 pilot record follows
below as historical evidence; its 57-test count is superseded by the current suite.

## New executed commands

```sh
.venv/bin/python -m quoteguard fit --input data/btcusdt-research-01.jsonl --out models/pilot-frozen.json
.venv/bin/python -m quoteguard collect --symbol BTCUSDT --minutes 10 --system-trust --out data/btcusdt-research-02.jsonl
.venv/bin/python -m quoteguard holdout --model models/pilot-frozen.json --input data/btcusdt-research-02.jsonl --out reports/frozen-holdout
.venv/bin/python -m quoteguard audit --model models/pilot-frozen.json --input data/btcusdt-research-02.jsonl --report reports/frozen-holdout --out reports/frozen-holdout/audit.json
.venv/bin/python -m quoteguard session-demo --out reports/session-demo
.venv/bin/python -m pytest -q
.venv/bin/python -m pip install -e '.[test,system-trust]'
.venv/bin/python -m pip check
```

Training state and SESSION_PROTOCOL.md were fingerprinted before the new capture.
The registration check confirms the artifact/protocol identities remain unchanged.
The real frozen-model audit passes for **8,330 saved forecasts**, recomputing raw
features, saved-state scoring, test labels, quality masks and RMSE. The offline
synthetic session demo/audit also passes. Both charts were visually inspected.
No test-session fitting, normalization or model selection is performed.

The new tests include artifact round-trip/determinism, exclusive model creation,
no-refit enforcement, overlap/embargo/source/symbol rejection, malformed state and
fingerprint checks, past-only receipt-quality masks, fixed baselines, deterministic
held-out reports, corrupted/duplicate forecast rejection, an idempotent offline
session demo, telemetry fields/cancellation state and fatal disk-write classification.

## Measured later capture

- UTC window: 2026-10-26 17:42:06.122438 to 17:52:05.307209; **599.184771s**.
- **60,582 events**: **45,495 quotes**, **15,087 trades**; all persisted records parse.
- **1 connection**, **0 recorded disconnects**; duration stop, elapsed cleanup ~601s.
- Starts **7,963.647457s** after training ends; both recordings are on the same day.
- **599** grid observations, **598** feature-eligible; **597/593** labeled rows at 1s/5s.
- Trade receipt-gap median **16.14ms**, p99 **560.76238ms**; no trade exceeds 1s or is
  below -100ms. All feature-quality windows pass; subset/primary metrics coincide.
- Recorder: **5,924** scheduling observations, max lag **16.895208ms**, none >100ms.
- Serialization/write: **60,582** writes, total **3,644.807358ms**, max **12.961417ms**.
- Test SHA-256: `2376c64cac7d0241e41216247eb65cad7cf4eed64c8fd294a33c0e4e6b42dd58`.

These are run-specific observations, not portable latency/throughput benchmarks.
Differences from the pilot cannot be attributed causally to software changes.
Total across the two successful recordings: **205,370 real events**.

Combined-model later-session RMSE is **0.269235/0.738618 bps** at 1s/5s, compared with
zero-return **0.260491/0.716083 bps**. The combined point errors are higher at both
horizons; paired intervals versus zero include zero. Its 93.33% conditional 1s hit
rate has only **90 nonflat targets among 597**; it is not a trading-performance claim.
The later recording passes the predeclared timing gate but does not establish
synchronized quote timestamps, durable alpha or independent-day robustness.

Remaining research: fixed-model replication on later independent days, stable
transport/clock auditing and regime sensitivity. No persistent capture remains running.
Hosted CI is configured, including session-demo, but has not run remotely.

---

# Validation record — QuoteGuard 0.3.0

Verified locally on Python 3.12.1/macOS. The runtime pins are in
`requirements-lock.txt`. Python 3.11/3.12 hosted CI is configured but has not been
executed on a remote runner. No trading service is deployed.

## Commands executed

From the project folder:

```sh
.venv/bin/python -m pip install -e '.[test,system-trust]'
.venv/bin/python -m pytest -q
.venv/bin/python -m quoteguard collect --symbol BTCUSDT --minutes 10 --system-trust --out data/btcusdt-research-01.jsonl
.venv/bin/python -m quoteguard analyze --input data/btcusdt-research-01.jsonl --out reports/live-descriptive
.venv/bin/python -m quoteguard study --input data/btcusdt-research-01.jsonl --out reports/live-study
.venv/bin/python -m quoteguard audit --input data/btcusdt-research-01.jsonl --study reports/live-study --out reports/live-study/audit.json
.venv/bin/python -m quoteguard demo --out reports/demo
.venv/bin/python -m quoteguard analyze --input data/synthetic.jsonl --out reports/replay
.venv/bin/python -m quoteguard study --input data/synthetic.jsonl --out reports/study-demo
.venv/bin/python -m quoteguard audit --input data/synthetic.jsonl --study reports/study-demo --out reports/study-demo/audit.json
.venv/bin/python -m quoteguard --help
.venv/bin/python -m pip check
```

The original MVP had 39 passing tests and a failed 30-second capture using the
standard Python certificate store. That historical failed attempt is retained.
Native system TLS verification resolved the certificate-store problem. No
certificate or hostname verification was disabled. The subsequent ten-minute
capture succeeded and is the only real input used in the pilot case study.

## Automated validation

**57 passed in 7.54s** on the final source. `reports/test-results.txt` is the log.

Coverage includes quote/trade parsing, maker/aggressor direction, invalid/crossed
markets, IDs and clocks, missing/stale observations, zero denominators, prior-only
joins, equal-timestamp ordering, 1s/5s forward-only targets, missing future quotes,
tolerance boundaries, deterministic replay, CLI paths, bounded capture and
cancellation cleanup. The upgrade adds:

- Hand-computed best-quote OFI transitions and trailing-window boundaries.
- Causal regular-grid trade/quote features and future-mutation invariance.
- Reconnect isolation for as-of features, target labels and lookback warmup.
- Train-only scaling, known linear-signal recovery and actual-label-time purging.
- Equal OOS rows across models, neutral predictions and flat-target handling.
- Deterministic time-block intervals, insufficient-block handling and a clustered
  synthetic example demonstrating why individual-event resampling understates uncertainty.
- Adapter injection and verified system/default TLS-context invariants.
- Full study artifacts, deterministic study replay, insufficient-sample rejection,
  independent saved-output audit and deliberate prediction-corruption detection.

The installed package, CLI help and dependency integrity check succeed.
Both offline study and real study audits pass. The real audit independently checks
the input fingerprint, prior-quote times, forward horizon bounds, purged training
rows, equal test rows, saved actual targets and RMSE recomputation across **4,998
saved forecast rows**. Synthetic audit checks **966 forecast rows**.

The demo and explicit offline replay summary/PNG match byte-for-byte. Study tests
compare all primary artifact bytes from identical synthetic input. Real and
synthetic study charts were visually inspected. Float CSV output is rounded to ten
significant digits; the artifact audit uses small numeric tolerances accordingly.

## Measured real session

- Source: verified public Binance Spot BTCUSDT streams.
- UTC window: 2026-10-26 15:19:23.615103 to 15:29:22.474981; **598.859878s**.
- **144,788** raw records; all pass parsing: **109,635 quotes**, **35,153 trades**.
- **4 connections**, **3 keepalive-timeout failures**; raw gaps are preserved.
- **599** regular grid observations; **496** eligible feature rows.
- Usable labels: **473** at 1s and **467** at 5s; OOS rows: **359** and **355**.
- Median quote gap: .046ms; p99: 92.59076ms; maximum: 9,326.444ms.
- Median trade receipt-minus-event difference: 63.78198ms; p99: 19,470.75852ms.
- 2,462 trades have receipt-minus-event differences >1s; 1,067 exceed 5s.
- Input SHA-256: `190c6cd8887d9a2cf3169039f7ab2bdee4de0831a70fe420407320a1b9a42089`.

Parser validity describes persisted messages, not complete upstream capture.
Receipt differences combine clock offset, timestamp semantics, transport and
application scheduling; they are not calibrated network latency measurements.
The material timing distortions are emphasized in the report and case study.

## Research result

Combined-model OOS RMSE: **0.891946 bps at 1s**, **1.533865 bps at 5s**.
Zero-return OOS RMSE: **0.660875 bps at 1s**, **1.604741 bps at 5s**.
The combined model is worse at 1s; its lower 5s point error is not a robust
improvement claim. All six primary paired forecast-comparison intervals include
zero. The protocol has only twelve 30-second OOS time blocks.

Full feature ablations, coefficient/scaling exports, freshness/sampling sweeps and
10s/30s/60s block sensitivity are preserved under `reports/live-study/`.
This is a single-session pilot with no independent-day replication, real fills,
queue model, execution-price P&L, profitability or durable-alpha claim.

## Remaining validation

Collect independent later sessions on a stable trusted transport, audit clocks and
buffering, keep the existing protocol fixed and evaluate entire held-out sessions.
Use new filenames; captures are never overwritten. CI needs an actual repository
push before hosted execution can be claimed. See PORTFOLIO_GUIDE.md and CASE_STUDY.md.
