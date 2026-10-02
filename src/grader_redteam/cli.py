"""Command line entry point."""

from __future__ import annotations

import argparse
import json

from . import __version__
from .config import load
from .probes import MISSED, PROBES, run_all


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="grader-redteam",
        description="Run exploit probes against a grader and report what it misses.",
    )
    ap.add_argument("--version", action="version", version=__version__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="run the battery against a config")
    r.add_argument("config")
    r.add_argument("--only", action="append", help="run just this probe (repeatable)")
    r.add_argument("--no-controls", action="store_true")
    r.add_argument("--json", action="store_true", help="print results as JSON")
    sub.add_parser("list", help="list the probes")
    args = ap.parse_args(argv)

    if args.cmd == "list":
        for name, fn in PROBES.items():
            print(f"{name:24} {fn.__doc__.strip().splitlines()[0]}")
        return 0

    cfg = load(args.config)
    results = run_all(cfg, only=args.only, with_controls=not args.no_controls)
    if args.json:
        print(json.dumps([r.__dict__ for r in results], indent=2))
    else:
        for res in results:
            print(f"{res.status:8} {res.name:40} {res.detail}")
        missed = sum(r.status == "MISSED" for r in results)
        print(f"\n{missed} of {len(results)} checks missed")
    return 1 if any(r.status == MISSED for r in results) else 0
