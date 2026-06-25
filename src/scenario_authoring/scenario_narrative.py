"""Deterministic narrative re-skin core for scenario_authoring.

apply_relabel   — rename faction/issue/outcome identifiers under a bijective map,
                  preserving all numeric scores/BATNAs/coalition_values unchanged.
assert_structure_preserved — value-isomorphism guard: raises AssertionError if the
                  reskinned analysis drifts from the source under the relabel_map.

Both functions are stdlib-only (no LLM, no sibling imports beyond this module).
The LLM layer that emits the relabel_map + prose lives in reskin_scenario (step 48.3).
"""

from __future__ import annotations

import copy
from typing import Any


def _validate_relabel_map(relabel_map: dict[str, dict[str, str]]) -> None:
    """Raise ValueError if relabel_map is missing required keys or has non-str values."""
    for section in ("factions", "issues", "outcomes"):
        if section not in relabel_map:
            raise ValueError(f"relabel_map missing required key: '{section}'")
        mapping = relabel_map[section]
        if not isinstance(mapping, dict):
            raise ValueError(f"relabel_map['{section}'] must be a dict")
        for k, v in mapping.items():
            if not isinstance(k, str) or not isinstance(v, str):
                raise ValueError(
                    f"relabel_map['{section}'] must map str → str; got {k!r} → {v!r}"
                )


def _check_bijective(relabel_map: dict[str, dict[str, str]], section: str) -> None:
    """Raise AssertionError if the section mapping is not injective (not bijective)."""
    mapping = relabel_map[section]
    new_names = list(mapping.values())
    if len(new_names) != len(set(new_names)):
        seen: set[str] = set()
        dupes = [n for n in new_names if n in seen or seen.add(n)]  # type: ignore[func-returns-value]
        raise AssertionError(
            f"relabel_map['{section}'] is not bijective: duplicate new names {dupes}"
        )


def _check_complete(
    relabel_map: dict[str, dict[str, str]],
    source: dict[str, Any],
) -> None:
    """Raise AssertionError if any identifier in source is absent from relabel_map."""
    faction_map = relabel_map["factions"]
    issue_map = relabel_map["issues"]
    outcome_map = relabel_map["outcomes"]

    for f in source["factions"]:
        if f not in faction_map:
            raise AssertionError(
                f"relabel_map.factions is incomplete: missing '{f}'"
            )
    for issue in source["issues"]:
        if issue["name"] not in issue_map:
            raise AssertionError(
                f"relabel_map.issues is incomplete: missing '{issue['name']}'"
            )
        for outcome in issue["outcomes"]:
            if outcome not in outcome_map:
                raise AssertionError(
                    f"relabel_map.outcomes is incomplete: missing '{outcome}'"
                )


