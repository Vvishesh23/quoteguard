import json
import pytest
from quoteguard.events import BinanceAdapter, load_events

BASE = 1767225600000000000


def record(payload, offset=0):
    return {"source": "synthetic", "recv_ns": BASE + offset, "mono_ns": offset + 1,
            "raw": json.dumps({"stream": "btcusdt@bookTicker", "data": payload})}


def quote(uid=1, **kwargs):
    return dict({"u": uid, "s": "BTCUSDT", "b": "100", "a": "102", "B": "3", "A": "1"}, **kwargs)


def trade(maker=False, tid=1):
    return {"e": "trade", "s": "BTCUSDT", "t": tid, "p": "102", "q": "1",
            "m": maker, "E": BASE // 1000000, "T": BASE // 1000000}


def test_quote_has_no_invented_exchange_time():
    event = BinanceAdapter().parse(record(quote()), 0)
    assert event.bid == 100 and event.ask_qty == 1
    assert event.exchange_event_ms is None and event.exchange_trade_ms is None


@pytest.mark.parametrize("maker,sign", [(True, -1), (False, 1)])
def test_aggressor_mapping(maker, sign):
    event = BinanceAdapter().parse(record(trade(maker)), 0)
    assert event.sign == sign
    assert event.exchange_trade_ms == BASE // 1000000


@pytest.mark.parametrize("key,value", [("b", "103"), ("b", "-1"), ("B", "0"), ("A", "nan"),
                                       ("a", "inf"), ("u", True), ("s", "BTC/USDT")])
def test_invalid_quote(key, value):
    data = quote()
    data[key] = value
    with pytest.raises(ValueError):
        BinanceAdapter().parse(record(data), 0)


def test_locked_spread_allowed():
    data = quote()
    data["a"] = "100"
    assert BinanceAdapter().parse(record(data), 0).ask == 100


@pytest.mark.parametrize("key,value", [("m", "false"), ("T", 0), ("E", "bad"), ("q", "-2")])
def test_invalid_trade(key, value):
    data = trade()
    data[key] = value
    with pytest.raises(ValueError):
        BinanceAdapter().parse(record(data), 0)


@pytest.mark.parametrize("uid", [1, 0])
def test_duplicate_decreasing_id(uid):
    adapter = BinanceAdapter()
    adapter.parse(record(quote()), 0)
    with pytest.raises(ValueError, match="stream ID"):
        adapter.parse(record(quote(uid), 1), 1)


def test_bad_receive_clock():
    adapter = BinanceAdapter()
    adapter.parse(record(quote(), 100), 0)
    with pytest.raises(ValueError, match="clock regression"):
        adapter.parse(record(quote(2), 99), 1)
    bad = record(quote())
    bad["recv_ns"] = "2026-01-01"
    with pytest.raises(ValueError):
        BinanceAdapter().parse(bad, 0)


def test_corrupt_lines_accounted_for(tmp_path):
    path = tmp_path / "broken.jsonl"
    path.write_text('\nnot json\n{}\n[]\n' + json.dumps(record(quote())) + '\n')
    events, stats = load_events(path)
    assert len(events) == 1
    assert stats["raw_records"] == 5 and stats["valid_fraction"] == .2


def test_ids_are_independent_between_streams():
    adapter = BinanceAdapter()
    adapter.parse(record(quote(100)), 0)
    parsed = adapter.parse(record(trade(tid=1), 1), 1)
    assert parsed.event_id == 1 and parsed.kind == "trade"


def test_rejected_id_does_not_replace_last_accepted_id():
    adapter = BinanceAdapter()
    adapter.parse(record(quote(3)), 0)
    with pytest.raises(ValueError):
        adapter.parse(record(quote(2), 1), 1)
    assert adapter.parse(record(quote(4), 2), 2).event_id == 4
