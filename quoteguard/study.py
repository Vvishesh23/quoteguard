"""Reproducible pilot study: causal features, purged validation and uncertainty."""
from __future__ import annotations
from itertools import product
import hashlib
import json
import platform
from . import __version__
from pathlib import Path
from .plotting import plt
import numpy as np
import pandas as pd
from .analysis import analyze_events
from .evaluation import expanding_evaluation, summarize_predictions, time_block_interval
from .events import load_events, utc_ns
from .sampling import sample_features


def evaluate(samples: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    parts = [expanding_evaluation(samples, horizon) for horizon in (1, 5)]
    return tuple(pd.concat([part[i] for part in parts], ignore_index=True) for i in range(3))


def table(frame: pd.DataFrame, columns: list[str]) -> list[str]:
    lines = ["| " + " | ".join(columns) + " |", "| " + " | ".join("---" for _ in columns) + " |"]
    for _, row in frame.iterrows():
        cells = []
        for col in columns:
            value = row[col]
            cells.append("NA" if pd.isna(value) else f"{value:.6g}" if isinstance(value, (float, np.floating)) else str(value))
        lines.append("| " + " | ".join(cells) + " |")
    return lines


def build_study(path: Path, out: Path, *, sensitivity: bool = True) -> dict:
    events, quality = load_events(path)
    if not events:
        raise ValueError("no valid events for study")
    samples, coverage = sample_features(events)
    predictions, splits, coefficients = evaluate(samples)
    metrics, comparisons = summarize_predictions(predictions)
    block_sensitivity = pd.concat(
        [summarize_predictions(predictions, block_s=length)[1] for length in (10, 30, 60)],
        ignore_index=True)
    if predictions.empty:
        raise ValueError("insufficient eligible observations for chronological study; record a longer session")
    _, trades, _ = analyze_events(events)
    markouts = []
    for sign, group in trades.groupby("sign"):
        for horizon in (1, 5):
            values = group[f"markout_bps_{horizon}s"].to_numpy()
            markouts.append({"side": "buy" if sign == 1 else "sell", "horizon_s": horizon,
                             **time_block_interval(group.recv_ns.to_numpy(), values)})
    markouts = pd.DataFrame(markouts)
    sweep = []
    if sensitivity:
        for interval, stale, tolerance in product((1., 2.), (.25, 1.), (.1, .5)):
            alternate, counts = sample_features(events, interval_s=interval, stale_s=stale, tolerance_s=tolerance)
            p, _, _ = evaluate(alternate)
            m, _ = summarize_predictions(p)
            for _, row in m[m.model.isin(["zero", "combined"])].iterrows() if len(m) else []:
                sweep.append({"interval_s": interval, "stale_s": stale, "tolerance_s": tolerance,
                              "eligible_features": counts["eligible_features"], **row.to_dict()})
    sweep = pd.DataFrame(sweep)
    source = events[0]["source"]
    label = "SYNTHETIC" if source == "synthetic" else "BINANCE PUBLIC CAPTURE"
    frame = pd.DataFrame(events)
    q = frame[frame.kind == "quote"]
    gaps = np.diff(q.recv_ns.to_numpy(dtype=np.int64)) / 1e6
    trade_lag = frame[frame.kind == "trade"]
    lag = trade_lag.recv_ns.to_numpy(dtype=np.int64) / 1e6 - trade_lag.exchange_event_ms.to_numpy(dtype=float)
    connection_meta = path.with_suffix(path.suffix + ".meta.json")
    metadata = json.loads(connection_meta.read_text()) if connection_meta.exists() else None
    summary = {"source": source, "label": label, "symbol": str(frame.symbol.iloc[0]),
               "input_sha256": hashlib.sha256(path.read_bytes()).hexdigest(), **quality,
               "quotes": int((frame.kind == "quote").sum()), "trades": int((frame.kind == "trade").sum()),
               "window_start_utc": utc_ns(frame.recv_ns.iloc[0]), "window_end_utc": utc_ns(frame.recv_ns.iloc[-1]),
               "duration_s": (int(frame.recv_ns.iloc[-1]) - int(frame.recv_ns.iloc[0])) / 1e9,
               "sampling": coverage, "ridge_alpha": 10, "embargo_s": 1,
               "runtime": {"python": platform.python_version(), "numpy": np.__version__, "pandas": pd.__version__, "quoteguard": __version__},
               "bootstrap": {"block_s": 30, "resamples": 1000, "seed": 17, "minimum_blocks": 8},
               "connections_in_events": int(frame.connection_id.nunique()),
               "quote_gap_ms": {"median": float(np.median(gaps)) if len(gaps) else None,
                                "p99": float(np.quantile(gaps, .99)) if len(gaps) else None,
                                "maximum": float(gaps.max()) if len(gaps) else None},
               "trade_receipt_minus_exchange_event_ms": {
                   "median": float(np.median(lag)) if len(lag) else None,
                   "p99": float(np.quantile(lag, .99)) if len(lag) else None},
               "trade_receipt_gap_diagnostics": {
                   "above_1s": int((lag > 1000).sum()), "above_5s": int((lag > 5000).sum()),
                   "negative": int((lag < 0).sum())},
               "capture_metadata": metadata, "protocol": "RESEARCH_PROTOCOL.md",
               "oos_rows_by_horizon": {str(h): int(len(group) // group.model.nunique())
                                        for h, group in predictions.groupby("horizon_s")}}
    out.mkdir(parents=True, exist_ok=True)
    for name, data in (("samples", samples), ("predictions", predictions), ("splits", splits),
                       ("coefficients", coefficients), ("metrics", metrics), ("paired_intervals", comparisons),
                       ("markout_intervals", markouts), ("block_sensitivity", block_sensitivity), ("sensitivity", sweep)):
        data.to_csv(out / f"{name}.csv", index=False, float_format="%.10g")
    (out / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True, allow_nan=False) + "\n")
    draw_study(out, label, metrics, comparisons, markouts)
    write_study(out, summary, metrics, comparisons, markouts, sweep, splits, block_sensitivity)
    return summary


def draw_study(out: Path, label: str, metrics: pd.DataFrame,
               comparisons: pd.DataFrame, markouts: pd.DataFrame) -> None:
    plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False})
    fig, axes = plt.subplots(2, 2, figsize=(13, 9), layout="constrained")
    order = ["zero", "train_mean", "lag_persistence", "imbalance", "book", "trade", "combined"]
    for horizon, axis in zip((1, 5), axes[0]):
        data = metrics[metrics.horizon_s == horizon].set_index("model").reindex(order)
        axis.barh(data.index, data.rmse_bps, color=["#de9445" if name == "combined" else "#225e83" for name in data.index])
        axis.invert_yaxis()
        axis.set(title=f"{horizon}s chronological out-of-sample error", xlabel="RMSE (bps); lower is better")
    axis = axes[1, 0]
    for i, (_, row) in enumerate(comparisons.iterrows()):
        name = str(row.comparison).replace("_minus_combined_squared_error", "")
        axis.plot(row["mean"], i, "o", color="#225e83")
        if pd.notna(row.ci_low):
            axis.hlines(i, row.ci_low, row.ci_high, color="#225e83")
    axis.set(yticks=range(len(comparisons)),
             yticklabels=[f"{int(row.horizon_s)}s: {str(row.comparison).replace('_minus_combined_squared_error', '')}" for _, row in comparisons.iterrows()],
             xlabel="Baseline − combined squared error (bps²)", title="Exploratory 95% time-block intervals")
    axis.axvline(0, color="gray", lw=.8)
    axis = axes[1, 1]
    for i, (_, row) in enumerate(markouts.iterrows()):
        axis.plot(row["mean"], i, "o", color="#de9445")
        if pd.notna(row.ci_low):
            axis.hlines(i, row.ci_low, row.ci_high, color="#de9445")
    axis.set(yticks=range(len(markouts)), yticklabels=[f"{row.side}, {int(row.horizon_s)}s" for _, row in markouts.iterrows()],
             xlabel="Mean signed midprice markout (bps)", title="Trade-conditioned markouts; no inferred fills")
    axis.axvline(0, color="gray", lw=.8)
    fig.suptitle(f"QuoteGuard research study | {label}\nSingle-session pilot; no execution or alpha-validation claim", fontsize=14)
    fig.savefig(out / "study.png", dpi=150, metadata={"Software": "QuoteGuard"})
    plt.close(fig)


