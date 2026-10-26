"""Bounded, credential-free capture with lossless raw text and receipt clocks."""
from __future__ import annotations
import asyncio
import json
import logging
import re
import ssl
import math
import time
from pathlib import Path
import websockets
from .events import utc_ns

LOG = logging.getLogger(__name__)


class CaptureWriteError(ValueError):
    """A raw persistence failure is fatal rather than a network reconnect trigger."""


def persist_raw(handle, record: dict) -> None:
    try:
        handle.write(json.dumps(record, separators=(",", ":")) + "\n")
    except OSError as exc:
        raise CaptureWriteError(f"cannot persist raw capture: {exc}") from exc


def stream_url(symbol: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9]{4,24}", symbol):
        raise ValueError("symbol must be 4–24 alphanumeric characters")
    name = symbol.lower()
    return f"wss://stream.binance.com:9443/stream?streams={name}@bookTicker/{name}@trade"


def verified_context(system_trust: bool = False) -> ssl.SSLContext:
    if system_trust:
        try:
            import truststore
        except ImportError as exc:
            raise ValueError("system trust requires: pip install 'quoteguard[system-trust]'") from exc
        return truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    return ssl.create_default_context()


async def collect(symbol: str, seconds: float, out: Path, *, system_trust: bool = False) -> dict:
    if not math.isfinite(seconds) or seconds <= 0:
        raise ValueError("duration must be positive")
    url = stream_url(symbol)
    context = verified_context(system_trust)
    out.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation protects any earlier capture, including interrupted runs.
    stats = {"source": "binance_public", "symbol": symbol.upper(), "url": url,
             "received": 0, "connections": 0, "errors": [], "requested_seconds": seconds,
             "tls_trust": "system" if system_trust else "python_default", "tls_verified": True}
    loop = asyncio.get_running_loop()
    stats["loop_health"] = {"samples": 0, "max_lag_ms": 0., "above_100ms": 0}
    stats["write_health"] = {"writes": 0, "total_ms": 0., "max_ms": 0.}
    stats["stop_reason"] = "duration"
    started = time.monotonic()
    deadline = started + seconds
    timer = None
    def observe_loop(expected: float) -> None:
        nonlocal timer
        now = loop.time()
        lag_ms = max(0., (now - expected) * 1000)
        health = stats["loop_health"]
        health["samples"] += 1
        health["max_lag_ms"] = max(health["max_lag_ms"], lag_ms)
        health["above_100ms"] += int(lag_ms > 100)
        next_time = now + .1
        timer = loop.call_at(next_time, observe_loop, next_time)
    backoff = 1.0
    with out.open("x", buffering=1) as handle:
        timer = loop.call_later(.1, observe_loop, loop.time() + .1)
        try:
            while time.monotonic() < deadline:
                try:
                    remaining = deadline - time.monotonic()
                    async with asyncio.timeout(remaining):
                        async with websockets.connect(url, open_timeout=min(10, remaining),
                                                      close_timeout=1, max_queue=256, ssl=context,
                                                      max_size=1_048_576) as socket:
                            stats["connections"] += 1
                            while True:
                                raw = await socket.recv()
                                recv_ns, mono_ns = time.time_ns(), time.monotonic_ns()
                                if isinstance(raw, bytes):
                                    raw = raw.decode("utf-8")
                                write_start = time.perf_counter_ns()
                                persist_raw(handle, {"source": "binance_public", "recv_ns": recv_ns,
                                    "recv_utc": utc_ns(recv_ns), "connection_id": stats["connections"],
                                    "mono_ns": mono_ns, "raw": raw})
                                write_ms = (time.perf_counter_ns() - write_start) / 1e6
                                health = stats["write_health"]
                                health["writes"] += 1
                                health["total_ms"] += write_ms
                                health["max_ms"] = max(health["max_ms"], write_ms)
                                stats["received"] += 1
                                backoff = 1.0
                except TimeoutError:
                    if time.monotonic() >= deadline:
                        break
                    stats["errors"].append("TimeoutError: opening connection timed out")
                    LOG.warning("Connection open timed out; retrying within capture duration")
                    await asyncio.sleep(min(backoff, max(0, deadline - time.monotonic())))
                    backoff = min(backoff * 2, 30)
                except (OSError, websockets.exceptions.WebSocketException, UnicodeError) as exc:
                    message = f"{type(exc).__name__}: {exc}"
                    stats["errors"].append(message)
                    LOG.warning("Capture connection failed: %s", message)
                    await asyncio.sleep(min(backoff, max(0, deadline - time.monotonic())))
                    backoff = min(backoff * 2, 30)
        except asyncio.CancelledError:
            stats["stop_reason"] = "cancelled"
            raise
        except Exception:
            stats["stop_reason"] = "fatal_error"
            raise
        finally:
            if timer is not None:
                timer.cancel()
            stats["elapsed_seconds"] = time.monotonic() - started
            handle.flush()
            out.with_suffix(out.suffix + ".meta.json").write_text(json.dumps(stats, indent=2) + "\n")
    return stats
