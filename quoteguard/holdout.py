"""Later-session evaluation with frozen training state and visible quality gates."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
from .evaluation import summarize_predictions
from .events import load_events, utc_ns
from .frozen import frozen_predictions, load_artifact
from .plotting import plt
from .study import table


def run_holdout(model_path: Path, input_path: Path, out: Path) -> dict:
    artifact = load_artifact(model_path)
    payload = artifact["payload"]
    events, validity = load_events(input_path)
    samples, predictions, drift, diagnostics = frozen_predictions(artifact, events)
    metric_parts, interval_parts, length_parts = [], [], []
    for scope in ("all_eligible", "feature_quality_subset"):
        subset = predictions if scope == "all_eligible" else predictions[predictions.receipt_quality_ok]
        metrics, intervals = summarize_predictions(subset)
        if not metrics.empty:
            metrics["scope"], intervals["scope"] = scope, scope
            metric_parts.append(metrics)
            interval_parts.append(intervals)
            for length in (10, 30, 60):
                _, alternate = summarize_predictions(subset, block_s=length)
                alternate["scope"] = scope
                length_parts.append(alternate)
    metrics = pd.concat(metric_parts, ignore_index=True)
    intervals = pd.concat(interval_parts, ignore_index=True)
    block_sensitivity = pd.concat(length_parts, ignore_index=True)
    metadata_path = input_path.with_suffix(input_path.suffix + ".meta.json")
    summary = {"source": payload["source"], "symbol": payload["symbol"],
               "model_artifact_id": artifact["artifact_id"],
               "training_input_sha256": payload["training_input_sha256"],
               "test_input_sha256": hashlib.sha256(input_path.read_bytes()).hexdigest(),
               "training_last_recv_ns": payload["training_last_recv_ns"],
               "test_first_recv_ns": events[0]["recv_ns"], "test_last_recv_ns": events[-1]["recv_ns"],
               "test_start_utc": utc_ns(events[0]["recv_ns"]), "test_end_utc": utc_ns(events[-1]["recv_ns"]),
               "test_duration_s": (events[-1]["recv_ns"] - events[0]["recv_ns"]) / 1e9,
               "separation_seconds": (events[0]["recv_ns"] - payload["training_last_recv_ns"]) / 1e9,
               "refit_on_test": False, "training_quality": payload["training_transport"],
               **validity, **diagnostics,
               "quotes": sum(e["kind"] == "quote" for e in events),
               "trades": sum(e["kind"] == "trade" for e in events),
               "capture_metadata": json.loads(metadata_path.read_text()) if metadata_path.exists() else None,
               "protocol": "SESSION_PROTOCOL.md", "same_day_only": True}
    # Different dates are still not a planned independent-day replication.
    summary["same_day_only"] = utc_ns(payload["training_last_recv_ns"])[:10] == summary["test_start_utc"][:10]
    out.mkdir(parents=True, exist_ok=True)
    for name, frame in (("samples", samples), ("predictions", predictions), ("metrics", metrics),
                        ("paired_intervals", intervals), ("block_sensitivity", block_sensitivity), ("feature_drift", drift)):
        frame.to_csv(out / f"{name}.csv", index=False, float_format="%.10g")
    (out / "summary.json").write_text(json.dumps(summary, sort_keys=True, indent=2, allow_nan=False) + "\n")
    draw_holdout(out, summary, metrics, samples, drift)
    write_holdout(out, summary, metrics, intervals, drift)
    return summary


def draw_holdout(out: Path, summary: dict, metrics: pd.DataFrame,
                 samples: pd.DataFrame, drift: pd.DataFrame) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(13, 9), layout="constrained")
    order = ["zero", "train_mean", "lag_persistence", "imbalance", "book", "trade", "combined"]
    for horizon, axis in zip((1, 5), axes[0]):
        frame = metrics[(metrics.horizon_s == horizon) & (metrics.scope == "all_eligible")].set_index("model").reindex(order)
        axis.barh(order, frame.rmse_bps, color=["#de9445" if name == "combined" else "#225e83" for name in order])
        axis.invert_yaxis()
        axis.set(title=f"{horizon}s later-session frozen-model error", xlabel="RMSE (bps)")
    frame = drift[drift.horizon_s == 1]
    axes[1, 0].barh(frame.feature, frame.mean_in_train_std, color="#225e83")
    axes[1, 0].axvline(0, color="gray", lw=.7)
    axes[1, 0].axvline(-1, color="#de9445", ls="--", lw=.8)
    axes[1, 0].axvline(1, color="#de9445", ls="--", lw=.8)
    axes[1, 0].set(title="Feature mean drift (1s eligible rows)", xlabel="Frozen training standard deviations")
    x = (samples.recv_ns - samples.recv_ns.iloc[0]) / 1e9
    axes[1, 1].plot(x, samples.window_trade_gap_max_ms, color="#225e83", lw=1)
    axes[1, 1].axhline(1000, color="#de9445", ls="--", label="1s diagnostic threshold")
    axes[1, 1].set_yscale("symlog", linthresh=1)
    axes[1, 1].set(title="Largest trade receipt gap in preceding 1s", xlabel="Seconds into later capture", ylabel="Receipt − event time (ms)")
    axes[1, 1].legend(fontsize=8)
    label = "SYNTHETIC" if summary["source"] == "synthetic" else "BINANCE PUBLIC CAPTURE"
    gate = "PASS" if summary["transport"]["timing_gate_passed"] else "FAIL"
    fig.suptitle(f"QuoteGuard | {label} | frozen later-session evaluation\nTransport timing gate: {gate}; exploratory, no execution inference", fontsize=13)
    fig.savefig(out / "holdout.png", dpi=150, metadata={"Software": "QuoteGuard"})
    plt.close(fig)


def write_holdout(out: Path, summary: dict, metrics: pd.DataFrame,
                  intervals: pd.DataFrame, drift: pd.DataFrame) -> None:
    label = "SYNTHETIC" if summary["source"] == "synthetic" else "BINANCE PUBLIC CAPTURE"
    lines = [f"# QuoteGuard frozen later-session evaluation — {label}", "",
        f"Model artifact: `{summary['model_artifact_id']}`.",
        f"Training input SHA-256: `{summary['training_input_sha256']}`.",
        f"Test input SHA-256: `{summary['test_input_sha256']}`.", "",
        f"New capture: {summary['test_start_utc']} to {summary['test_end_utc']} "
        f"({summary['test_duration_s']:.2f}s), {summary['raw_records']:,} raw records; "
        f"{summary['quotes']:,} quotes and {summary['trades']:,} trades.",
        f"The new recording starts {summary['separation_seconds']:.2f}s after the training recording ends.", "",
        "## Frozen protocol and findings", "",
        "Every model coefficient, feature mean/scale and training-mean baseline was fixed in a "
        "fingerprinted JSON artifact before this capture. There is no test-session refit, normalization "
        "or parameter selection. Source, symbol and strict temporal separation are validated. "
        "The quality thresholds were fixed in SESSION_PROTOCOL.md before inspecting these outcomes.", ""]
    primary = metrics[metrics.scope == "all_eligible"]
    for horizon in (1, 5):
        rows = primary[primary.horizon_s == horizon].set_index("model")
        if "combined" in rows.index:
            lines.append(f"- {horizon}s: combined RMSE {rows.loc['combined', 'rmse_bps']:.6f} bps; "
                         f"zero baseline {rows.loc['zero', 'rmse_bps']:.6f} bps; "
                         f"imbalance-only {rows.loc['imbalance', 'rmse_bps']:.6f} bps. "
                         f"Nonflat targets: {int(rows.loc['combined', 'nonflat_targets'])}/{int(rows.loc['combined', 'n'])}; "
                         "directional accuracy is conditional on those nonflat targets.")
    gate = summary["transport"]["timing_gate_passed"]
    lines += ["", f"**Transport timing gate: {'PASS' if gate else 'FAIL'}.** "
              "The gate checks trade receipt-gap p99 <=1s and at least 80% of grid snapshots "
              "without a flagged trade in their previous 1s window. Passing does not establish "
              "synchronized clocks or exchange-time quote sequencing. Failing weakens timing inference; "
              "it does not hide or replace the primary results.", "",
              "This is a separate later recording" + (" on the same day." if summary["same_day_only"] else ".") +
              " It does not establish independent-day or regime robustness.", "", "## Forecast metrics", ""]
    lines += table(metrics, ["scope", "horizon_s", "model", "n", "nonflat_targets", "rmse_bps", "mae_bps", "correlation", "nonflat_directional_accuracy"])
    if summary["transport"]["snapshot_quality_fraction"] == 1:
        lines += ["", "No grid windows were flagged by the feature-quality rule in this recording, "
                  "so the primary and feature-quality subset metrics are identical."]
    lines += ["", "The feature-quality subset uses only receipt-time information: in the preceding 1s, "
              "no received trade may have receipt-minus-event time >1s or <-100ms. No model is refit. "
              "Subset and primary metrics have different samples, so differences are not a controlled "
              "forecast-improvement comparison. Quote exchange timestamps remain unavailable.", "", "## Paired time-block intervals", ""]
    lines += table(intervals, ["scope", "horizon_s", "comparison", "mean", "ci_low", "ci_high", "blocks", "status"])
    lines += ["", "Positive paired error differences favor the combined model. Primary 30s blocks, "
              "1,000 resamples, seed 17; 10s/60s alternatives are in block_sensitivity.csv. "
              "Few blocks and multiple comparisons make these pointwise intervals exploratory.", "",
              "## Train-to-test feature drift", ""]
    lines += table(drift, ["horizon_s", "feature", "mean_in_train_std", "test_std_in_train_std", "fraction_abs_z_above_3", "flag_mean_shift"])
    lines += ["", "Drift uses the combined model's frozen training mean and scale. A mean shift above "
              "one training standard deviation is flagged descriptively. Constant training columns use "
              "the model's unit-scale fallback, so those ratios require care. Drift is not proof of cause.", "",
              "![Frozen-session research](holdout.png)", "", "## Quality and provenance", "",
              "Training transport: `" + json.dumps(summary["training_quality"], sort_keys=True) + "`.",
              "Test transport: `" + json.dumps(summary["transport"], sort_keys=True) + "`.",
              "Grid coverage: `" + json.dumps(summary["coverage"], sort_keys=True) + "`.", "",
              "Receipt gaps mix clock offset, timestamp semantics, transport buffering and application "
              "scheduling. The collector reports event-loop and disk-write telemetry when available, "
              "without treating it as a latency benchmark. Raw captures retain reconnect boundaries.", "",
              "Model IDs detect accidental changes, not malicious tampering or venue authenticity. "
              "No order fills, queue position, trading P&L, fees or profitable strategy are inferred. "
              "Next validation requires independent later days and stable timestamp/transport behavior."]
    metadata = summary["capture_metadata"] or {}
    if "loop_health" in metadata and "write_health" in metadata:
        loop, writes = metadata["loop_health"], metadata["write_health"]
        lines += ["", "## Recorder telemetry", "", "| Measurement | Value |", "|---|---:|",
                  f"| Event-loop timer samples | {loop['samples']} |",
                  f"| Maximum observed timer scheduling lag (ms) | {loop['max_lag_ms']:.6f} |",
                  f"| Timer observations above 100ms | {loop['above_100ms']} |",
                  f"| Raw record writes | {writes['writes']} |",
                  f"| Mean serialization/write duration (ms) | {writes['total_ms'] / max(1, writes['writes']):.6f} |",
                  f"| Maximum serialization/write duration (ms) | {writes['max_ms']:.6f} |", "",
                  "These are measurements from this recorder/run, not portable throughput or venue-latency benchmarks."]
    (out / "holdout.md").write_text("\n".join(lines) + "\n")


def audit_holdout(model_path: Path, input_path: Path, report_dir: Path, out: Path) -> dict:
    """Recompute frozen scoring from raw features, without invoking the evaluator."""
    from .sampling import sample_features, FEATURE_SETS
    from .quality import receipt_quality
    from .evaluation import regression_metrics
    artifact = load_artifact(model_path)
    payload = artifact["payload"]
    summary = json.loads((report_dir / "summary.json").read_text())
    if summary["model_artifact_id"] != artifact["artifact_id"]:
        raise ValueError("holdout audit: model identity mismatch")
    if hashlib.sha256(input_path.read_bytes()).hexdigest() != summary["test_input_sha256"]:
        raise ValueError("holdout audit: input fingerprint mismatch")
    events, _ = load_events(input_path)
    if events[0]["recv_ns"] <= payload["training_last_recv_ns"] + 1000000000:
        raise ValueError("holdout audit: recording overlap")
    if any(e["source"] != payload["source"] or e["symbol"] != payload["symbol"] for e in events):
        raise ValueError("holdout audit: source or symbol mismatch")
    samples, _ = sample_features(events, **payload["parameters"])
    samples, _ = receipt_quality(events, samples)
    saved = pd.read_csv(report_dir / "predictions.csv")
    metrics = pd.read_csv(report_dir / "metrics.csv")
    if set(saved.horizon_s) - {1, 5} or saved.duplicated(["recv_ns", "horizon_s", "model"]).any():
        raise ValueError("holdout audit: duplicate or unexpected prediction rows")
    if set(metrics.scope) - {"all_eligible", "feature_quality_subset"} or metrics.duplicated(["scope", "horizon_s", "model"]).any():
        raise ValueError("holdout audit: invalid metric rows")
    expected_metric_keys = set()
    for (horizon, name), group in saved.groupby(["horizon_s", "model"]):
        expected_metric_keys.add(("all_eligible", horizon, name))
        if group.receipt_quality_ok.any():
            expected_metric_keys.add(("feature_quality_subset", horizon, name))
    if set(zip(metrics.scope, metrics.horizon_s, metrics.model)) != expected_metric_keys:
        raise ValueError("holdout audit: incomplete metric rows")
    expected_models = set(FEATURE_SETS) | {"zero", "train_mean", "lag_persistence"}
    for horizon in (1, 5):
        target = f"forward_bps_{horizon}s"
        test = samples.dropna(subset=FEATURE_SETS["combined"] + [target]).set_index("recv_ns")
        states = payload["horizons"][str(horizon)]
        rows = saved[saved.horizon_s == horizon]
        if not len(test):
            if len(rows):
                raise ValueError("holdout audit: unexpected horizon rows")
            continue
        if set(rows.model) != expected_models:
            raise ValueError("holdout audit: missing or extra model")
        for name in expected_models:
            group = rows[rows.model == name]
            if group.recv_ns.tolist() != test.index.tolist():
                raise ValueError("holdout audit: test row mismatch")
            if not np.allclose(group.actual_bps, test[target], rtol=1e-8, atol=1e-9):
                raise ValueError("holdout audit: actual target mismatch")
            if not np.array_equal(group.receipt_quality_ok, test.receipt_quality_ok):
                raise ValueError("holdout audit: quality mask mismatch")
            if name == "zero":
                expected = np.zeros(len(test))
            elif name == "train_mean":
                expected = np.full(len(test), states["train_mean_bps"])
            elif name == "lag_persistence":
                expected = test.lag_return_bps.to_numpy()
            else:
                state = states["models"][name]
                z = (test[state["features"]].to_numpy() - np.asarray(state["means"])) / np.asarray(state["scales"])
                expected = z.dot(np.asarray(state["coefficients"])) + state["intercept"]
            if not np.allclose(group.predicted_bps, expected, rtol=1e-8, atol=1e-9):
                raise ValueError("holdout audit: frozen prediction mismatch")
    for _, row in metrics.iterrows():
        group = saved[(saved.horizon_s == row.horizon_s) & (saved.model == row.model)]
        if row.scope == "feature_quality_subset":
            group = group[group.receipt_quality_ok]
        computed = regression_metrics(group.actual_bps.to_numpy(), group.predicted_bps.to_numpy())
        if len(group) != row.n or not np.isclose(computed["rmse_bps"], row.rmse_bps, rtol=1e-8, atol=1e-9):
            raise ValueError("holdout audit: metric mismatch")
    result = {"status": "passed", "model_artifact_id": artifact["artifact_id"],
              "prediction_rows": len(saved), "checks": ["model_identity", "input_fingerprint",
              "strict_session_separation", "raw_feature_recomputation", "frozen_scoring",
              "no_refit", "quality_masks", "actual_targets", "saved_metric_recomputation"]}
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    return result


def frozen_demo(out: Path) -> dict:
    """Exercise train/freeze/later-inference/audit offline on labeled synthetic data."""
    from .fixture import generate
    from .frozen import fit_artifact
    out.mkdir(parents=True, exist_ok=True)
    train, test, model = out / "synthetic-train.jsonl", out / "synthetic-test.jsonl", out / "model.json"
    generate(train)
    generate(test, seed=44, steps=1800, start_ns=1767225900000000000)
    if model.exists():
        artifact = load_artifact(model)
        if artifact["payload"]["training_input_sha256"] != hashlib.sha256(train.read_bytes()).hexdigest():
            raise ValueError("existing demo model belongs to different training data; choose a new output directory")
    else:
        fit_artifact(train, model)
    summary = run_holdout(model, test, out)
    audit_holdout(model, test, out, out / "audit.json")
    return summary
