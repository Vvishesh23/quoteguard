"""Deterministic synthetic events; no calibration or market-performance claims."""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
from .events import utc_ns


def generate(path: Path, seed: int = 17, steps: int = 1200,
             start_ns: int = 1767225600000000000) -> None:
    rng = np.random.default_rng(seed)
    start = start_ns
    mid = 100000.0
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as handle:
        for i in range(steps):
            mid += rng.normal(0, 0.9)
            qty = rng.lognormal(0, 0.8, size=2)
            now = start + i * 100_000_000
            quote = {"u": i + 1, "s": "BTCUSDT", "b": f"{mid - 0.5:.2f}",
                     "a": f"{mid + 0.5:.2f}", "B": f"{qty[0]:.6f}", "A": f"{qty[1]:.6f}"}
            trade_ns = now + 20_000_000
            maker = bool(rng.integers(2))
            trade = {"e": "trade", "s": "BTCUSDT", "t": i + 1,
                     "p": quote["b"] if maker else quote["a"], "q": "0.01",
                     "m": maker, "E": trade_ns // 1_000_000, "T": trade_ns // 1_000_000}
            for timestamp, stream, payload in ((now, "bookTicker", quote), (trade_ns, "trade", trade)):
                record = {"source": "synthetic", "recv_ns": timestamp, "recv_utc": utc_ns(timestamp),
                          "mono_ns": timestamp - start + 1, "raw": json.dumps(
                              {"stream": f"btcusdt@{stream}", "data": payload}, separators=(",", ":"))}
                handle.write(json.dumps(record, separators=(",", ":")) + "\n")
