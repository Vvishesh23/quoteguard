"""Deterministic CSV, chart, and Markdown research artifacts."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
from .plotting import plt
from matplotlib.ticker import FormatStrFormatter
import numpy as np
import pandas as pd
from .analysis import analyze_events
from .events import load_events, utc_ns


def build_report(path: Path, out: Path, stale_s: float = 1, tolerance_s: float = .5) -> dict:
    events, quality = load_events(path)
    quotes, trades, counts = analyze_events(events, stale_s, tolerance_s)
    out.mkdir(parents=True, exist_ok=True)
    source = events[0]["source"]
    label = "SYNTHETIC" if source == "synthetic" else "BINANCE PUBLIC CAPTURE"
    bucketed = quotes.copy()
    bucketed["imbalance_bucket"] = pd.cut(bucketed.imbalance, [-1.000001, -.6, -.2, .2, .6, 1.000001],
                                          labels=["[-1,-.6]", "(-.6,-.2]", "(-.2,.2]", "(.2,.6]", "(.6,1]"])
    buckets = bucketed.groupby("imbalance_bucket", observed=False).agg(
        observations=("mid", "size"), count_1s=("forward_bps_1s", "count"),
        mean_1s_bps=("forward_bps_1s", "mean"), count_5s=("forward_bps_5s", "count"),
        mean_5s_bps=("forward_bps_5s", "mean"))
    sides = trades.groupby("sign").agg(trades=("sign", "size"),
        count_1s=("markout_bps_1s", "count"), mean_1s_bps=("markout_bps_1s", "mean"),
        count_5s=("markout_bps_5s", "count"), mean_5s_bps=("markout_bps_5s", "mean"))
    coverage = {kind: {f"{h}s": int(frame[f"forward_bps_{h}s"].notna().sum()) for h in (1, 5)}
                for kind, frame in (("quote_labels", quotes), ("trade_labels", trades))}
    summary = {"source": source, "label": label, "input_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
               **quality, **counts, "window_start_utc": utc_ns(events[0]["recv_ns"]),
               "window_end_utc": utc_ns(events[-1]["recv_ns"]),
               "duration_s": (events[-1]["recv_ns"] - events[0]["recv_ns"]) / 1e9,
               "stale_quote_seconds": stale_s, "future_tolerance_seconds": tolerance_s,
               "coverage": coverage, "spread_bps": {str(k): float(v) for k, v in
                   quotes.spread_bps.quantile([0, .25, .5, .75, .95, 1]).items()}}
    (out / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True, allow_nan=False) + "\n")
    quotes.to_csv(out / "quotes.csv", index=False, float_format="%.10g")
    trades.to_csv(out / "trades.csv", index=False, float_format="%.10g")
    buckets.to_csv(out / "imbalance_buckets.csv", float_format="%.10g")
    sides.to_csv(out / "trade_markouts.csv", float_format="%.10g")
    plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False})
    fig, axes = plt.subplots(2, 2, figsize=(12, 8), layout="constrained")
    elapsed = (quotes.recv_ns - quotes.recv_ns.iloc[0]) / 1e9
    axes[0, 0].plot(elapsed, quotes.mid, color="#225e83", lw=1)
    axes[0, 0].set(xlabel="Seconds since first quote", ylabel="Midprice (USDT)", title="Level-1 midprice")
    axes[0, 0].ticklabel_format(axis="y", style="plain", useOffset=False)
    axes[0, 1].hist(quotes.spread_bps, bins=30, color="#225e83")
    axes[0, 1].xaxis.set_major_formatter(FormatStrFormatter("%.5f"))
    axes[0, 1].tick_params(axis="x", labelrotation=20)
    axes[0, 1].set(xlabel="Spread (bps)", ylabel="Quote observations", title="Spread distribution")
    buckets[["mean_1s_bps", "mean_5s_bps"]].plot.bar(ax=axes[1, 0], color=["#225e83", "#de9445"], rot=20)
    axes[1, 0].set(xlabel="Quantity imbalance bucket", ylabel="Mean forward change (bps)", title="Quote-conditioned movement")
    axes[1, 0].legend(["1 second", "5 seconds"])
    if len(sides):
        plot_sides = sides.rename(index={-1: "Aggressive sell", 1: "Aggressive buy"})
        plot_sides[["mean_1s_bps", "mean_5s_bps"]].plot.bar(ax=axes[1, 1], color=["#225e83", "#de9445"], rot=0)
        axes[1, 1].legend(["1 second", "5 seconds"])
    else:
        axes[1, 1].text(.5, .5, "No valid trades", ha="center", transform=axes[1, 1].transAxes)
    axes[1, 1].set(xlabel="Aggressor direction", ylabel="Signed markout (bps)", title="Trade-conditioned markouts")
    for axis in axes[1]:
        axis.axhline(0, color="gray", lw=.7)
    fig.suptitle(f"QuoteGuard | {label}\nExploratory observations • no execution or profitability inference", fontsize=14)
    fig.savefig(out / "research.png", dpi=150, metadata={"Software": "QuoteGuard"})
    plt.close(fig)
    lines = [f"# QuoteGuard research report — {label}", "",
             f"Source: `{source}`. Input SHA-256: `{summary['input_sha256']}`.", "",
             f"Recording window: {summary['window_start_utc']} to {summary['window_end_utc']}.",
             f"Raw records: {quality['raw_records']}; valid: {quality['valid_records']} "
             f"({quality['valid_fraction']:.2%}); quotes: {len(quotes)}; trades: {len(trades)}.",
             f"Trades with eligible prior quote: {counts['trades_with_eligible_quote']}; "
             f"stale or unmatched: {counts['stale_or_unmatched_trades']}.", "",
             f"Maximum quote age: {stale_s}s. Maximum forward sampling delay: {tolerance_s}s.",
             f"Available forward labels: `{json.dumps(coverage, sort_keys=True)}`.", "",
             "## Spread distribution (bps)", "", "| Percentile | Spread |", "|---|---:|"]
    lines += [f"| {float(k):.0%} | {v:.6f} |" for k, v in summary["spread_bps"].items()]
    lines += ["", "## Imbalance buckets", "", "| Bucket | Quotes | 1s count | 1s mean bps | 5s count | 5s mean bps |", "|---|---:|---:|---:|---:|---:|"]
    for key, row in buckets.iterrows():
        lines.append(f"| {key} | {int(row.observations)} | {int(row.count_1s)} | {row.mean_1s_bps:.6f} | {int(row.count_5s)} | {row.mean_5s_bps:.6f} |")
    lines += ["", "## Trade-conditioned markouts", "", "| Aggressor | Trades | 1s count | 1s mean bps | 5s count | 5s mean bps |", "|---|---:|---:|---:|---:|---:|"]
    for key, row in sides.iterrows():
        lines.append(f"| {'Buy' if key == 1 else 'Sell'} | {int(row.trades)} | {int(row.count_1s)} | {row.mean_1s_bps:.6f} | {int(row.count_5s)} | {row.mean_5s_bps:.6f} |")
    lines += ["", "![Research charts](research.png)", "", "## Interpretation and limitations", "",
        "Positive aggressor-signed markouts indicate adverse price movement for a hypothetical passive counterparty. "
        "These are trade-conditioned midprice markouts, without inferred fills, queue position, fees, inventory, or P&L.", "",
        "Features use receive order and the last available quote, including file order to resolve equal timestamps. "
        "Forward labels use the first quote at or after receipt time plus the horizon, within tolerance. "
        "Unavailable labels remain missing; counts differ by horizon. Standard bookTicker has no comparable exchange event timestamp.", "",
        "Receive clocks describe local arrival order, not exchange causality. Network delay, buffering, disconnects, "
        "clock adjustments and asynchronous streams limit sequencing accuracy. ID gaps are possible; level-1 data is not a synchronized full order book.", "",
        "Each quote update receives equal weight; this is not a time-weighted estimate. Overlapping horizons and clustered trades "
        "make observations dependent. No statistical significance or predictive alpha is established; "
        "longer sessions, independent days, held-out evaluation and dependence-aware inference are needed.", "",
        "Synthetic data is a reproducibility fixture with uncalibrated random price movements, never exchange evidence." if source == "synthetic" else
        "This report describes a short real capture only; it is exploratory and cannot validate a trading strategy.", "",
        "Rejected records: `" + json.dumps(quality["rejected"], sort_keys=True) + "`."]
    (out / "report.md").write_text("\n".join(lines) + "\n")
    return summary
