"""CLI entry point; all operations are public-data or offline research."""
from __future__ import annotations
import argparse
import asyncio
import json
import logging
import math
from pathlib import Path
from .collector import collect


def positive_number(value: str) -> float:
    result = float(value)
    if not math.isfinite(result) or result <= 0:
        raise argparse.ArgumentTypeError("must be finite and positive")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="QuoteGuard public level-1 order flow research")
    commands = parser.add_subparsers(dest="command", required=True)
    capture = commands.add_parser("collect", help="bounded public Binance capture; never overwrites")
    capture.add_argument("--system-trust", action="store_true", help="verify TLS with native system trust; requires system-trust extra")
    capture.add_argument("--symbol", default="BTCUSDT")
    capture.add_argument("--minutes", type=positive_number, default=20)
    capture.add_argument("--out", type=Path, required=True)
    analyze = commands.add_parser("analyze", help="analyze one captured or labeled synthetic JSONL")
    analyze.add_argument("--input", type=Path, required=True)
    analyze.add_argument("--out", type=Path, required=True)
    analyze.add_argument("--stale-seconds", type=positive_number, default=1)
    analyze.add_argument("--future-tolerance-seconds", type=positive_number, default=.5)
    holdout = commands.add_parser("holdout", help="evaluate a frozen model on a strictly later recording without refitting")
    holdout.add_argument("--model", type=Path, required=True)
    holdout.add_argument("--input", type=Path, required=True)
    holdout.add_argument("--out", type=Path, required=True)
    fit = commands.add_parser("fit", help="freeze training-only models into a fingerprinted JSON artifact")
    fit.add_argument("--input", type=Path, required=True)
    fit.add_argument("--out", type=Path, required=True)
    audit = commands.add_parser("audit", help="independently verify saved study metrics and split timing")
    audit.add_argument("--input", type=Path, required=True)
    audit.add_argument("--study", "--report", dest="study", type=Path, required=True)
    audit.add_argument("--model", type=Path, help="audit frozen held-out inference instead of within-session study")
    audit.add_argument("--out", type=Path, required=True)
    study = commands.add_parser("study", help="regular-time features, purged chronological models and block uncertainty")
    study.add_argument("--input", type=Path, required=True)
    study.add_argument("--out", type=Path, required=True)
    study.add_argument("--no-sensitivity", action="store_true", help="skip predeclared sensitivity grid")
    session_demo = commands.add_parser("session-demo", help="offline synthetic train/freeze/later-session/audit workflow")
    session_demo.add_argument("--out", type=Path, default=Path("reports/session-demo"))
    demo = commands.add_parser("demo", help="deterministic offline SYNTHETIC report")
    demo.add_argument("--out", type=Path, default=Path("reports/demo"))
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        if args.command == "collect":
            summary = asyncio.run(collect(args.symbol, args.minutes * 60, args.out, system_trust=args.system_trust))
            print(json.dumps(summary, indent=2))
            if not summary["received"]:
                print("No stream data captured. Run: python -m quoteguard demo --out reports/demo")
                return 2
        elif args.command == "session-demo":
            from .holdout import frozen_demo
            print(json.dumps(frozen_demo(args.out), indent=2))
        elif args.command == "holdout":
            from .holdout import run_holdout
            print(json.dumps(run_holdout(args.model, args.input, args.out), indent=2))
        elif args.command == "fit":
            from .frozen import fit_artifact
            artifact = fit_artifact(args.input, args.out)
            print(json.dumps({"artifact_id": artifact["artifact_id"], "out": str(args.out)}, indent=2))
        elif args.command == "audit":
            if args.model:
                from .holdout import audit_holdout
                result = audit_holdout(args.model, args.input, args.study, args.out)
            else:
                from .audit import audit_study
                result = audit_study(args.input, args.study, args.out)
            print(json.dumps(result, indent=2))
        elif args.command == "study":
            from .study import build_study
            print(json.dumps(build_study(args.input, args.out, sensitivity=not args.no_sensitivity), indent=2))
        else:
            from .report import build_report
            if args.command == "demo":
                from .fixture import generate
                fixture = args.out / "synthetic.jsonl"
                generate(fixture)
                summary = build_report(fixture, args.out)
            else:
                summary = build_report(args.input, args.out, args.stale_seconds, args.future_tolerance_seconds)
            print(json.dumps(summary, indent=2))
    except KeyboardInterrupt:
        print("Stopped; received raw data and capture metadata are preserved.")
        return 130
    except (ValueError, OSError) as exc:
        parser.exit(2, f"QuoteGuard: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
