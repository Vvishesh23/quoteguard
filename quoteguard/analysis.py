"""Receive-order features and forward-only targets, with explicit coverage."""
from __future__ import annotations
import numpy as np
import pandas as pd


def quote_features(quotes: pd.DataFrame) -> pd.DataFrame:
    q = quotes.copy()
    denominator = q.bid_qty + q.ask_qty
    q["mid"] = (q.bid + q.ask) / 2
    q["spread_bps"] = (q.ask - q.bid) / q.mid * 10000
    q["imbalance"] = (q.bid_qty - q.ask_qty).div(denominator.where(denominator > 0))
    q["microprice"] = (q.ask * q.bid_qty + q.bid * q.ask_qty).div(denominator.where(denominator > 0))
    return q


def forward_targets(observations: pd.DataFrame, quotes: pd.DataFrame,
                    tolerance_s: float) -> pd.DataFrame:
    result = observations.copy()
    times = quotes.recv_ns.to_numpy(dtype=np.int64)
    mids = quotes.mid.to_numpy()
    for horizon in (1, 5):
        targets = result.recv_ns.to_numpy(dtype=np.int64) + horizon * 1_000_000_000
        indices = np.searchsorted(times, targets, side="left")
        eligible = indices < len(times)
        clipped = np.minimum(indices, max(0, len(times) - 1))
        values = np.full(len(result), np.nan)
        delays = np.full(len(result), np.nan)
        if len(times):
            eligible &= times[clipped] - targets <= round(tolerance_s * 1e9)
            if "connection_id" in result and "connection_id" in quotes:
                eligible &= quotes.connection_id.to_numpy()[clipped] == result.connection_id.to_numpy()
            values[eligible] = mids[clipped[eligible]]
            delays[eligible] = (times[clipped[eligible]] - targets[eligible]) / 1e6
        result[f"target_recv_ns_{horizon}s"] = pd.array(
            [int(times[j]) if ok else None for j, ok in zip(clipped, eligible)], dtype="Int64")
        result[f"future_mid_{horizon}s"] = values
        result[f"target_delay_ms_{horizon}s"] = delays
        result[f"forward_bps_{horizon}s"] = (values / result.mid - 1) * 10000
        if "sign" in result:
            result[f"markout_bps_{horizon}s"] = result.sign * result[f"forward_bps_{horizon}s"]
    return result


def analyze_events(events: list[dict], stale_s: float = 1, tolerance_s: float = 0.5
                   ) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    if not np.isfinite(stale_s) or not np.isfinite(tolerance_s) or stale_s < 0 or tolerance_s < 0:
        raise ValueError("stale age and future tolerance must be nonnegative")
    frame = pd.DataFrame(events)
    if frame.empty or not (frame.kind == "quote").any():
        raise ValueError("no valid quotes in input")
    if frame.symbol.nunique() != 1 or frame.source.nunique() != 1:
        raise ValueError("analyze one symbol and one source at a time")
    quotes = quote_features(frame[frame.kind == "quote"].sort_values("sequence").reset_index(drop=True))
    trades = frame[frame.kind == "trade"].sort_values("sequence").reset_index(drop=True)
    # Sequence is the tie breaker: a later quote with the same receipt nanosecond is unavailable.
    quote_sequences = quotes.sequence.to_numpy()
    index = np.searchsorted(quote_sequences, trades.sequence.to_numpy(), side="right") - 1
    matched = index >= 0
    for column in ("mid", "spread_bps", "imbalance", "microprice"):
        trades[column] = np.nan
        if len(trades):
            trades.loc[matched, column] = quotes[column].to_numpy()[index[matched]]
    trades["quote_recv_ns"] = pd.array(
        [int(quotes.recv_ns.iloc[j]) if j >= 0 else None for j in index], dtype="Int64")
    trades["quote_age_ms"] = (trades.recv_ns - trades.quote_recv_ns).astype(float) / 1e6
    same_connection = np.ones(len(trades), dtype=bool)
    if "connection_id" in frame:
        same_connection[matched] = (quotes.connection_id.to_numpy()[index[matched]] ==
                                    trades.connection_id.to_numpy()[matched])
    trades["quote_eligible"] = matched & same_connection & (trades.quote_age_ms <= stale_s * 1000)
    for column in ("mid", "spread_bps", "imbalance", "microprice"):
        trades.loc[~trades.quote_eligible, column] = np.nan
    quotes = forward_targets(quotes, quotes, tolerance_s)
    trades = forward_targets(trades, quotes, tolerance_s)
    return quotes, trades, {"quotes": len(quotes), "trades": len(trades),
                           "trades_with_eligible_quote": int(trades.quote_eligible.sum()),
                           "stale_or_unmatched_trades": int((~trades.quote_eligible).sum())}
