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
DEFAULT_STATE_PATCH_SCHEMA_PATH = Path("config/schemas/state_patch.json")
_CONTINGENCY_MARKERS = ("contingent on", "conditional on", "if ")


def state_patch_entity_types(
    schema_path: str | Path = DEFAULT_STATE_PATCH_SCHEMA_PATH,
) -> list[str]:
    """Return state patch root entity keys in schema order."""
    schema = json.loads(Path(schema_path).read_text(encoding="utf-8"))
    properties = schema.get("properties", {})
    if not isinstance(properties, dict):
        raise ValueError("State patch schema properties must be an object")
    return list(properties.keys())


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


def compute_near_miss(results: dict[str, Any]) -> dict[str, Any]:
    """Detect near-miss convergence patterns from self-play results."""
    scenario_analysis = results.get("scenario_analysis")
    if not isinstance(scenario_analysis, dict):
        return {
            "near_miss": None,
            "converging_factions": [],
            "dissenting_faction": None,
            "defection_event_log": [],
        }

    issues = _scenario_issues(scenario_analysis)
    if not issues:
        return {
            "near_miss": False,
            "converging_factions": [],
            "dissenting_faction": None,
            "defection_event_log": [],
        }

    factions = _scenario_factions(scenario_analysis, results.get("agents", {}))
    round_responses = results.get("round_responses", {})
    final_round_key = _latest_round_key(round_responses, results.get("rounds_completed"))
    if final_round_key is None:
        return {
            "near_miss": False,
            "converging_factions": [],
            "dissenting_faction": None,
            "defection_event_log": [],
        }

    final_positions: dict[str, dict[str, str | None]] = {}
    for faction_id in factions:
        final_positions[faction_id] = _extract_positions_for_round(
            scenario_analysis,
            _round_response_text(round_responses, final_round_key, faction_id),
        )
    previous_round_key = _previous_round_key(round_responses, final_round_key)
    previous_positions: dict[str, dict[str, str | None]] = {}
    if previous_round_key is not None:
        for faction_id in factions:
            previous_positions[faction_id] = _extract_positions_for_round(
                scenario_analysis,
                _round_response_text(round_responses, previous_round_key, faction_id),
            )
    defection_event_log = _build_defection_event_log(
        scenario_analysis,
        round_responses,
        factions,
    )

    near_miss = False
    converging_factions: list[str] = []
    dissenting_faction: str | None = None
    candidate: tuple[int, int, list[str], str] | None = None
    for issue in issues:
        issue_name = str(issue["name"])
        issue_positions = {
            faction_id: final_positions[faction_id].get(issue_name)
            for faction_id in factions
        }
        if any(position is None for position in issue_positions.values()):
            continue

        grouped_factions: dict[str | None, list[str]] = {}
        for faction_id, position in issue_positions.items():
            grouped_factions.setdefault(position, []).append(faction_id)

        if len(grouped_factions) != 2:
            continue

        majority_position, majority_factions = max(
            grouped_factions.items(),
            key=lambda item: len(item[1]),
        )
        if len(majority_factions) != len(factions) - 1:
            continue

        issue_dissent = next(
            (faction for faction in factions if faction not in majority_factions),
            None,
        )
        if issue_dissent is None:
            continue

        if previous_round_key is None:
            continue

        previous_issue_positions = {
            faction_id: previous_positions[faction_id].get(issue_name)
            for faction_id in factions
        }
        if any(position is None for position in previous_issue_positions.values()):
            continue

        previous_grouped: dict[str | None, list[str]] = {}
        for faction_id, position in previous_issue_positions.items():
            previous_grouped.setdefault(position, []).append(faction_id)
        previous_majority_position, previous_majority_factions = max(
            previous_grouped.items(),
            key=lambda item: len(item[1]),
        )
        if len(previous_majority_factions) < 2:
            continue
        if previous_issue_positions[issue_dissent] != previous_majority_position:
            continue

        current_candidate = (
            len(previous_majority_factions),
            next((index for index, known_issue in enumerate(issues) if known_issue is issue), 0),
            majority_factions,
            issue_dissent,
        )
        if candidate is None or current_candidate > candidate:
            candidate = current_candidate

    if candidate is not None:
        near_miss = True
        converging_factions = candidate[2]
        dissenting_faction = candidate[3]

    return {
        "near_miss": near_miss,
        "converging_factions": converging_factions,
        "dissenting_faction": dissenting_faction,
        "defection_event_log": defection_event_log,
    }


