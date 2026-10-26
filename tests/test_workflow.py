import asyncio
import hashlib
import json
import pytest
from quoteguard.collector import collect, stream_url
from quoteguard.events import load_events
from quoteguard.fixture import generate
from quoteguard.report import build_report


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_deterministic_fixture_and_report(tmp_path):
    a, b = tmp_path / "a.jsonl", tmp_path / "b.jsonl"
    generate(a, steps=70)
    generate(b, steps=70)
    assert a.read_bytes() == b.read_bytes()
    assert load_events(a) == load_events(b)
    result = build_report(a, tmp_path / "one")
    build_report(b, tmp_path / "two")
    assert result["source"] == "synthetic" and result["raw_records"] == 140
    for name in ["summary.json", "quotes.csv", "trades.csv", "imbalance_buckets.csv",
                 "trade_markouts.csv", "research.png", "report.md"]:
        assert digest(tmp_path / "one" / name) == digest(tmp_path / "two" / name)
    text = (tmp_path / "one" / "report.md").read_text()
    assert "SYNTHETIC" in text and "without inferred fills" in text


def test_safe_url_and_output(tmp_path):
    assert "btcusdt@bookTicker/btcusdt@trade" in stream_url("BTCUSDT")
    with pytest.raises(ValueError):
        stream_url("BTC/USDT?bad")
    path = tmp_path / "existing.jsonl"
    path.write_text("preserve")
    with pytest.raises(FileExistsError):
        asyncio.run(collect("BTCUSDT", 1, path))
    assert path.read_text() == "preserve"


def test_collector_with_fake_socket(tmp_path, monkeypatch):
    import quoteguard.collector as module
    class Socket:
        sent = False
        async def recv(self):
            if self.sent:
                await asyncio.sleep(1)
            self.sent = True
            return '{"data":{"example":true}}'
    class Connection:
        async def __aenter__(self):
            return Socket()
        async def __aexit__(self, *args):
            return False
    monkeypatch.setattr(module.websockets, "connect", lambda *a, **k: Connection())
    path = tmp_path / "capture.jsonl"
    stats = asyncio.run(collect("BTCUSDT", .02, path))
    line = json.loads(path.read_text())
    assert stats["received"] == 1
    assert line["raw"] == '{"data":{"example":true}}'
    assert line["mono_ns"] > 0 and line["recv_utc"].endswith("Z")
    assert path.with_suffix(".jsonl.meta.json").exists()
    assert stats["write_health"]["writes"] == 1
    assert stats["write_health"]["max_ms"] >= 0
    assert stats["stop_reason"] == "duration"
    assert stats["elapsed_seconds"] >= .02


def test_disconnect_recovery_metadata(tmp_path, monkeypatch):
    import quoteguard.collector as module
    def fail(*args, **kwargs):
        raise OSError("simulated offline")
    monkeypatch.setattr(module.websockets, "connect", fail)
    path = tmp_path / "offline.jsonl"
    result = asyncio.run(collect("BTCUSDT", .01, path))
    assert result["received"] == 0 and len(result["errors"]) == 1
    assert path.read_text() == ""


def test_open_timeout_retries(tmp_path, monkeypatch):
    import quoteguard.collector as module
    calls = []
    original_sleep = asyncio.sleep
    class Socket:
        sent = False
        async def recv(self):
            if self.sent:
                await original_sleep(1)
            self.sent = True
            return '{}'
    class Connection:
        async def __aenter__(self):
            calls.append(1)
            if len(calls) == 1:
                raise TimeoutError()
            return Socket()
        async def __aexit__(self, *args):
            return False
    async def fast_backoff(delay):
        return None
    monkeypatch.setattr(module.websockets, "connect", lambda *a, **k: Connection())
    monkeypatch.setattr(module.asyncio, "sleep", fast_backoff)
    result = asyncio.run(collect("BTCUSDT", .03, tmp_path / "timeout.jsonl"))
    assert len(calls) == 2 and result["received"] == 1
    assert "opening connection" in result["errors"][0]


def test_interrupted_capture_preserves_data_and_metadata(tmp_path, monkeypatch):
    import quoteguard.collector as module
    class Socket:
        sent = False
        async def recv(self):
            if self.sent:
                await asyncio.sleep(60)
            self.sent = True
            return '{"saved":true}'
    class Connection:
        async def __aenter__(self):
            return Socket()
        async def __aexit__(self, *args):
            return False
    monkeypatch.setattr(module.websockets, "connect", lambda *a, **k: Connection())
    path = tmp_path / "interrupted.jsonl"
    async def interrupt():
        task = asyncio.create_task(collect("BTCUSDT", 20, path))
        await asyncio.sleep(.01)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    asyncio.run(interrupt())
    assert json.loads(path.read_text())["raw"] == '{"saved":true}'
    saved = json.loads(path.with_suffix(".jsonl.meta.json").read_text())
    assert saved["received"] == 1
    assert saved["stop_reason"] == "cancelled"


def test_raw_disk_failure_is_not_a_reconnect():
    from quoteguard.collector import persist_raw, CaptureWriteError
    class BrokenDisk:
        def write(self, text):
            raise OSError("simulated disk failure")
    with pytest.raises(CaptureWriteError, match="persist raw"):
        persist_raw(BrokenDisk(), {"raw": "keep"})
