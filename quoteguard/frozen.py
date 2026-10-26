"""Plain-JSON, fingerprinted frozen models and strictly later-session inference."""
from __future__ import annotations
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
from . import __version__
from .evaluation import RidgeModel, fit_ridge, summarize_predictions
from .events import load_events, utc_ns
from .quality import receipt_quality
from .sampling import FEATURE_SETS, sample_features

PARAMETERS = {"interval_s": 1, "stale_s": 1, "tolerance_s": .5, "lookback_s": 1}


def fingerprint(payload: dict) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def fit_artifact(input_path: Path, out: Path) -> dict:
    events, quality = load_events(input_path)
    samples, coverage = sample_features(events, **PARAMETERS)
    samples, transport = receipt_quality(events, samples)
    payload = {"schema_version": 1, "software_version": __version__, "parameters": PARAMETERS.copy(),
               "alpha": 10, "embargo_s": 1, "source": events[0]["source"], "symbol": events[0]["symbol"],
               "training_input_sha256": hashlib.sha256(input_path.read_bytes()).hexdigest(),
               "training_first_recv_ns": events[0]["recv_ns"], "training_last_recv_ns": events[-1]["recv_ns"],
               "training_quality": quality, "training_transport": transport, "coverage": coverage,
               "horizons": {}}
    for horizon in (1, 5):
        target = f"forward_bps_{horizon}s"
        train = samples.dropna(subset=FEATURE_SETS["combined"] + [target])
        if len(train) < 20:
            raise ValueError("at least 20 eligible training rows per horizon required")
        models = {}
        for name, features in FEATURE_SETS.items():
            model = fit_ridge(train, target, features)
            models[name] = {key: value.tolist() if isinstance(value, np.ndarray) else value
                            for key, value in asdict(model).items()}
        payload["horizons"][str(horizon)] = {"n_train": len(train), "train_mean_bps": float(train[target].mean()),
            "max_training_target_ns": int(train[f"target_recv_ns_{horizon}s"].max()), "models": models}
    artifact = {"artifact_id": fingerprint(payload), "payload": payload}
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("x") as handle:
        handle.write(json.dumps(artifact, sort_keys=True, indent=2, allow_nan=False) + "\n")
    return artifact


def load_artifact(path: Path) -> dict:
    try:
        artifact = json.loads(path.read_text())
        payload = artifact["payload"]
        if artifact["artifact_id"] != fingerprint(payload):
            raise ValueError("model fingerprint mismatch")
        if payload["alpha"] != 10:
            raise ValueError("unsupported ridge penalty")
        if payload["schema_version"] != 1 or payload["parameters"] != PARAMETERS:
            raise ValueError("unsupported model schema or feature parameters")
        if payload["source"] not in ("binance_public", "synthetic") or not isinstance(payload["symbol"], str):
            raise ValueError("invalid model provenance")
        if type(payload["training_last_recv_ns"]) is not int or payload["embargo_s"] != 1:
            raise ValueError("invalid training time boundary")
        for horizon in ("1", "5"):
            data = payload["horizons"][horizon]
            if not np.isfinite(data["train_mean_bps"]) or data["n_train"] < 20:
                raise ValueError("invalid fitted baseline")
            if data["max_training_target_ns"] > payload["training_last_recv_ns"]:
                raise ValueError("training target beyond recording")
            if set(data["models"]) != set(FEATURE_SETS):
                raise ValueError("model set mismatch")
            for name, features in FEATURE_SETS.items():
                model = data["models"][name]
                if model["features"] != features or not np.isfinite(model["intercept"]):
                    raise ValueError("model feature schema mismatch")
                for key in ("means", "scales", "coefficients"):
                    values = np.asarray(model[key], dtype=float)
                    if values.shape != (len(features),) or not np.isfinite(values).all():
                        raise ValueError("invalid model vector")
                if (np.asarray(model["scales"]) <= 0).any():
                    raise ValueError("nonpositive fitted scale")
        return artifact
    except (KeyError, TypeError, OverflowError, AttributeError) as exc:
        raise ValueError(f"invalid model artifact: {exc}") from exc


def frozen_predictions(artifact: dict, events: list[dict]) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    payload = artifact["payload"]
    if not events:
        raise ValueError("no held-out events")
    if any(e["source"] != payload["source"] or e["symbol"] != payload["symbol"] for e in events):
        raise ValueError("held-out source/symbol differs from training")
    boundary = payload["training_last_recv_ns"] + round(payload["embargo_s"] * 1e9)
    if events[0]["recv_ns"] <= boundary:
        raise ValueError("held-out recording overlaps training or embargo")
    samples, coverage = sample_features(events, **payload["parameters"])
    samples, transport = receipt_quality(events, samples)
    prediction_rows, drift_rows = [], []
    for horizon in (1, 5):
        target = f"forward_bps_{horizon}s"
        test = samples.dropna(subset=FEATURE_SETS["combined"] + [target])
        if not len(test):
            continue
        trained = payload["horizons"][str(horizon)]
        outputs = {"zero": np.zeros(len(test)), "train_mean": np.full(len(test), trained["train_mean_bps"]),
                   "lag_persistence": test.lag_return_bps.to_numpy()}
        for name, state in trained["models"].items():
            model = RidgeModel(state["features"], np.asarray(state["means"]), np.asarray(state["scales"]),
                               np.asarray(state["coefficients"]), state["intercept"])
            outputs[name] = model.predict(test)
            if name == "combined":
                z = (test[model.features].to_numpy() - model.means) / model.scales
                for j, feature in enumerate(model.features):
                    drift_rows.append({"horizon_s": horizon, "feature": feature, "n": len(test),
                        "mean_in_train_std": float(z[:, j].mean()), "test_std_in_train_std": float(z[:, j].std()),
                        "fraction_abs_z_above_3": float((np.abs(z[:, j]) > 3).mean()),
                        "flag_mean_shift": bool(abs(z[:, j].mean()) > 1)})
        base = pd.DataFrame({"recv_ns": test.recv_ns.to_numpy(), "horizon_s": horizon, "fold": 0,
                             "actual_bps": test[target].to_numpy(), "receipt_quality_ok": test.receipt_quality_ok.to_numpy()})
        for name, values in outputs.items():
            rows = base.copy()
            rows["model"], rows["predicted_bps"] = name, values
            prediction_rows.append(rows)
    if not prediction_rows:
        raise ValueError("no eligible held-out labels")
    predictions = pd.concat(prediction_rows, ignore_index=True)
    return samples, predictions, pd.DataFrame(drift_rows), {"coverage": coverage, "transport": transport}
