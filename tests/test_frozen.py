import asyncio
import copy
import json
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
from quoteguard.events import load_events
from quoteguard.fixture import generate
from quoteguard.frozen import fit_artifact, load_artifact, frozen_predictions, fingerprint
from quoteguard.holdout import run_holdout
from quoteguard.quality import receipt_quality
from quoteguard.sampling import sample_features


def sessions(tmp_path):
    train, test = tmp_path / "train.jsonl", tmp_path / "test.jsonl"
    generate(train, steps=1200)
    generate(test, seed=44, steps=1800)
    # Shift only the synthetic recording clocks, preserving a coherent later session.
    records = []
    for line in test.read_text().splitlines():
        row = json.loads(line)
        row["recv_ns"] += 300000000000
        from quoteguard.events import utc_ns
        row["recv_utc"] = utc_ns(row["recv_ns"])
        raw = json.loads(row["raw"])
        if raw["data"].get("e") == "trade":
            raw["data"]["E"] += 300000
            raw["data"]["T"] += 300000
        row["raw"] = json.dumps(raw)
        records.append(json.dumps(row))
    test.write_text("\n".join(records) + "\n")
    model = tmp_path / "model.json"
    artifact = fit_artifact(train, model)
    return train, test, model, artifact


def test_frozen_model_roundtrip_exclusive_write_and_determinism(tmp_path):
    train, test, model, artifact = sessions(tmp_path)
    assert load_artifact(model) == artifact
    other = fit_artifact(train, tmp_path / "other.json")
    assert other == artifact
    with pytest.raises(FileExistsError):
        fit_artifact(train, model)
    assert "pickle" not in model.read_text()
    _, predictions, drift, metadata = frozen_predictions(load_artifact(model), load_events(test)[0])
    assert predictions.groupby(["model", "horizon_s"]).size().groupby("horizon_s").nunique().eq(1).all()
    assert not drift.empty and metadata["transport"]["timing_gate_passed"]


def test_holdout_never_fits_or_mutates_training_state(tmp_path, monkeypatch):
    import quoteguard.frozen as module
    _, test, model, artifact = sessions(tmp_path)
    before = model.read_bytes()
    def forbidden(*args, **kwargs):
        raise AssertionError("test session attempted to train")
    monkeypatch.setattr(module, "fit_ridge", forbidden)
    rows = load_events(test)[0]
    _, a, _, _ = frozen_predictions(artifact, rows)
    changed = [dict(row) for row in rows]
    for row in changed:
        if row["kind"] == "quote":
            row["bid"] += 1000
            row["ask"] += 1000
    frozen_predictions(artifact, changed)
    assert model.read_bytes() == before
    assert not a.empty


@pytest.mark.parametrize("change", ["overlap", "source", "symbol", "embargo"])
def test_holdout_rejects_invalid_session_boundaries(tmp_path, change):
    train, test, model, artifact = sessions(tmp_path)
    rows = load_events(test)[0]
    if change == "overlap":
        rows = load_events(train)[0]
    elif change in ("source", "symbol"):
        rows[0][change] = "binance_public" if change == "source" else "ETHUSDT"
    else:
        rows[0]["recv_ns"] = artifact["payload"]["training_last_recv_ns"] + 1000000000
    with pytest.raises(ValueError):
        frozen_predictions(artifact, rows)


@pytest.mark.parametrize("change", ["fingerprint", "feature", "scale", "nan", "shape", "extra_model", "schema"])
def test_corrupt_models_rejected_without_unsafe_deserialization(tmp_path, change):
    _, _, model, artifact = sessions(tmp_path)
    altered = copy.deepcopy(artifact)
    state = altered["payload"]["horizons"]["1"]["models"]["combined"]
    if change == "fingerprint":
        state["intercept"] += 1
    elif change == "feature":
        state["features"][0] = "future_mid_1s"
    elif change == "scale":
        state["scales"][0] = 0
    elif change == "nan":
        state["means"][0] = float("nan")
    elif change == "shape":
        state["coefficients"].pop()
    elif change == "extra_model":
        altered["payload"]["horizons"]["1"]["models"]["surprise"] = state
    else:
        altered["payload"]["schema_version"] = 99
    if change not in ("fingerprint", "nan"):
        altered["artifact_id"] = fingerprint(altered["payload"])
    model.write_text(json.dumps(altered))
    with pytest.raises(ValueError):
        load_artifact(model)