def write_study(out: Path, summary: dict, metrics: pd.DataFrame, comparisons: pd.DataFrame,
                markouts: pd.DataFrame, sweep: pd.DataFrame, splits: pd.DataFrame, block_sensitivity: pd.DataFrame) -> None:
    lines = [f"# QuoteGuard — chronological research study ({summary['label']})", "",
        f"Symbol: **{summary['symbol']}**. Source: `{summary['source']}`. "
        f"Input SHA-256: `{summary['input_sha256']}`.", "",
        f"UTC window: {summary['window_start_utc']} to {summary['window_end_utc']} "
        f"({summary['duration_s']:.2f}s). Valid records: {summary['valid_records']:,}/{summary['raw_records']:,}; "
        f"quotes: {summary['quotes']:,}; trades: {summary['trades']:,}.", "",
        "## Findings", ""]
    for horizon in (1, 5):
        m = metrics[metrics.horizon_s == horizon].set_index("model")
        if "combined" in m.index and "zero" in m.index:
            combined, zero = m.loc["combined", "rmse_bps"], m.loc["zero", "rmse_bps"]
            direction = "lower" if combined < zero else "higher"
            lines.append(f"- At {horizon}s, the combined model's OOS RMSE was {combined:.6f} bps "
                         f"versus {zero:.6f} bps for zero return ({direction} error). "
                         "This is a single-session comparison, not evidence of durable predictability.")
    if len(comparisons) and comparisons.ci_low.notna().any():
        contains_zero = ((comparisons.ci_low <= 0) & (comparisons.ci_high >= 0)).sum()
        lines.append(f"- {int(contains_zero)} of {int(comparisons.ci_low.notna().sum())} paired forecast-improvement intervals include zero; "
                     "the reported comparisons are exploratory and provide no confirmatory improvement claim.")
    if summary["trade_receipt_minus_exchange_event_ms"]["p99"] is not None and summary["trade_receipt_minus_exchange_event_ms"]["p99"] > 1000:
        lines.append("- Delivery/clock quality is a material limitation: the 99th-percentile trade receipt-minus-exchange-event "
                     f"difference is {summary['trade_receipt_minus_exchange_event_ms']['p99'] / 1000:.2f}s. "
                     "Features and labels describe local arrival order; apparent relationships cannot be interpreted as exchange-time predictability.")
    lines += ["", "The model penalty, feature sets, split fractions and sensitivity grid were fixed in "
              "RESEARCH_PROTOCOL.md before inspecting the session outcomes. No best-performing "
              "sensitivity configuration was substituted for the baseline protocol.", "",
              "## Method", "",
              "Regular 1s receive-time grid; last available quote <=1s old. Past 1s best-quote OFI, "
              "signed aggressive volume, count, quantity imbalance, microprice edge, spread and lagged return. "
              "Future targets select the first quote at/after 1s or 5s, at most .5s late. "
              "Known reconnect boundaries invalidate carried features and targets.", "",
              "Three expanding chronological folds train on the initial 40%, 60%, and 80% of the timeline. "
              "Each tests the following 20%. Training labels must be realized strictly before "
              "test start minus a 1s embargo. Means/scales and ridge coefficients use training rows only. "
              "Alpha=10 is fixed; no shuffled split, test-time fitting or hyperparameter search is used.", "",
              "## Out-of-sample metrics", ""]
    lines += table(metrics, ["horizon_s", "model", "n", "nonflat_targets", "rmse_bps", "mae_bps", "correlation", "nonflat_directional_accuracy"])
    lines += ["", "Directional accuracy excludes flat targets; neutral predictions count as incorrect. "
              "Models are compared on the same eligible rows per horizon. These are return forecasts, "
              "without spreads, fees, inventory or execution assumptions.", "",
              "## Paired error comparison", "",
              "Positive values mean the combined model has lower squared error than the named baseline. "
              "Intervals use 1,000 bootstrap resamples of 30s time blocks. Intervals are suppressed below "
              "8 blocks, and fewer than 20 blocks are flagged as especially unstable.", ""]
    lines += table(comparisons, ["horizon_s", "comparison", "mean", "ci_low", "ci_high", "blocks", "status"])
    lines += ["", "Block-length sensitivity (same paired errors; headline block length remains 30s):", ""]
    lines += table(block_sensitivity, ["horizon_s", "comparison", "block_s", "mean", "ci_low", "ci_high", "blocks", "status"])
    lines += ["", "## Trade-conditioned markouts", "",
              "Positive signed markouts are adverse midprice movement for a hypothetical passive counterparty. "
              "Buy/sell means use event weighting; the resampling unit is a time block, not an individual trade.", ""]
    lines += table(markouts, ["side", "horizon_s", "n", "mean", "ci_low", "ci_high", "blocks", "status"])
    lines += ["", "![Research study](study.png)", "", "## Purge audit", ""]
    lines += table(splits, ["horizon_s", "fold", "train_rows", "test_rows", "purged_rows", "status"])
    lines += ["", "Exact nanosecond cutoff and latest training-label timestamps are in splits.csv; "
              "train-only scaling and model coefficients are in coefficients.csv. OOS predictions "
              "retain timestamps and folds for independent error recomputation.", "", "## Sensitivity grid", ""]
    if len(sweep):
        lines += table(sweep, ["interval_s", "stale_s", "tolerance_s", "horizon_s", "model", "n", "rmse_bps"])
    else:
        lines += ["Not requested for this run."]
    lines += ["", "## Data quality and limits", "",
              f"Sampling coverage: `{json.dumps(summary['sampling'], sort_keys=True)}`.",
              f"Quote interarrival gaps (ms): `{json.dumps(summary['quote_gap_ms'], sort_keys=True)}`.",
              f"Receipt-gap diagnostic counts: `{json.dumps(summary['trade_receipt_gap_diagnostics'], sort_keys=True)}`.",
              f"Receipt minus exchange-event time (ms): `{json.dumps(summary['trade_receipt_minus_exchange_event_ms'], sort_keys=True)}`.", "",
              "Receipt-minus-exchange differences combine clock offset, venue timestamp semantics, transport "
              "and application scheduling; they are not calibrated latency benchmarks. Quote receipt times "
              "do not reveal exchange quote event times. Rejected-record counts describe parser validity, "
              "not proof that no messages were lost upstream.", "",
              "Regular sampling reduces update-intensity weighting but does not make observations independent. "
              "Overlapping targets, repeated quotes, clustered activity and shared training histories remain. "
              "The block bootstrap assumes blocks capture enough short-range dependence; a single session "
              "has few blocks and no independent-day replication. Intervals are pointwise, unadjusted for "
              "multiple comparisons, and must not be treated as confirmatory significance tests.", "",
              "Next validation: independent sessions/days, held-out sessions, longer block-length sensitivity, "
              "venue/clock diagnostics and stability under changing market regimes. There is no strategy "
              "backtest, maker-fill model, queue position, P&L or profitability claim."]
    if summary["source"] == "synthetic":
        lines += ["", "**SYNTHETIC fixture: all results here validate software behavior only.**"]
    (out / "study.md").write_text("\n".join(lines) + "\n")
