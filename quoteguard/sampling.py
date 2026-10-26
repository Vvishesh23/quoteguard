"""Regular receive-time sampling and causal trailing-window order-flow features."""
from __future__ import annotations
import numpy as np
import pandas as pd
from .analysis import forward_targets, quote_features

FEATURE_SETS = {
    "imbalance": ["imbalance"],
    "book": ["imbalance", "microprice_edge_bps", "spread_bps", "ofi_depth"],
    "trade": ["trade_flow_imbalance", "log_trade_count"],
    "combined": ["imbalance", "microprice_edge_bps", "spread_bps", "ofi_depth",
                 "trade_flow_imbalance", "log_trade_count", "lag_return_bps"],
}


def trailing_sum(times: np.ndarray, values: np.ndarray, ticks: np.ndarray,
                 lookback_ns: int) -> np.ndarray:
    """Sum values in (tick-lookback, tick]; no following events are accessible."""
    cumulative = np.r_[0., np.cumsum(values, dtype=float)]
    right = np.searchsorted(times, ticks, side="right")
    left = np.searchsorted(times, ticks - lookback_ns, side="right")
    return cumulative[right] - cumulative[left]


def level1_ofi(quotes: pd.DataFrame) -> np.ndarray:
    """Best-quote price/size transition OFI; first update per connection is unknown."""
    b, a = quotes.bid.to_numpy(), quotes.ask.to_numpy()
    B, A = quotes.bid_qty.to_numpy(), quotes.ask_qty.to_numpy()
    result = np.zeros(len(quotes))
    if len(quotes) > 1:
        result[1:] = ((b[1:] >= b[:-1]) * B[1:] - (b[1:] <= b[:-1]) * B[:-1]
                      - (a[1:] <= a[:-1]) * A[1:] + (a[1:] >= a[:-1]) * A[:-1])
        if "connection_id" in quotes:
            result[1:][quotes.connection_id.to_numpy()[1:] != quotes.connection_id.to_numpy()[:-1]] = 0
    return result


def sample_features(events: list[dict], interval_s: float = 1, stale_s: float = 1,
                    tolerance_s: float = .5, lookback_s: float = 1) -> tuple[pd.DataFrame, dict]:
    parameters = [interval_s, stale_s, tolerance_s, lookback_s]
    if not all(np.isfinite(parameters)) or min(parameters) <= 0:
        raise ValueError("sampling parameters must be finite and positive")
    frame = pd.DataFrame(events)
    if frame.empty or not (frame.kind == "quote").any():
        raise ValueError("no valid quotes in input")
    frame = frame.sort_values("sequence").reset_index(drop=True)
    if frame.symbol.nunique() != 1 or frame.source.nunique() != 1:
        raise ValueError("one source and symbol required")
    if "connection_id" not in frame:
        frame["connection_id"] = 0
    if (np.diff(frame.recv_ns.to_numpy(dtype=np.int64)) < 0).any():
        raise ValueError("receive times must be nondecreasing")
    quotes = quote_features(frame[frame.kind == "quote"].reset_index(drop=True))
    trades = frame[frame.kind == "trade"]
    step, lookback = round(interval_s * 1e9), round(lookback_s * 1e9)
    if step < 1 or lookback < 1:
        raise ValueError("sampling resolution must be at least one nanosecond")
    start = ((int(frame.recv_ns.iloc[0]) + step - 1) // step) * step
    ticks = np.arange(start, int(frame.recv_ns.iloc[-1]) + 1, step, dtype=np.int64)
    qt = quotes.recv_ns.to_numpy(dtype=np.int64)
    qi = np.searchsorted(qt, ticks, side="right") - 1
    valid = qi >= 0
    qi = qi.clip(min=0)
    snapshots = quotes.iloc[qi].reset_index(drop=True).copy()
    snapshots["quote_recv_ns"] = snapshots.recv_ns.copy()
    snapshots["recv_ns"] = ticks
    snapshots["quote_age_ms"] = (ticks - snapshots.quote_recv_ns.to_numpy()) / 1e6
    latest_event = np.searchsorted(frame.recv_ns.to_numpy(dtype=np.int64), ticks, side="right") - 1
    valid &= frame.connection_id.to_numpy()[latest_event] == snapshots.connection_id.to_numpy()
    valid &= snapshots.quote_age_ms <= stale_s * 1000
    snapshots["quote_eligible"] = valid
    snapshots["microprice_edge_bps"] = (snapshots.microprice / snapshots.mid - 1) * 10000
    snapshots["ofi_depth"] = 0.
    snapshots["trade_flow_imbalance"] = 0.
    snapshots["log_trade_count"] = 0.
    snapshots["trade_count"] = 0.
    snapshots["signed_trade_qty"] = 0.
    snapshots["total_trade_qty"] = 0.
    ofi = level1_ofi(quotes)
    for connection in snapshots.connection_id.unique():
        mask = snapshots.connection_id.to_numpy() == connection
        tq = ticks[mask]
        qmask = quotes.connection_id.to_numpy() == connection
        t = trades[trades.connection_id == connection]
        sums = trailing_sum(qt[qmask], ofi[qmask], tq, lookback)
        depth = snapshots.loc[mask, "bid_qty"].to_numpy() + snapshots.loc[mask, "ask_qty"].to_numpy()
        snapshots.loc[mask, "ofi_depth"] = sums / depth
        tt = t.recv_ns.to_numpy(dtype=np.int64)
        qty = t.qty.to_numpy()
        total = trailing_sum(tt, qty, tq, lookback)
        signed = trailing_sum(tt, qty * t.sign.to_numpy(), tq, lookback)
        count = trailing_sum(tt, np.ones(len(t)), tq, lookback)
        snapshots.loc[mask, "trade_flow_imbalance"] = np.clip(np.divide(signed, total, out=np.zeros(len(tq)), where=total > 0), -1, 1)
        snapshots.loc[mask, "log_trade_count"] = np.log1p(count)
        snapshots.loc[mask, "trade_count"] = count
        snapshots.loc[mask, "signed_trade_qty"] = signed
        snapshots.loc[mask, "total_trade_qty"] = total
    past_target = ticks - lookback
    past_i = np.searchsorted(qt, past_target, side="right") - 1
    past_valid = past_i >= 0
    past_i = past_i.clip(min=0)
    past_valid &= quotes.connection_id.to_numpy()[past_i] == snapshots.connection_id.to_numpy()
    past_valid &= past_target - qt[past_i] <= round(stale_s * 1e9)
    lag = (snapshots.mid.to_numpy() / quotes.mid.to_numpy()[past_i] - 1) * 10000
    lag[~past_valid] = np.nan
    snapshots["lag_return_bps"] = lag
    connection_start = frame.groupby("connection_id").recv_ns.min().to_dict()
    warmup_ok = ticks - snapshots.connection_id.map(connection_start).to_numpy(dtype=np.int64) >= lookback
    snapshots["feature_eligible"] = valid & past_valid & warmup_ok
    columns = list(dict.fromkeys(sum(FEATURE_SETS.values(), []))) + ["mid"]
    snapshots.loc[~snapshots.feature_eligible, columns] = np.nan
    snapshots = forward_targets(snapshots, quotes, tolerance_s)
    coverage = {"grid_observations": len(snapshots), "eligible_features": int(snapshots.feature_eligible.sum()),
                "interval_s": interval_s, "lookback_s": lookback_s, "stale_s": stale_s,
                "tolerance_s": tolerance_s}
    for h in (1, 5):
        coverage[f"labeled_{h}s"] = int(snapshots[f"forward_bps_{h}s"].notna().sum())
    return snapshots, coverage
