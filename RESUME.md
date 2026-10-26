# Resume work safely — QuoteGuard 0.3

The current upgrade is complete. Read README.md, PROJECT_STATUS.md,
FROZEN_CASE_STUDY.md, SESSION_PROTOCOL.md, FROZEN_MODELS.md and VALIDATION.md;
inspect existing files, then run `.venv/bin/python -m pytest -q`.
Preserve both real recordings and frozen training state.

Implemented: bounded public capture, raw/receipt clocks, strict event adapter,
reconnect-safe as-of features/targets, regular-time OFI/trade features, purged
within-session forecasts, block uncertainty/sensitivity, immutable JSON model
artifacts, separate-session no-refit inference, observable quality gates, feature
drift, independent frozen-scoring audits, deterministic offline session-demo,
recorder telemetry and persistence-error classification.

Verified: **77 tests pass in 37.00s**. Real held-out audit passes for **8,330 forecasts**.
Offline session-demo/audit and deterministic artifact checks pass. Installation,
dependency integrity and CLI paths pass. Actual charts inspected. No job remains.

Data: pilot 144,788 events; later same-day capture 60,582 events (45,495 quotes,
15,087 trades), one connection/no disconnects. Total **205,370 real events**.
The later transport gate passes, but the frozen combined model has higher RMSE
than zero return at both 1s and 5s. Its conditional hit rate is not an execution
or unconditional forecasting success claim. No independent-day alpha validation.

Frozen model: `models/pilot-frozen.json`, ID
`e75939fd3dedbbd1b0029b4a84f8f1febb57138ee708d3cde5a007bb1d8ac91e`.
It was fitted under the existing 0.2 feature definitions; schema 1 is supported by
the 0.3 reader. Keep it unchanged. The session manifest/protocol hashes match.

Single next highest-priority research task: independent later-day replication with
the existing frozen model and stable transport. Use a fresh recording filename:

```sh
.venv/bin/python -m quoteguard collect --symbol BTCUSDT --minutes 20 --system-trust --out data/session-03.jsonl
.venv/bin/python -m quoteguard holdout --model models/pilot-frozen.json --input data/session-03.jsonl --out reports/session-03-holdout
.venv/bin/python -m quoteguard audit --model models/pilot-frozen.json --input data/session-03.jsonl --report reports/session-03-holdout --out reports/session-03-holdout/audit.json
```

Do not refit after inspecting held-out results and imply they remained held out.
Any revised model/protocol needs new later observations. Hosted CI is configured
but not run remotely. No order execution, fees, fills or P&L model is implemented.

Restart instruction: Read the latest status, frozen-case study and protocol, run
the quick tests, then continue fixed-model independent-day validation without
recreating completed work, altering frozen state or fabricating data.
