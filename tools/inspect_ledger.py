"""Quick cost ledger inspection.

Usage:
    python tools/inspect_ledger.py                          # production ledger (data/cost_ledger.jsonl)
    python tools/inspect_ledger.py --selfplay               # self-play ledger ($TMPDIR/diplomat_selfplay/cost_ledger.jsonl)
    python tools/inspect_ledger.py --path <some/path>       # explicit path

Prints total spend, by-operation breakdown, and a cumulative timeline.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from collections import defaultdict
from pathlib import Path


PRODUCTION_LEDGER = Path("data/cost_ledger.jsonl")
SELFPLAY_LEDGER = Path(tempfile.gettempdir()) / "diplomat_selfplay" / "cost_ledger.jsonl"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--selfplay",
        action="store_true",
        help=f"Inspect the self-play ledger ({SELFPLAY_LEDGER}) instead of production",
    )
    group.add_argument(
        "--path",
        type=str,
        default=None,
        help="Explicit path to a ledger JSONL file",
    )
    parser.add_argument(
        "--show",
        type=int,
        default=30,
        help="How many leading + trailing rows of the timeline to show (default 30 + 10)",
    )
    return parser.parse_args()


def _resolve_path(args: argparse.Namespace) -> Path:
    if args.path:
        return Path(args.path)
    if args.selfplay:
        return SELFPLAY_LEDGER
    return PRODUCTION_LEDGER


def main() -> None:
    args = _parse_args()
    ledger = _resolve_path(args)
    print(f"Ledger: {ledger}")
    if not ledger.exists():
        print("NO LEDGER FOUND")
        # Show the alternative path as a hint
        alt = SELFPLAY_LEDGER if not args.selfplay and not args.path else PRODUCTION_LEDGER
        if alt.exists():
            print(f"(but {alt} exists — re-run with the other --flag if that's what you wanted)")
        sys.exit(1)

    entries = [
        json.loads(line)
        for line in ledger.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    print(f"Total entries: {len(entries)}")
    if not entries:
        print("(empty ledger)")
        return

    total = sum(e.get("cost_usd", 0) for e in entries)
    print(f"Total spent: ${total:.4f}")

    # By operation. LedgerEntry has 'operation' field (not 'operation_name').
    by_op: dict[str, dict[str, float]] = defaultdict(lambda: {"count": 0, "cost": 0.0})
    by_model: dict[str, float] = defaultdict(float)
    for e in entries:
        op = e.get("operation", "?")
        by_op[op]["count"] += 1
        by_op[op]["cost"] += e.get("cost_usd", 0)
        by_model[e.get("model", "?")] += e.get("cost_usd", 0)

    print("\nBy operation:")
    for op, d in sorted(by_op.items(), key=lambda x: -x[1]["cost"]):
        print(f"  {op:30s} {int(d['count']):3d} calls  ${d['cost']:.4f}")

    print("\nBy model:")
    for model, cost in sorted(by_model.items(), key=lambda x: -x[1]):
        print(f"  {model:45s} ${cost:.4f}")

    # Cumulative spend timeline
    head = args.show
    tail = max(10, args.show // 3)
    print(f"\nCumulative spend timeline (first {head}, last {tail}):")
    running = 0.0
    for i, e in enumerate(entries):
        running += e.get("cost_usd", 0)
        ts = e.get("timestamp", "?")
        ts_tail = ts[-8:] if len(ts) >= 8 else ts
        if i < head or i >= len(entries) - tail:
            print(
                f"  [{i:3d}] +${e.get('cost_usd', 0):.4f}  "
                f"running=${running:.4f}  ts={ts_tail}"
            )
        elif i == head:
            print("  ...")

    print(f"\nFinal running: ${running:.4f}")

    # Show recent failures if any
    failures = [e for e in entries if not e.get("success", True)]
    if failures:
        print(f"\nFailures: {len(failures)} (last 5)")
        for e in failures[-5:]:
            print(f"  ts={e.get('timestamp', '?')[-8:]}  op={e.get('operation', '?')}  err={e.get('error', '?')[:80]}")


if __name__ == "__main__":
    main()
