"""Post-game analysis for self-play simulation results.

    python -m tests.self_play.analysis --results tests/self_play/results/run_*.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def analyze_results(results: dict) -> None:
    """Print a formatted analysis report from simulation results."""
    rounds = results.get("rounds_completed", 0)
    transcript = results.get("transcript", [])
    agents = results.get("agents", {})
    round_responses = results.get("round_responses", {})

    print(f"\n{'='*60}")
    print("  SELF-PLAY ANALYSIS REPORT")
    print(f"{'='*60}")

    # Overview.
    print(f"\n  Rounds completed: {rounds}")
    print(f"  Total messages in transcript: {len(transcript)}")
    print(f"  Factions: {', '.join(agents.keys())}")

    # Per-agent summary.
    print(f"\n{'-'*60}")
    print("  PER-AGENT SUMMARY")
    print(f"{'-'*60}")

    for faction_id, data in agents.items():
        promises = data.get("promises", [])
        coalitions = data.get("coalitions", [])
        inconsistencies = data.get("inconsistencies", [])
        intelligence = data.get("intelligence", [])

        print(f"\n  [{faction_id.upper()}]")
        print(f"    Promises tracked:       {len(promises)}")
        print(f"    Coalitions detected:    {len(coalitions)}")
        print(f"    Inconsistencies found:  {len(inconsistencies)}")
        print(f"    Intelligence reports:   {len(intelligence)}")
        print(f"    Final round number:     {data.get('round', '?')}")

        if promises:
            print("    Promise details:")
            for p in promises:
                status = p.get("status", "?")
                from_f = p.get("from_faction", "?")
                to_f = p.get("to_faction", "?")
                desc = p.get("description", "")[:80]
                print(f"      {from_f} -> {to_f}: {status} - {desc}")

        if coalitions:
            print("    Coalition details:")
            for c in coalitions:
                members = c.get("members", c.get("factions", "?"))
                strength = c.get("strength", "?")
                print(f"      members={members}, strength={strength}")

    # Communication analysis.
    print(f"\n{'-'*60}")
    print("  COMMUNICATION ANALYSIS")
    print(f"{'-'*60}")

    sender_counts: dict[str, int] = {}
    for msg in transcript:
        sender = msg.get("sender", "unknown")
        sender_counts[sender] = sender_counts.get(sender, 0) + 1

    for sender, count in sorted(sender_counts.items(), key=lambda x: -x[1]):
        print(f"    {sender}: {count} messages")

    # Per-round responses.
    if round_responses:
        print(f"\n{'-'*60}")
        print("  ROUND-BY-ROUND RESPONSES")
        print(f"{'-'*60}")

        for round_num in sorted(round_responses.keys(), key=int):
            responses = round_responses[round_num]
            print(f"\n  Round {round_num}:")
            for faction_id, response in responses.items():
                truncated = response[:200] + "..." if len(response) > 200 else response
                # Replace newlines for compact display.
                truncated = truncated.replace("\n", " ")
                print(f"    [{faction_id}] {truncated}")

    # Promise cross-reference.
    print(f"\n{'-'*60}")
    print("  PROMISE CROSS-REFERENCE")
    print(f"{'-'*60}")

    all_promises: list[dict] = []
    for faction_id, data in agents.items():
        for p in data.get("promises", []):
            p_copy = dict(p)
            p_copy["_tracked_by"] = faction_id
            all_promises.append(p_copy)

    if all_promises:
        # Group by from_faction -> to_faction.
        pairs: dict[str, list[dict]] = {}
        for p in all_promises:
            key = f"{p.get('from_faction', '?')} -> {p.get('to_faction', '?')}"
            pairs.setdefault(key, []).append(p)

        for pair, items in sorted(pairs.items()):
            statuses = [i.get("status", "?") for i in items]
            trackers = [i.get("_tracked_by", "?") for i in items]
            print(f"    {pair}: tracked by {trackers}, statuses={statuses}")
    else:
        print("    (no promises tracked by any agent)")

    print(f"\n{'='*60}")
    print("  END OF REPORT")
    print(f"{'='*60}\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Analyze self-play simulation results."
    )
    parser.add_argument(
        "--results",
        type=str,
        required=True,
        help="Path to simulation results JSON file",
    )
    args = parser.parse_args()

    path = Path(args.results)
    if not path.is_file():
        print(f"ERROR: results file not found: {path}", file=sys.stderr)
        sys.exit(1)

    results = json.loads(path.read_text(encoding="utf-8"))
    analyze_results(results)


if __name__ == "__main__":
    main()