def test_quality_mask_uses_only_already_received_trades(tmp_path):
    _, test, _, _ = sessions(tmp_path)
    rows = load_events(test)[0]
    samples, _ = sample_features(rows)
    tick = int(samples.recv_ns.iloc[10])
    for row in rows:
        if row["kind"] == "trade" and row["recv_ns"] > tick:
            row["exchange_event_ms"] -= 3000
    result, diagnostics = receipt_quality(rows, samples)
    assert result.loc[result.recv_ns <= tick, "receipt_quality_ok"].all()
    assert not result.loc[result.recv_ns > tick + 1000000000, "receipt_quality_ok"].all()
    assert not diagnostics["timing_gate_passed"]


def test_quality_threshold_boundary_and_no_trade_window(tmp_path):
    _, test, _, _ = sessions(tmp_path)
    rows = load_events(test)[0]
    samples, _ = sample_features(rows)
    trades = [row for row in rows if row["kind"] == "trade"]
    for row in trades:
        row["exchange_event_ms"] = row["recv_ns"] // 1000000 - 1000
    _, diagnostics = receipt_quality(rows, samples)
    assert diagnostics["trades_above_1s"] == 0
    assert diagnostics["timing_gate_passed"]
    quotes_only = [row for row in rows if row["kind"] == "quote"]
    grid, _ = sample_features(quotes_only)
    result, diagnostics = receipt_quality(quotes_only, grid)
    assert result.receipt_quality_ok.all() and not diagnostics["timing_gate_passed"]


def test_frozen_training_only_baselines_are_constant_on_test(tmp_path):
    _, test, _, artifact = sessions(tmp_path)
    _, predictions, _, _ = frozen_predictions(artifact, load_events(test)[0])
    for horizon in (1, 5):
        rows = predictions[(predictions.horizon_s == horizon) & (predictions.model == "train_mean")]
        assert rows.predicted_bps.nunique() == 1
        assert rows.predicted_bps.iloc[0] == artifact["payload"]["horizons"][str(horizon)]["train_mean_bps"]


def test_holdout_report_reproducibility_and_visible_quality(tmp_path):
    _, test, model, _ = sessions(tmp_path)
    a, b = tmp_path / "a", tmp_path / "b"
    summary = run_holdout(model, test, a)
    run_holdout(model, test, b)
    assert summary["refit_on_test"] is False
    for name in ["summary.json", "metrics.csv", "feature_drift.csv", "predictions.csv", "holdout.md", "holdout.png"]:
        assert (a / name).read_bytes() == (b / name).read_bytes()
    from quoteguard.holdout import audit_holdout
    assert audit_holdout(model, test, a, a / "audit.json")["status"] == "passed"
    corrupted = pd.read_csv(a / "predictions.csv")
    corrupted.loc[0, "predicted_bps"] += 1
    corrupted.to_csv(a / "predictions.csv", index=False)
    with pytest.raises(ValueError, match="frozen prediction"):
        audit_holdout(model, test, a, a / "bad-audit.json")
    text = (a / "holdout.md").read_text()
    assert "SYNTHETIC" in text and "Transport timing gate" in text


def test_one_command_offline_frozen_demo_is_idempotent(tmp_path):
    from quoteguard.holdout import frozen_demo
    out = tmp_path / "demo"
    a = frozen_demo(out)
    before = {name: (out / name).read_bytes() for name in ("model.json", "summary.json", "audit.json", "holdout.png")}
    b = frozen_demo(out)
    assert a == b and a["source"] == "synthetic"
    for name, content in before.items():
        assert (out / name).read_bytes() == content


def test_holdout_audit_rejects_duplicate_forecasts(tmp_path):
    from quoteguard.holdout import audit_holdout
    _, test, model, _ = sessions(tmp_path)
    out = tmp_path / "result"
    run_holdout(model, test, out)
    rows = pd.read_csv(out / "predictions.csv")
    pd.concat([rows, rows.iloc[:1]], ignore_index=True).to_csv(out / "predictions.csv", index=False)
    with pytest.raises(ValueError, match="duplicate"):
        audit_holdout(model, test, out, out / "bad.json")