def analyze_results(
    results: dict,
    state_patch_schema_path: str | Path = DEFAULT_STATE_PATCH_SCHEMA_PATH,
) -> None:
    """Print a formatted analysis report from simulation results."""
    rounds = results.get("rounds_completed", 0)
    transcript = results.get("transcript", [])
    agents = results.get("agents", {})
    round_responses = results.get("round_responses", {})
    entity_types = state_patch_entity_types(state_patch_schema_path)

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
        intelligence = data.get("intelligence", [])

        print(f"\n  [{faction_id.upper()}]")
        for entity_type in entity_types:
            label = entity_type.replace("_", " ").title()
            print(f"    {label} tracked:       {len(data.get(entity_type, []))}")
        print(f"    Intelligence reports:   {len(intelligence)}")
        print(f"    Final round number:     {data.get('round', '?')}")

        promises = data.get("promises", [])
        if promises:
            print("    Promise details:")
            for p in promises:
                status = p.get("status", "?")
                from_f = p.get("from_faction", "?")
                to_f = p.get("to_faction", "?")
                desc = p.get("description", "")[:80]
                print(f"      {from_f} -> {to_f}: {status} - {desc}")

        coalitions = data.get("coalitions", [])
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

    # No-deal-aware scoring.
    scores = results.get("scores", {})
    if scores:
        print(f"\n{'-'*60}")
        print("  NO-DEAL-AWARE SCORING")
        print(f"{'-'*60}")
        print(f"    pareto_efficiency: {float(scores.get('pareto_efficiency', 0.0)):.3f}")
        print(
            "    negotiated_surplus_share: "
            f"{float(scores.get('negotiated_surplus_share', 0.0)):.3f}"
        )
        print(
            "    delta_above_batna_sum: "
            f"{float(scores.get('delta_above_batna_sum', 0.0)):.3f}"
        )
        print(
            "    min_faction_delta: "
            f"{float(scores.get('min_faction_delta', 0.0)):.3f}"
        )
        print(
            "    surplus_distribution_stdev: "
            f"{float(scores.get('surplus_distribution_stdev', 0.0)):.3f}"
        )
        faction_deltas = scores.get("faction_deltas", {})
        if faction_deltas:
            print("    faction_deltas:")
            for faction_id, delta in sorted(faction_deltas.items()):
                print(f"      {faction_id}: {float(delta):+.3f}")
        else:
            print("    faction_deltas: n/a")

    near_miss_data = compute_near_miss(results)
    if near_miss_data.get("near_miss") is not None:
        print(f"\n{'-'*60}")
        print("  NEAR-MISS DIAGNOSTIC")
        print(f"{'-'*60}")
        print(f"    near_miss: {near_miss_data['near_miss']}")
        converging_factions = near_miss_data.get("converging_factions", [])
        if converging_factions:
            print(
                "    converging_factions: "
                + ", ".join(str(faction) for faction in converging_factions)
            )
        else:
            print("    converging_factions: n/a")
        dissenting_faction = near_miss_data.get("dissenting_faction")
        print(
            "    dissenting_faction: "
            f"{dissenting_faction if dissenting_faction is not None else 'n/a'}"
        )
        defection_event_log = near_miss_data.get("defection_event_log", [])
        if defection_event_log:
            print("    defection_event_log:")
            for entry in defection_event_log:
                print(
                    "      "
                    f"R{entry['round_from']}->{entry['round_to']} "
                    f"[{entry['faction']}] {entry['issue']}: "
                    f"{entry['from_position']} -> {entry['to_position']} "
                    f"contingent={entry['was_contingent']}"
                )
        else:
            print("    defection_event_log: n/a")

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


def _scenario_issues(scenario_analysis: dict[str, Any]) -> list[dict[str, Any]]:
    issues = scenario_analysis.get("issues", [])
    if not isinstance(issues, list):
        return []
    return [issue for issue in issues if isinstance(issue, dict) and issue.get("name")]


def _scenario_factions(
    scenario_analysis: dict[str, Any],
    agents: dict[str, Any],
) -> list[str]:
    factions = scenario_analysis.get("factions", [])
    if isinstance(factions, list) and factions:
        return [str(faction) for faction in factions if str(faction).strip()]
    return [str(faction) for faction in agents.keys()]


