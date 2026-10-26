"""Observable receive-time quality diagnostics, without inferring network latency."""
from __future__ import annotations
import numpy as np
import pandas as pd


def receipt_quality(events: list[dict], samples: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    frame = pd.DataFrame(events)
    trades = frame[frame.kind == "trade"].copy()
    # Subtract integer milliseconds first to retain submillisecond receipt precision.
    lag = ((trades.recv_ns.to_numpy(dtype=np.int64) // 1_000_000 -
            trades.exchange_event_ms.to_numpy(dtype=np.int64)) +
           (trades.recv_ns.to_numpy(dtype=np.int64) % 1_000_000) / 1e6)
    trades["receipt_gap_ms"] = lag
    trades["gap_flag"] = (lag > 1000) | (lag < -100)
    result = samples.copy()
    result["window_flagged_trades"] = 0
    result["window_trade_gap_max_ms"] = np.nan
    result["receipt_quality_ok"] = True
    for connection in samples.connection_id.unique():
        mask = samples.connection_id.to_numpy() == connection
        subset = trades[trades.connection_id == connection]
        times = subset.recv_ns.to_numpy(dtype=np.int64)
        gaps = subset.receipt_gap_ms.to_numpy()
        flags = subset.gap_flag.to_numpy()
        for i in np.flatnonzero(mask):
            end = int(samples.recv_ns.iloc[i])
            left = np.searchsorted(times, end - 1000000000, side="right")
            right = np.searchsorted(times, end, side="right")
            result.loc[result.index[i], "window_flagged_trades"] = int(flags[left:right].sum())
            if right > left:
                result.loc[result.index[i], "window_trade_gap_max_ms"] = float(gaps[left:right].max())
    result["receipt_quality_ok"] = result.window_flagged_trades == 0
    fraction = float(result.receipt_quality_ok.mean()) if len(result) else 0
    p99 = float(np.quantile(lag, .99)) if len(lag) else None
    passes = p99 is not None and p99 <= 1000 and fraction >= .8
    summary = {"trade_count": len(trades), "gap_median_ms": float(np.median(lag)) if len(lag) else None,
               "gap_p99_ms": p99, "trades_above_1s": int((lag > 1000).sum()),
               "trades_below_minus_100ms": int((lag < -100).sum()),
               "snapshot_quality_fraction": fraction, "timing_gate_passed": bool(passes),
               "thresholds": {"max_trade_gap_ms": 1000, "min_trade_gap_ms": -100,
                              "max_p99_ms": 1000, "min_snapshot_fraction": .8},
               "scope": "observable trailing features only; no quote exchange timestamps exist"}
    return result, summary
