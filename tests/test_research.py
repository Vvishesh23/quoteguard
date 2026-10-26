from dataclasses import asdict
import json
import numpy as np
import pandas as pd
import pytest
from quoteguard.events import BinanceAdapter, Event, load_events
from quoteguard.analysis import analyze_events
from quoteguard.sampling import sample_features, trailing_sum, level1_ofi, FEATURE_SETS
from quoteguard.evaluation import (fit_ridge, expanding_evaluation, regression_metrics,
                                  time_block_interval, summarize_predictions)
from quoteguard.fixture import generate
from quoteguard.study import build_study
from test_events import quote, trade, record, BASE
from test_analysis import events


def test_trailing_window_excludes_future_and_left_boundary():
    times = np.array([0, 1, 2, 3], dtype=np.int64)
    result = trailing_sum(times, np.array([2., 3., 5., 100.]), np.array([1, 2]), 1)
    assert result.tolist() == [3., 5.]


def test_ofi_price_and_quantity_transitions():
    q = pd.DataFrame(dict(bid=[100, 100, 101, 99], ask=[102, 102, 103, 101],
                          bid_qty=[3, 5, 4, 1], ask_qty=[1, 2, 3, 4], connection_id=[1, 1, 1, 1]))
    assert level1_ofi(q).tolist() == [0, 1, 6, -8]
    q.loc[2:, "connection_id"] = 2
    assert level1_ofi(q).tolist() == [0, 1, 0, -8]


def test_sampler_uses_only_available_quotes_and_trade_flow():
    rows = [(0, quote()), (.2, trade(tid=1)), (.5, quote(2)),
            (.8, trade(maker=True, tid=2)), (1.01, quote(3, b="110", a="112")),
            (2, quote(4, b="120", a="122"))]
    samples, counts = sample_features(events(rows))
    at_one = samples[samples.recv_ns == BASE + 1000000000].iloc[0]
    assert at_one.mid == 101  # The 1.01s quote cannot enter the 1s snapshot.
    assert at_one.trade_count == 2
    assert at_one.trade_flow_imbalance == 0
    assert at_one.quote_age_ms == 500
    strict, _ = sample_features(events(rows), stale_s=.25)
    assert not strict[strict.recv_ns == BASE + 1000000000].feature_eligible.iloc[0]


def test_feature_mutation_invariance(tmp_path):
    path = tmp_path / "synthetic.jsonl"
    generate(path, steps=70)
    original, _ = load_events(path)
    changed = [dict(e) for e in original]
    for e in changed:
        if e["recv_ns"] > BASE + 4000000000:
            e["bid"], e["ask"], e["qty"], e["bid_qty"] = 200000, 200001, 100, 100
    a, _ = sample_features(original)
    b, _ = sample_features(changed)
    before = a.recv_ns <= BASE + 4000000000
    pd.testing.assert_frame_equal(a.loc[before, FEATURE_SETS["combined"]], b.loc[before, FEATURE_SETS["combined"]])


def test_connection_boundaries_prevent_markouts_and_asof_carry():
    rows = events([(0, quote()), (.1, trade()), (1.1, quote(2, b="110", a="112")),
                   (1.2, trade(tid=2)), (2.1, quote(3, b="120", a="122"))])
    rows[2]["connection_id"] = 2
    rows[3]["connection_id"] = 3  # No quote for this connection yet.
    rows[4]["connection_id"] = 3
    q, t, _ = analyze_events(rows)
    assert np.isnan(q.future_mid_1s.iloc[0])
    assert np.isnan(t.markout_bps_1s.iloc[0])
    assert not t.quote_eligible.iloc[1]


def test_sampler_warmup_resets_on_reconnect():
    rows = events([(0, quote()), (1, quote(2)), (2, quote(3)), (3, quote(4)), (4, quote(5))])
    for e in rows[2:]:
        e["connection_id"] = 1
    sample, _ = sample_features(rows)
    assert not sample.feature_eligible.iloc[2]
    assert sample.feature_eligible.iloc[3]


def test_train_only_standardization_and_known_ridge():
    train = pd.DataFrame({"x": np.arange(100.), "target": 3 * np.arange(100.) + 2})
    fit = fit_ridge(train, "target", ["x"], alpha=1e-8)
    assert fit.means[0] == 49.5
    assert fit.predict(pd.DataFrame({"x": [150.]}))[0] == pytest.approx(452)
    assert fit.means[0] == 49.5  # Predict does not fit on the test row.


def research_samples(n=300):
    t = BASE + np.arange(n, dtype=np.int64) * 1000000000
    rng = np.random.default_rng(4)
    frame = pd.DataFrame({name: rng.normal(size=n) for name in FEATURE_SETS["combined"]})
    frame["recv_ns"] = t
    for h in (1, 5):
        frame[f"forward_bps_{h}s"] = .5 * frame.imbalance + rng.normal(scale=.1, size=n)
        frame[f"target_recv_ns_{h}s"] = t + h * 1000000000 + 100000000
    return frame