def _latest_round_key(
    round_responses: dict[str, Any],
    rounds_completed: Any,
) -> str | None:
    if not isinstance(round_responses, dict) or not round_responses:
        return None
    if rounds_completed is not None:
        candidate = str(rounds_completed)
        if candidate in round_responses:
            return candidate

    numeric_rounds = []
    for key in round_responses.keys():
        try:
            numeric_rounds.append((int(str(key)), str(key)))
        except (TypeError, ValueError):
            continue
    if not numeric_rounds:
        return next(iter(round_responses.keys()))
    return max(numeric_rounds, key=lambda item: item[0])[1]


def _previous_round_key(
    round_responses: dict[str, Any],
    final_round_key: str,
) -> str | None:
    if not isinstance(round_responses, dict) or not round_responses:
        return None
    try:
        final_round = int(str(final_round_key))
    except (TypeError, ValueError):
        return None

    previous_rounds = sorted(
        {
            int(str(key))
            for key in round_responses.keys()
            if str(key).isdigit() and int(str(key)) < final_round
        }
    )
    if not previous_rounds:
        return None
    return str(previous_rounds[-1])


def _last_change_round(
    defection_event_log: list[dict[str, Any]],
    *,
    faction_id: str,
    issue_name: str,
) -> int | None:
    rounds = [
        int(entry["round_to"])
        for entry in defection_event_log
        if entry.get("faction") == faction_id and entry.get("issue") == issue_name
    ]
    if not rounds:
        return None
    return max(rounds)


def _round_response_text(
    round_responses: dict[str, Any],
    round_key: str,
    faction_id: str,
) -> str:
    responses = round_responses.get(round_key)
    if not isinstance(responses, dict):
        responses = round_responses.get(str(round_key), {})
    if not isinstance(responses, dict):
        return ""
    response = responses.get(faction_id, "")
    return response if isinstance(response, str) else str(response)


def _extract_positions_for_round(
    scenario_analysis: dict[str, Any],
    response_text: str,
) -> dict[str, str | None]:
    positions: dict[str, str | None] = {}
    for issue in _scenario_issues(scenario_analysis):
        issue_name = str(issue["name"])
        position = None
        for outcome in issue.get("outcomes", []):
            outcome_text = str(outcome)
            if _response_matches_outcome(response_text, outcome_text):
                position = outcome_text
                break
        positions[issue_name] = position
    return positions


def _build_defection_event_log(
    scenario_analysis: dict[str, Any],
    round_responses: dict[str, Any],
    factions: list[str],
) -> list[dict[str, Any]]:
    issue_names = [str(issue["name"]) for issue in _scenario_issues(scenario_analysis)]
    numeric_rounds = sorted(
        {
            int(str(key))
            for key in round_responses.keys()
            if str(key).isdigit()
        }
    )
    if len(numeric_rounds) < 2:
        return []

    log: list[dict[str, Any]] = []
    for previous_round, current_round in zip(numeric_rounds, numeric_rounds[1:]):
        previous_key = str(previous_round)
        current_key = str(current_round)
        for faction_id in factions:
            previous_positions = _extract_positions_for_round(
                scenario_analysis,
                _round_response_text(round_responses, previous_key, faction_id),
            )
            current_positions = _extract_positions_for_round(
                scenario_analysis,
                _round_response_text(round_responses, current_key, faction_id),
            )
            previous_text = _round_response_text(round_responses, previous_key, faction_id)
            was_contingent = _is_contingent(previous_text)

            for issue_name in issue_names:
                previous_position = previous_positions.get(issue_name)
                current_position = current_positions.get(issue_name)
                if previous_position == current_position:
                    continue
                log.append(
                    {
                        "round_from": previous_round,
                        "round_to": current_round,
                        "faction": faction_id,
                        "issue": issue_name,
                        "from_position": previous_position,
                        "to_position": current_position,
                        "was_contingent": was_contingent,
                    }
                )

    return log


def _is_contingent(response_text: str) -> bool:
    lowered = response_text.lower()
    return any(marker in lowered for marker in _CONTINGENCY_MARKERS)


def _response_matches_outcome(response_text: str, outcome_text: str) -> bool:
    response_tokens = _tokenize(response_text)
    outcome_tokens = _tokenize(outcome_text)
    if not response_tokens or not outcome_tokens:
        return False
    if _is_subsequence(outcome_tokens, response_tokens):
        return True
    return outcome_tokens[0] in response_tokens


def _tokenize(text: str) -> list[str]:
    import re

    return re.findall(r"[a-z0-9]+", text.lower())


def _is_subsequence(needle: list[str], haystack: list[str]) -> bool:
    if len(needle) > len(haystack):
        return False
    index = 0
    for token in haystack:
        if token == needle[index]:
            index += 1
            if index == len(needle):
                return True
    return False


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
