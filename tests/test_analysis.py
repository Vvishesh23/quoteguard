from dataclasses import asdict
import numpy as np
import pandas as pd
import pytest
from quoteguard.analysis import analyze_events, quote_features
from quoteguard.events import BinanceAdapter
from test_events import record, quote, trade


def events(rows):
    adapter = BinanceAdapter()
    return [asdict(adapter.parse(record(payload, round(seconds * 1e9)), i))
            for i, (seconds, payload) in enumerate(rows)]


def test_formulas_and_zero_denominator():
    q = quote_features(pd.DataFrame([dict(bid=100., ask=102., bid_qty=3., ask_qty=1.),
                                    dict(bid=100., ask=102., bid_qty=0., ask_qty=0.)]))
    assert q.mid[0] == 101
    assert q.spread_bps[0] == pytest.approx(2 / 101 * 10000)
    assert q.imbalance[0] == .5 and q.microprice[0] == 101.5
    assert np.isnan(q.imbalance[1]) and np.isnan(q.microprice[1])


def test_no_lookahead_asof_and_stale():
    rows = [(0, trade()), (.1, quote()), (.2, trade(tid=2)),
            (.2, quote(2, b="110", a="112")), (2, trade(tid=3))]
    _, t, stats = analyze_events(events(rows), stale_s=.5)
    assert np.isnan(t.mid[0])
    assert t.mid[1] == 101  # Later quote at identical timestamp is unavailable.
    assert np.isnan(t.mid[2])
    assert stats["stale_or_unmatched_trades"] == 2


def test_forward_at_or_after_never_before():
    rows = [(0, quote()), (.1, trade(False)), (.99, quote(2, b="90", a="92")),
            (1.1, quote(3, b="110", a="112")), (4.99, quote(4, b="80", a="82")),
            (5.1, quote(5, b="120", a="122"))]
    q, t, _ = analyze_events(events(rows), tolerance_s=.2)
    assert q.future_mid_1s[0] == 111
    assert q.future_mid_5s[0] == 121
    assert t.future_mid_1s[0] == 111 and t.future_mid_5s[0] == 121
    assert t.markout_bps_1s[0] == pytest.approx((111 / 101 - 1) * 10000)
    assert np.isnan(q.future_mid_1s.iloc[-1])


def test_sell_sign_and_future_tolerance():
    rows = [(0, quote()), (.1, trade(True)), (1.4, quote(2, b="110", a="112"))]
    _, t, _ = analyze_events(events(rows), tolerance_s=.4)
    assert t.markout_bps_1s[0] < 0
    _, t, _ = analyze_events(events(rows), tolerance_s=.2)
    assert np.isnan(t.markout_bps_1s[0]) and np.isnan(t.markout_bps_5s[0])


def test_stale_boundary():
    _, t, _ = analyze_events(events([(0, quote()), (1, trade())]), stale_s=1)
    assert t.quote_eligible[0]


def test_empty_trade_stream_and_no_quotes():
    q, t, _ = analyze_events(events([(0, quote())]))
    assert len(q) == 1 and t.empty
    with pytest.raises(ValueError, match="no valid quotes"):
        analyze_events([])


def test_mixed_source_symbol_rejected():
    rows = events([(0, quote()), (1, quote(2))])
    rows[1]["symbol"] = "ETHUSDT"
    with pytest.raises(ValueError, match="one symbol"):
        analyze_events(rows)


def test_future_mutation_cannot_change_features():
    early = [(0, quote()), (.1, trade()), (.3, quote(2, b="110", a="112"))]
    changed = [(0, quote()), (.1, trade()), (.3, quote(2, b="210", a="212"))]
    _, a, _ = analyze_events(events(early))
    _, b, _ = analyze_events(events(changed))
    for column in ("mid", "imbalance", "microprice", "spread_bps", "quote_age_ms"):
        assert a[column].equals(b[column])


def test_forward_labels_match_brute_force():
    rng = np.random.default_rng(23)
    times = np.cumsum(rng.uniform(.01, .35, 120))
    rows = [(float(t), quote(i + 1, b=str(100 + i), a=str(102 + i)))
            for i, t in enumerate(times)]
    q, _, _ = analyze_events(events(rows), tolerance_s=.12)
    for _, observation in q.iterrows():
        for horizon in (1, 5):
            target = int(observation.recv_ns) + horizon * 1000000000
            future = q[q.recv_ns >= target]
            actual = observation[f"future_mid_{horizon}s"]
            if future.empty or int(future.recv_ns.iloc[0]) - target > 120000000:
                assert np.isnan(actual)
            else:
                assert actual == future.mid.iloc[0]


def test_forward_tolerance_inclusive_boundary():
    rows = [(0, quote()), (1.2, quote(2, b="110", a="112"))]
    q, _, _ = analyze_events(events(rows), tolerance_s=.2)
    assert q.future_mid_1s[0] == 111
    q, _, _ = analyze_events(events(rows), tolerance_s=.199)
    assert np.isnan(q.future_mid_1s[0])