def apply_relabel(
    analysis: dict[str, Any],
    relabel_map: dict[str, dict[str, str]],
) -> dict[str, Any]:
    """Return a deep-copied analysis with all identifiers renamed under relabel_map.

    relabel_map must have three string-to-string sub-dicts:
      "factions": {old_faction_id: new_faction_id, ...}
      "issues":   {old_issue_name: new_issue_name, ...}
      "outcomes": {old_outcome: new_outcome, ...}  (flat across all issues)

    All numeric scores, BATNAs, and coalition_values numeric payoffs are preserved
    unchanged.  Prose fields (logrolling list items, issue descriptions,
    deception_tactics values) are copied as-is; reskin_scenario replaces them
    with LLM-authored prose.

    Raises ValueError for a structurally malformed relabel_map.
    Does NOT validate bijectivity or completeness — call assert_structure_preserved
    afterwards to enforce the isomorphism contract.
    """
    _validate_relabel_map(relabel_map)

    faction_map = relabel_map["factions"]
    issue_map = relabel_map["issues"]
    outcome_map = relabel_map["outcomes"]

    result: dict[str, Any] = {}

    result["factions"] = [faction_map.get(f, f) for f in analysis["factions"]]

    new_issues = []
    for issue in analysis["issues"]:
        new_issues.append(
            {
                "name": issue_map.get(issue["name"], issue["name"]),
                "outcomes": [outcome_map.get(o, o) for o in issue["outcomes"]],
                "description": issue.get("description", ""),
            }
        )
    result["issues"] = new_issues

    new_scoring: dict[str, Any] = {}
    for faction, issue_scores in analysis.get("scoring", {}).items():
        new_faction = faction_map.get(faction, faction)
        new_issue_scores: dict[str, Any] = {}
        for issue_name, outcome_scores in issue_scores.items():
            new_issue_name = issue_map.get(issue_name, issue_name)
            new_issue_scores[new_issue_name] = {
                outcome_map.get(outcome, outcome): score
                for outcome, score in outcome_scores.items()
            }
        new_scoring[new_faction] = new_issue_scores
    result["scoring"] = new_scoring

    result["batna"] = {
        faction_map.get(f, f): v for f, v in analysis.get("batna", {}).items()
    }

    result["deception_tactics"] = {
        faction_map.get(f, f): text
        for f, text in analysis.get("deception_tactics", {}).items()
    }

    result["logrolling"] = copy.deepcopy(analysis.get("logrolling", []))

    result["game_mode"] = analysis.get("game_mode", "mixed")

    pressure = analysis.get("pressure", {})
    result["pressure"] = {
        "round_cost_decay": pressure.get("round_cost_decay", 0),
        "asymmetric_clocks": {
            faction_map.get(f, f): v
            for f, v in pressure.get("asymmetric_clocks", {}).items()
        },
        "penalty_floor_offset": pressure.get("penalty_floor_offset", 0),
    }

    result["pressure_profile"] = copy.deepcopy(analysis.get("pressure_profile", {}))

    new_cv = []
    for entry in analysis.get("coalition_values", []):
        new_cv.append(
            {
                "members": [faction_map.get(f, f) for f in entry["members"]],
                "values": {
                    faction_map.get(f, f): v for f, v in entry.get("values", {}).items()
                },
            }
        )
    result["coalition_values"] = new_cv

    return result


