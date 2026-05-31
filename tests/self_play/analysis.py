"""Post-game analysis for self-play simulation results.

    python -m tests.self_play.analysis --results tests/self_play/results/run_*.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


_BROKEN_PROMISE_STATUSES = {"broken"}
_INACTIVE_COALITION_STATUSES = {"broken", "dissolved", "ended", "void"}
_DEAL_MARKERS = (
    "deal reached",
    "agreement reached",
    "we have a deal",
    "final agreement",
    "binding agreement",
)


def compute_process_signatures(results: dict[str, Any]) -> dict[str, Any]:
    """Compute deterministic process signatures from self-play results."""
    agents = results.get("agents", {})
    promises = _unique_records(
        (
            promise
            for data in agents.values()
            for promise in data.get("promises", [])
        ),
        "promise_id",
    )
    coalitions = _unique_records(
        (
            coalition
            for data in agents.values()
            for coalition in data.get("coalitions", [])
        ),
        "coalition_id",
    )

    total_promises = len(promises)
    broken = sum(
        1
        for promise in promises
        if str(promise.get("status", "")).lower() in _BROKEN_PROMISE_STATUSES
    )

    formed = len(coalitions)
    survived = sum(
        1
        for coalition in coalitions
        if _coalition_survived(coalition, results.get("rounds_completed", 0))
    )

    return {
        "broken_promise_rate": broken / total_promises if total_promises else 0.0,
        "coalition_stability": survived / formed if formed else 0.0,
        "time_to_deal": _time_to_deal(results),
        "opening_gap": _opening_gap(results),
    }


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

    # Process signatures.
    signatures = results.get("process_signatures") or compute_process_signatures(results)
    print(f"\n{'-'*60}")
    print("  PROCESS SIGNATURES")
    print(f"{'-'*60}")
    print(f"    broken_promise_rate: {signatures['broken_promise_rate']:.3f}")
    print(f"    coalition_stability: {signatures['coalition_stability']:.3f}")
    print(f"    time_to_deal: {signatures['time_to_deal']}")
    opening_gap = signatures.get("opening_gap", {})
    if opening_gap:
        print("    opening_gap:")
        for faction_id, gap in sorted(opening_gap.items()):
            value = "n/a" if gap is None else f"{gap:.3f}"
            print(f"      {faction_id}: {value}")
    else:
        print("    opening_gap: n/a")

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


def _unique_records(records: Any, id_key: str) -> list[dict[str, Any]]:
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for idx, record in enumerate(records):
        if not isinstance(record, dict):
            continue
        record_id = str(record.get(id_key) or f"__idx_{idx}")
        if record_id in seen:
            continue
        seen.add(record_id)
        unique.append(record)
    return unique


def _coalition_survived(coalition: dict[str, Any], final_round: int) -> bool:
    status = str(coalition.get("status", "")).lower()
    if status in _INACTIVE_COALITION_STATUSES:
        return False
    ended_round = coalition.get("ended_round") or coalition.get("dissolved_round")
    if ended_round is None:
        return True
    try:
        return int(ended_round) >= int(final_round)
    except (TypeError, ValueError):
        return True


def _time_to_deal(results: dict[str, Any]) -> int | None:
    transcript = results.get("transcript", [])
    for message in transcript:
        content = str(message.get("content", "")).lower()
        if any(marker in content for marker in _DEAL_MARKERS):
            round_number = _message_round(message)
            if round_number is not None:
                return round_number
    if results.get("scores", {}).get("deal_reached"):
        return results.get("rounds_completed")
    return None


def _message_round(message: dict[str, Any]) -> int | None:
    for key in ("round", "round_number"):
        if key in message:
            try:
                return int(message[key])
            except (TypeError, ValueError):
                return None
    return None


def _opening_gap(results: dict[str, Any]) -> dict[str, float | None]:
    scenario_analysis = results.get("scenario_analysis")
    scores = results.get("scores", {})
    round_one = results.get("round_responses", {}).get("1", {})
    if not scenario_analysis or not scores or not round_one:
        return {}

    final_scores = scores.get("faction_scores", {})
    gaps: dict[str, float | None] = {}
    for faction_id in scenario_analysis.get("factions", []):
        opening_score = _score_position_text(
            str(round_one.get(faction_id, "")),
            scenario_analysis,
            faction_id,
        )
        max_possible = _max_possible_score(scenario_analysis, faction_id)
        final_score = final_scores.get(faction_id, {}).get("points")
        if opening_score is None or final_score is None or max_possible <= 0:
            gaps[faction_id] = None
            continue
        gaps[faction_id] = abs(opening_score - float(final_score)) / max_possible
    return gaps


def _score_position_text(
    text: str,
    scenario_analysis: dict[str, Any],
    faction_id: str,
) -> float | None:
    scoring = scenario_analysis.get("scoring", {}).get(faction_id, {})
    if not scoring:
        return None

    lowered = text.lower()
    total = 0.0
    matched_any = False
    for issue in scenario_analysis.get("issues", []):
        issue_name = issue.get("name")
        if not issue_name:
            continue
        for outcome in issue.get("outcomes", []):
            if str(outcome).lower() in lowered:
                total += float(scoring.get(issue_name, {}).get(outcome, 0.0))
                matched_any = True
                break
    return total if matched_any else None


def _max_possible_score(scenario_analysis: dict[str, Any], faction_id: str) -> float:
    scoring = scenario_analysis.get("scoring", {}).get(faction_id, {})
    total = 0.0
    for issue in scenario_analysis.get("issues", []):
        issue_scores = scoring.get(issue.get("name"), {})
        total += max((float(value) for value in issue_scores.values()), default=0.0)
    return total


if __name__ == "__main__":
    main()
