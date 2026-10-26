"""Strict public Binance adapter. Raw capture and validation are separate stages."""
from __future__ import annotations

import json
import math
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class Event:
    kind: str
    symbol: str
    recv_ns: int
    mono_ns: int
    sequence: int
    source: str
    event_id: int
    bid: float = 0
    ask: float = 0
    bid_qty: float = 0
    ask_qty: float = 0
    price: float = 0
    qty: float = 0
    sign: int = 0
    exchange_event_ms: int | None = None
    exchange_trade_ms: int | None = None
    connection_id: int = 0


def integer(value: object, name: str) -> int:
    if type(value) is not int or value < 0:
        raise ValueError(f"invalid {name}")
    return value


def positive(value: object) -> float:
    if isinstance(value, bool):
        raise ValueError("boolean numeric field")
    result = float(value)
    if not math.isfinite(result) or result <= 0:
        raise ValueError("price/size must be finite and positive")
    return result


class BinanceAdapter:
    """Reject duplicate/decreasing IDs per stream and clock regressions per capture."""
    def __init__(self) -> None:
        self.ids: dict[tuple[str, str], int] = {}
        self.last_clock: tuple[int, int] | None = None

    def parse(self, record: dict, sequence: int) -> Event:
        recv = integer(record["recv_ns"], "receive timestamp")
        mono = integer(record["mono_ns"], "monotonic timestamp")
        # Reject unrepresentable UTC times before downstream pandas conversion.
        if not 946684800000000000 <= recv <= 4102444800000000000:
            raise ValueError("receive timestamp outside 2000–2100")
        if self.last_clock and (recv < self.last_clock[0] or mono < self.last_clock[1]):
            raise ValueError("receive clock regression")
        self.last_clock = recv, mono
        raw = record["raw"]
        payload = json.loads(raw) if isinstance(raw, str) else raw
        data = payload.get("data", payload)
        symbol = data["s"]
        if not isinstance(symbol, str) or not symbol.isalnum():
            raise ValueError("invalid symbol")
        source = record["source"]
        if source not in ("binance_public", "synthetic"):
            raise ValueError("unknown source")
        common = dict(symbol=symbol, recv_ns=recv, mono_ns=mono,
                      connection_id=integer(record.get("connection_id", 0), "connection ID"),
                      sequence=sequence, source=source)
        if "b" in data and "a" in data:
            bid, ask = positive(data["b"]), positive(data["a"])
            if bid > ask:
                raise ValueError("crossed quote")
            event = Event(kind="quote", event_id=integer(data["u"], "update ID"),
                          bid=bid, ask=ask, bid_qty=positive(data["B"]),
                          ask_qty=positive(data["A"]), **common)
        elif data.get("e") == "trade":
            if type(data["m"]) is not bool:
                raise ValueError("maker flag must be boolean")
            exchange = [integer(data[k], k) for k in ("E", "T")]
            if any(not 946684800000 <= t <= 4102444800000 for t in exchange):
                raise ValueError("invalid exchange timestamp")
            event = Event(kind="trade", event_id=integer(data["t"], "trade ID"),
                          price=positive(data["p"]), qty=positive(data["q"]),
                          sign=-1 if data["m"] else 1, exchange_event_ms=exchange[0],
                          exchange_trade_ms=exchange[1], **common)
        else:
            raise ValueError("unsupported payload")
        key = event.symbol, event.kind
        if event.event_id <= self.ids.get(key, -1):
            raise ValueError("duplicate/decreasing stream ID")
        self.ids[key] = event.event_id
        return event


class EventAdapter(Protocol):
    def parse(self, record: dict, sequence: int) -> Event: ...


def load_events(path: Path, adapter: EventAdapter | None = None) -> tuple[list[dict], dict]:
    adapter = BinanceAdapter() if adapter is None else adapter
    events: list[dict] = []
    reasons: Counter = Counter()
    total = 0
    with path.open() as handle:
        for sequence, line in enumerate(handle):
            total += 1
            try:
                record = json.loads(line)
                events.append(asdict(adapter.parse(record, sequence)))
            except (ValueError, KeyError, TypeError, AttributeError, OverflowError) as exc:
                reasons[str(exc)] += 1
    return events, {"raw_records": total, "valid_records": len(events),
                    "valid_fraction": len(events) / total if total else 0,
                    "rejected": dict(sorted(reasons.items()))}


def utc_ns(value: int) -> str:
    seconds, nanos = divmod(int(value), 1_000_000_000)
    return datetime.fromtimestamp(seconds, timezone.utc).strftime("%Y-%m-%dT%H:%M:%S") + f".{nanos:09d}Z"
