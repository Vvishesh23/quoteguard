"""Purged expanding-window ridge forecasts and time-block uncertainty."""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np
import pandas as pd
from .sampling import FEATURE_SETS


@dataclass
class RidgeModel:
    features: list[str]
    means: np.ndarray
    scales: np.ndarray
    coefficients: np.ndarray
    intercept: float

    def predict(self, frame: pd.DataFrame) -> np.ndarray:
        return ((frame[self.features].to_numpy(dtype=float) - self.means) / self.scales) @ self.coefficients + self.intercept


def fit_ridge(train: pd.DataFrame, target: str, features: list[str], alpha: float = 10) -> RidgeModel:
    if not np.isfinite(alpha) or alpha <= 0:
        raise ValueError("ridge penalty must be positive")
    x, y = train[features].to_numpy(dtype=float), train[target].to_numpy(dtype=float)
    means, scales = x.mean(axis=0), x.std(axis=0)
    scales[scales < 1e-12] = 1
    z = (x - means) / scales
    intercept = float(y.mean())
    coefficients = np.linalg.solve(z.T @ z + alpha * np.eye(len(features)), z.T @ (y - intercept))
    return RidgeModel(features, means, scales, coefficients, intercept)


def regression_metrics(y: np.ndarray, prediction: np.ndarray) -> dict:
    error = prediction - y
    nonflat = y != 0
    correlation = float(np.corrcoef(y, prediction)[0, 1]) if np.std(y) > 0 and np.std(prediction) > 1e-12 else None
    baseline_mse = float(np.mean(y ** 2))
    return {"n": len(y), "rmse_bps": float(np.sqrt(np.mean(error ** 2))),
            "mae_bps": float(np.mean(np.abs(error))), "correlation": correlation,
            "r2_vs_zero": float(1 - np.mean(error ** 2) / baseline_mse) if baseline_mse > 0 else None,
            "nonflat_targets": int(nonflat.sum()),
            "nonflat_directional_accuracy": float(np.mean(np.sign(prediction[nonflat]) == np.sign(y[nonflat]))) if nonflat.any() else None}


def expanding_evaluation(samples: pd.DataFrame, horizon: int, alpha: float = 10,
                         embargo_s: float = 1, min_train: int = 20) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    target, realized = f"forward_bps_{horizon}s", f"target_recv_ns_{horizon}s"
    features = FEATURE_SETS["combined"]
    prediction_rows, split_rows, coefficient_rows = [], [], []
    n = len(samples)
    # Boundaries refer to the full regular timeline, before eligibility filtering.
    boundaries = [int(n * fraction) for fraction in (.4, .6, .8, 1)]
    for fold, (begin, end) in enumerate(zip(boundaries[:-1], boundaries[1:]), 1):
        if begin >= n or end <= begin:
            continue
        test_start_ns = int(samples.recv_ns.iloc[begin])
        cutoff = test_start_ns - round(embargo_s * 1e9)
        original_train = samples.iloc[:begin]
        usable_train = original_train.dropna(subset=features + [target, realized])
        train = usable_train[usable_train[realized] < cutoff]
        test = samples.iloc[begin:end].dropna(subset=features + [target, realized])
        split = {"horizon_s": horizon, "fold": fold, "test_start_ns": test_start_ns,
                 "test_end_ns": int(samples.recv_ns.iloc[end - 1]), "purge_cutoff_ns": cutoff, "train_rows": len(train), "test_rows": len(test),
                 "purged_rows": len(usable_train) - len(train), "embargo_s": embargo_s,
                 "max_train_target_ns": int(train[realized].max()) if len(train) else None,
                 "status": "ok" if len(train) >= min_train and len(test) else "insufficient_data"}
        split_rows.append(split)
        if split["status"] != "ok":
            continue
        assert int(train[realized].max()) < cutoff
        base = pd.DataFrame({"recv_ns": test.recv_ns.to_numpy(), "fold": fold, "horizon_s": horizon,
                             "actual_bps": test[target].to_numpy()})
        outputs = {"zero": np.zeros(len(test)), "train_mean": np.full(len(test), train[target].mean()),
                   "lag_persistence": test.lag_return_bps.to_numpy()}
        for name, columns in FEATURE_SETS.items():
            model = fit_ridge(train, target, columns, alpha)
            outputs[name] = model.predict(test)
            for feature, mean, scale, coefficient in zip(columns, model.means, model.scales, model.coefficients):
                coefficient_rows.append({"fold": fold, "horizon_s": horizon, "model": name,
                    "feature": feature, "train_mean": mean, "train_scale": scale,
                    "coefficient_per_train_std_bps": coefficient, "intercept_bps": model.intercept,
                    "alpha": alpha})
        for name, predicted in outputs.items():
            rows = base.copy()
            rows["model"], rows["predicted_bps"] = name, predicted
            prediction_rows.append(rows)
    predictions = pd.concat(prediction_rows, ignore_index=True) if prediction_rows else pd.DataFrame()
    return predictions, pd.DataFrame(split_rows), pd.DataFrame(coefficient_rows)