def test_purging_uses_actual_realization_and_embargo():
    frame = research_samples()
    _, splits, _ = expanding_evaluation(frame, 5)
    assert (splits.max_train_target_ns < splits.purge_cutoff_ns).all()
    assert (splits.purged_rows >= 6).all()
    # Making first-fold test features/labels extreme cannot alter its training coefficients.
    _, _, original = expanding_evaluation(frame, 5)
    changed = frame.copy()
    changed.loc[120:179, FEATURE_SETS["combined"]] += 10000
    changed.loc[120:179, "forward_bps_5s"] = 10000
    _, _, altered = expanding_evaluation(changed, 5)
    pd.testing.assert_frame_equal(original[original.fold == 1], altered[altered.fold == 1])


def test_out_of_sample_predictions_and_baselines():
    pred, splits, coefficients = expanding_evaluation(research_samples(), 1)
    assert pred.recv_ns.min() == BASE + 120000000000
    assert pred.groupby("model").size().nunique() == 1
    metrics, paired = summarize_predictions(pred)
    assert metrics.set_index("model").loc["imbalance", "rmse_bps"] < metrics.set_index("model").loc["zero", "rmse_bps"]
    assert set(paired.comparison) == {f"{b}_minus_combined_squared_error" for b in ("zero", "train_mean", "imbalance")}


def test_bootstrap_determinism_and_insufficient_blocks():
    times = np.arange(600, dtype=np.int64) * 1000000000
    values = np.repeat(np.tile([-1., 1.], 10), 30)
    a = time_block_interval(times, values)
    b = time_block_interval(times, values)
    assert a == b and a["blocks"] == 20
    assert a["ci_low"] <= 0 <= a["ci_high"]
    naive = time_block_interval(times, values, block_s=1)
    assert a["ci_high"] - a["ci_low"] > naive["ci_high"] - naive["ci_low"]
    short = time_block_interval(times[:10], values[:10])
    assert short["status"] == "insufficient_blocks" and short["ci_low"] is None


def test_metrics_flat_targets_and_neutral_predictions():
    m = regression_metrics(np.array([0., 1., -1.]), np.zeros(3))
    assert m["nonflat_targets"] == 2 and m["nonflat_directional_accuracy"] == 0
    assert m["correlation"] is None


def test_swappable_event_adapter(tmp_path):
    path = tmp_path / "alternate.jsonl"
    path.write_text('{"price":100}\n')
    class Adapter:
        def parse(self, record, sequence):
            return Event(kind="quote", symbol="BTCUSDT", recv_ns=BASE, mono_ns=1,
                         sequence=sequence, source="synthetic", event_id=1,
                         bid=record["price"], ask=101, bid_qty=1, ask_qty=1)
    parsed, quality = load_events(path, adapter=Adapter())
    assert parsed[0]["bid"] == 100 and quality["valid_fraction"] == 1


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -1])
def test_invalid_sampling_parameters(value):
    with pytest.raises(ValueError):
        sample_features(events([(0, quote())]), interval_s=value)


def test_study_artifacts_and_reproducibility(tmp_path):
    path = tmp_path / "fixture.jsonl"
    generate(path)
    a, b = tmp_path / "one", tmp_path / "two"
    summary = build_study(path, a, sensitivity=False)
    build_study(path, b, sensitivity=False)
    assert summary["source"] == "synthetic"
    for name in ["summary.json", "study.md", "metrics.csv", "predictions.csv", "splits.csv",
                 "coefficients.csv", "paired_intervals.csv", "markout_intervals.csv", "study.png"]:
        assert (a / name).read_bytes() == (b / name).read_bytes()
    from quoteguard.audit import audit_study
    assert audit_study(path, a, a / "audit.json")["status"] == "passed"
    corrupted = pd.read_csv(a / "predictions.csv")
    corrupted.loc[0, "predicted_bps"] += 100
    corrupted.to_csv(a / "predictions.csv", index=False)
    with pytest.raises(ValueError, match="metric mismatch"):
        audit_study(path, a, a / "corrupt-audit.json")
    text = (a / "study.md").read_text()
    assert "SYNTHETIC" in text and "purge" in text.lower()


def test_study_rejects_insufficient_sample(tmp_path):
    path = tmp_path / "tiny.jsonl"
    generate(path, steps=10)
    with pytest.raises(ValueError, match="insufficient"):
        build_study(path, tmp_path / "out")


def test_verified_tls_contexts_keep_hostname_and_chain_verification():
    import ssl
    from quoteguard.collector import verified_context
    context = verified_context()
    assert context.check_hostname and context.verify_mode == ssl.CERT_REQUIRED
    pytest.importorskip("truststore")
    native = verified_context(system_trust=True)
    assert native.check_hostname and native.verify_mode == ssl.CERT_REQUIRED
