"""Independently recompute saved forecast errors and chronological split invariants."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
from .sampling import FEATURE_SETS


def audit_study(input_path: Path, study_dir: Path, out: Path) -> dict:
    summary = json.loads((study_dir / "summary.json").read_text())
    if hashlib.sha256(input_path.read_bytes()).hexdigest() != summary["input_sha256"]:
        raise ValueError("audit failed: input fingerprint mismatch")
    samples = pd.read_csv(study_dir / "samples.csv", dtype={
        "target_recv_ns_1s": "Int64", "target_recv_ns_5s": "Int64"})
    predictions = pd.read_csv(study_dir / "predictions.csv")
    metrics = pd.read_csv(study_dir / "metrics.csv")
    splits = pd.read_csv(study_dir / "splits.csv")
    checks = {"input_fingerprint": True, "prior_quote_times": True,
              "forward_horizon_bounds": True, "purged_training_labels": True,
              "same_test_rows": True, "saved_actual_targets": True, "recomputed_rmse": True}
    if (samples.quote_recv_ns > samples.recv_ns).any():
        raise ValueError("audit failed: quote received after feature observation")
    for horizon in (1, 5):
        target, realized = f"forward_bps_{horizon}s", f"target_recv_ns_{horizon}s"
        present = samples[realized].notna()
        delays = samples.loc[present, realized] - samples.loc[present, "recv_ns"] - horizon * 1000000000
        if (delays < 0).any() or (delays > round(summary["sampling"]["tolerance_s"] * 1e9)).any():
            raise ValueError("audit failed: invalid future target time")
        valid = samples.dropna(subset=FEATURE_SETS["combined"] + [target, realized])
        for _, split in splits[splits.horizon_s == horizon].iterrows():
            if split.status != "ok":
                continue
            train = valid[(valid.recv_ns < split.test_start_ns) & (valid[realized] < split.purge_cutoff_ns)]
            if len(train) != split.train_rows or int(train[realized].max()) != int(split.max_train_target_ns):
                raise ValueError("audit failed: purged training rows differ")
            expected = valid[(valid.recv_ns >= split.test_start_ns) & (valid.recv_ns <= split.test_end_ns)].set_index("recv_ns")
            fold_predictions = predictions[(predictions.horizon_s == horizon) & (predictions.fold == split.fold)]
            for _, model in fold_predictions.groupby("model"):
                if model.recv_ns.tolist() != expected.index.tolist():
                    raise ValueError("audit failed: test rows differ across models")
                if not np.allclose(model.actual_bps, expected.loc[model.recv_ns, target], rtol=1e-8, atol=1e-9):
                    raise ValueError("audit failed: saved forecast targets differ from samples")
    for _, row in metrics.iterrows():
        p = predictions[(predictions.model == row.model) & (predictions.horizon_s == row.horizon_s)]
        rmse = np.sqrt(np.mean((p.actual_bps - p.predicted_bps) ** 2))
        if len(p) != row.n or not np.isclose(rmse, row.rmse_bps, rtol=1e-8, atol=1e-9):
            raise ValueError("audit failed: forecast metric mismatch")
    result = {"status": "passed", "checks": checks, "prediction_rows": len(predictions),
              "input_sha256": summary["input_sha256"]}
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    return result