def time_block_interval(times_ns: np.ndarray, values: np.ndarray, *, block_s: float = 30,
                         resamples: int = 1000, seed: int = 17, min_blocks: int = 8) -> dict:
    """Bootstrap nonoverlapping time-block sums/counts, retaining event weighting."""
    if block_s <= 0 or not np.isfinite(block_s) or resamples < 1:
        raise ValueError("invalid bootstrap parameters")
    keep = np.isfinite(values)
    times, values = np.asarray(times_ns, dtype=np.int64)[keep], np.asarray(values, dtype=float)[keep]
    if not len(values):
        return {"n": 0, "blocks": 0, "mean": None, "ci_low": None, "ci_high": None, "status": "empty"}
    group = (times - times.min()) // round(block_s * 1e9)
    _, inverse = np.unique(group, return_inverse=True)
    counts, sums = np.bincount(inverse), np.bincount(inverse, weights=values)
    nblocks = len(counts)
    result = {"n": len(values), "blocks": nblocks, "mean": float(values.mean()),
              "ci_low": None, "ci_high": None, "block_s": block_s, "resamples": resamples,
              "status": "insufficient_blocks" if nblocks < min_blocks else "exploratory"}
    if nblocks >= min_blocks:
        rng = np.random.default_rng(seed)
        estimates = np.empty(resamples)
        for i in range(resamples):
            selected = rng.integers(0, nblocks, size=nblocks)
            estimates[i] = sums[selected].sum() / counts[selected].sum()
        result["ci_low"], result["ci_high"] = map(float, np.quantile(estimates, [.025, .975]))
        if nblocks < 20:
            result["status"] = "few_blocks_exploratory"
    return result


def summarize_predictions(predictions: pd.DataFrame, block_s: float = 30) -> tuple[pd.DataFrame, pd.DataFrame]:
    metrics, paired = [], []
    if predictions.empty:
        return pd.DataFrame(), pd.DataFrame()
    for (horizon, name), frame in predictions.groupby(["horizon_s", "model"], sort=True):
        metrics.append({"horizon_s": horizon, "model": name,
                        **regression_metrics(frame.actual_bps.to_numpy(), frame.predicted_bps.to_numpy())})
    for horizon, frame in predictions.groupby("horizon_s"):
        matrix = frame.pivot(index="recv_ns", columns="model", values="predicted_bps")
        y = frame.drop_duplicates("recv_ns").set_index("recv_ns").actual_bps.reindex(matrix.index).to_numpy()
        for baseline in ("zero", "train_mean", "imbalance"):
            improvement = (matrix[baseline].to_numpy() - y) ** 2 - (matrix.combined.to_numpy() - y) ** 2
            paired.append({"horizon_s": horizon, "comparison": f"{baseline}_minus_combined_squared_error",
                           "units": "bps_squared", **time_block_interval(matrix.index.to_numpy(), improvement, block_s=block_s)})
    return pd.DataFrame(metrics), pd.DataFrame(paired)