def assert_structure_preserved(
    source: dict[str, Any],
    reskinned: dict[str, Any],
    relabel_map: dict[str, dict[str, str]],
) -> None:
    """Assert that reskinned is a valid value-isomorphic relabeling of source.

    Checks (raises AssertionError with a descriptive message on the first failure):
      1. relabel_map is complete (every source identifier has a mapping)
      2. relabel_map is bijective (no two source identifiers share a new name)
      3. Faction, issue, and outcome counts match
      4. Every score in reskinned["scoring"] equals the source score under relabel
      5. Every batna in reskinned["batna"] equals the source batna under faction relabel
      6. coalition_values member sets and payoff values are preserved under faction relabel

    This guard is the single source of truth for "numeric structure unchanged".
    """
    _validate_relabel_map(relabel_map)

    faction_map = relabel_map["factions"]
    issue_map = relabel_map["issues"]
    outcome_map = relabel_map["outcomes"]

    # --- completeness ---
    _check_complete(relabel_map, source)

    # --- bijectivity ---
    _check_bijective(relabel_map, "factions")
    _check_bijective(relabel_map, "issues")
    _check_bijective(relabel_map, "outcomes")

    # --- structural counts ---
    src_factions = source["factions"]
    src_issues = source["issues"]

    if len(reskinned.get("factions", [])) != len(src_factions):
        raise AssertionError(
            f"faction count mismatch: source {len(src_factions)}, "
            f"reskinned {len(reskinned.get('factions', []))}"
        )
    if len(reskinned.get("issues", [])) != len(src_issues):
        raise AssertionError(
            f"issue count mismatch: source {len(src_issues)}, "
            f"reskinned {len(reskinned.get('issues', []))}"
        )

    reskinned_issue_by_name = {
        issue["name"]: issue for issue in reskinned.get("issues", [])
    }
    for src_issue in src_issues:
        new_issue_name = issue_map[src_issue["name"]]
        if new_issue_name not in reskinned_issue_by_name:
            raise AssertionError(
                f"missing issue in reskinned: '{new_issue_name}'"
            )
        res_issue = reskinned_issue_by_name[new_issue_name]
        if len(res_issue.get("outcomes", [])) != len(src_issue["outcomes"]):
            raise AssertionError(
                f"outcome count mismatch for issue '{new_issue_name}': "
                f"source {len(src_issue['outcomes'])}, "
                f"reskinned {len(res_issue.get('outcomes', []))}"
            )

    # --- scoring value isomorphism ---
    res_scoring = reskinned.get("scoring", {})
    for src_faction in src_factions:
        new_faction = faction_map[src_faction]
        if new_faction not in res_scoring:
            raise AssertionError(
                f"missing faction in reskinned scoring: '{new_faction}'"
            )
        for src_issue in src_issues:
            new_issue_name = issue_map[src_issue["name"]]
            if new_issue_name not in res_scoring[new_faction]:
                raise AssertionError(
                    f"missing issue in reskinned scoring['{new_faction}']: '{new_issue_name}'"
                )
            for src_outcome in src_issue["outcomes"]:
                new_outcome = outcome_map[src_outcome]
                if new_outcome not in res_scoring[new_faction][new_issue_name]:
                    raise AssertionError(
                        f"missing outcome in reskinned "
                        f"scoring['{new_faction}']['{new_issue_name}']: '{new_outcome}'"
                    )
                src_score = source["scoring"][src_faction][src_issue["name"]][src_outcome]
                res_score = res_scoring[new_faction][new_issue_name][new_outcome]
                if res_score != src_score:
                    raise AssertionError(
                        f"score drift at [{new_faction!r}][{new_issue_name!r}]"
                        f"[{new_outcome!r}]: expected {src_score}, got {res_score}"
                    )

    # --- batna value isomorphism ---
    res_batna = reskinned.get("batna", {})
    for src_faction in src_factions:
        new_faction = faction_map[src_faction]
        if new_faction not in res_batna:
            raise AssertionError(
                f"missing faction in reskinned batna: '{new_faction}'"
            )
        src_val = source["batna"][src_faction]
        res_val = res_batna[new_faction]
        if res_val != src_val:
            raise AssertionError(
                f"batna drift for faction '{new_faction}': "
                f"expected {src_val}, got {res_val}"
            )

    # --- coalition_values member and value isomorphism ---
    src_cv = source.get("coalition_values", [])
    res_cv = reskinned.get("coalition_values", [])
    if len(res_cv) != len(src_cv):
        raise AssertionError(
            f"coalition_values count mismatch: source {len(src_cv)}, "
            f"reskinned {len(res_cv)}"
        )
    for idx, (src_entry, res_entry) in enumerate(zip(src_cv, res_cv)):
        expected_members = sorted(faction_map[f] for f in src_entry["members"])
        actual_members = sorted(res_entry.get("members", []))
        if actual_members != expected_members:
            raise AssertionError(
                f"coalition_values[{idx}] members mismatch: "
                f"expected {expected_members}, got {actual_members}"
            )
        for src_member in src_entry["members"]:
            new_member = faction_map[src_member]
            if new_member not in res_entry.get("values", {}):
                raise AssertionError(
                    f"coalition_values[{idx}] missing value for '{new_member}'"
                )
            src_val = src_entry["values"][src_member]
            res_val = res_entry["values"][new_member]
            if res_val != src_val:
                raise AssertionError(
                    f"coalition_values[{idx}] value drift for '{new_member}': "
                    f"expected {src_val}, got {res_val}"
                )
