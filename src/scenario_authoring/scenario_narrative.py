"""Deterministic narrative re-skin core for scenario_authoring.

apply_relabel   — rename faction/issue/outcome identifiers under a bijective map,
                  preserving all numeric scores/BATNAs/coalition_values unchanged.
assert_structure_preserved — value-isomorphism guard: raises AssertionError if the
                  reskinned analysis drifts from the source under the relabel_map.
extract_catalogue_entry — heading-scoped section slice over the prose catalogue.
reskin_scenario — LLM re-skin: one structured_call emitting relabel_map + prose,
                  apply_relabel, assert_structure_preserved, return (analysis, md).
"""

from __future__ import annotations

import copy
import json
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


def _heading_level(line: str) -> int:
    """Return the Markdown heading level (1–6) for a line, or 0 if not a heading."""
    if not line.startswith("#"):
        return 0
    stripped = line.lstrip("#")
    if not stripped.startswith(" "):
        return 0
    return len(line) - len(stripped)


def extract_catalogue_entry(catalogue_text: str, heading: str) -> str:
    """Return the heading-scoped section for *heading* from *catalogue_text*.

    Finds the line exactly matching *heading*, then collects all lines until the
    next heading of equal or higher Markdown level (or end of document).

    Raises ValueError if *heading* is not a valid Markdown heading or is not
    found in *catalogue_text*.
    """
    target_level = _heading_level(heading)
    if target_level == 0:
        raise ValueError(
            f"heading must be a valid Markdown heading starting with '#': {heading!r}"
        )

    lines = catalogue_text.splitlines()

    start_idx: int | None = None
    for i, line in enumerate(lines):
        if line.rstrip() == heading.rstrip():
            start_idx = i
            break

    if start_idx is None:
        raise ValueError(f"Heading not found in catalogue: {heading!r}")

    result_lines = [lines[start_idx]]
    for line in lines[start_idx + 1 :]:
        lvl = _heading_level(line)
        if lvl > 0 and lvl <= target_level:
            break
        result_lines.append(line)

    return "\n".join(result_lines)


# ---------------------------------------------------------------------------
# reskin_scenario — LLM re-skin (step 48.3)
# ---------------------------------------------------------------------------

RESKIN_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["relabel_map", "logrolling", "deception_tactics", "narrative_md"],
    "properties": {
        "relabel_map": {
            "type": "object",
            "additionalProperties": False,
            "required": ["factions", "issues", "outcomes"],
            "description": "Bijective renaming maps for all identifiers in the scenario.",
            "properties": {
                "factions": {
                    "type": "object",
                    "additionalProperties": {"type": "string"},
                    "description": "old_faction_id -> new themed name",
                },
                "issues": {
                    "type": "object",
                    "additionalProperties": {"type": "string"},
                    "description": "old_issue_name -> new themed name",
                },
                "outcomes": {
                    "type": "object",
                    "additionalProperties": {"type": "string"},
                    "description": "old_outcome -> new themed name (flat across all issues)",
                },
            },
        },
        "logrolling": {
            "type": "array",
            "items": {"type": "string"},
            "description": (
                "3-5 plain-language descriptions of mutually beneficial trades, "
                "using the NEW themed faction/issue/outcome names."
            ),
        },
        "deception_tactics": {
            "type": "object",
            "additionalProperties": {"type": "string"},
            "description": (
                "Per-faction deception tactic (~1-2 sentences), keyed by NEW faction names."
            ),
        },
        "narrative_md": {
            "type": "string",
            "description": (
                "A 2-4 paragraph Markdown scenario narrative using the themed names. "
                "Describes the setting, factions, and the issues at stake. "
                "Does NOT reveal private scoring tables."
            ),
        },
    },
}

RESKIN_SYSTEM_PROMPT = """\
You are a creative scenario designer. Given a multi-party negotiation analysis \
(with generic faction/issue/outcome identifiers) and optional domain context, \
produce a themed re-skin that makes the scenario vivid and concrete.

Your job is to:
1. Create a BIJECTIVE relabel_map: assign a thematic name to every faction, \
issue, and outcome identifier. The mapping must be 1-to-1 — no two source \
identifiers may share the same new name.
2. Write logrolling descriptions (3-5 items) using the NEW themed names.
3. Write per-faction deception tactics (~1-2 sentences each), keyed by the \
NEW faction names, describing what each faction will anchor on early.
4. Write a narrative_md: 2-4 paragraphs in Markdown describing the setting, \
the parties, and what is at stake. Use the new themed names throughout. \
Do NOT reveal numeric scoring or BATNA values.

CRITICAL constraint: the relabel_map must cover EVERY faction, issue, and \
outcome that appears in the source analysis. Missing entries will cause a \
validation error.
"""


def _build_reskin_user_prompt(
    analysis: dict[str, Any],
    source_context: str,
    domain_context: str,
) -> str:
    parts = []
    if source_context.strip():
        parts += [source_context.strip(), ""]
    if domain_context.strip():
        parts += [domain_context.strip(), ""]
    parts += [
        "Source analysis to re-skin:",
        f"  Factions: {', '.join(analysis['factions'])}",
        f"  Issues: {', '.join(i['name'] for i in analysis['issues'])}",
    ]
    for issue in analysis["issues"]:
        parts.append(f"    {issue['name']} outcomes: {', '.join(issue['outcomes'])}")
    parts += [
        f"  Game mode: {analysis.get('game_mode', 'mixed')}",
        "",
        "Scoring structure (numeric values — preserve these exactly):",
        json.dumps(analysis.get("scoring", {}), indent=2),
        "",
        f"BATNAs: {json.dumps(analysis.get('batna', {}))}",
    ]
    coalition = analysis.get("coalition_values", [])
    if coalition:
        parts += ["", f"Coalition values (member ids only): {json.dumps(coalition)}"]
    return "\n".join(parts)


async def reskin_scenario(
    analysis: dict[str, Any],
    source_context: str,
    llm_client: Any,
    llm_config: dict[str, Any],
    tier: str = "commodity",
    *,
    domain_context: str = "",
) -> tuple[dict[str, Any], str]:
    """Apply a themed LLM re-skin to *analysis*.

    Makes one ``structured_call`` that returns a bijective ``relabel_map``
    plus prose (logrolling, deception_tactics, narrative_md).  Then:

    1. Calls ``apply_relabel(analysis, relabel_map)`` to rename identifiers.
    2. Overlays ``logrolling`` and ``deception_tactics`` from the LLM output.
    3. Calls ``assert_structure_preserved`` to confirm numeric values are intact.
    4. Returns ``(reskinned_analysis, narrative_md)``.

    Parameters
    ----------
    analysis:
        Source scenario analysis dict (factions/issues/scoring/batna/…).
    source_context:
        Operator-provided framing text included verbatim in the LLM prompt
        (e.g. a catalogue entry from ``extract_catalogue_entry``).
    llm_client, llm_config, tier:
        Injected toolkit-compatible LLM client and config.
    domain_context:
        Optional additional domain framing (appended after source_context).

    Returns
    -------
    (reskinned_analysis, narrative_md)

    Raises
    ------
    ValueError
        If the LLM call fails.
    AssertionError
        If ``assert_structure_preserved`` rejects the LLM output (numeric drift,
        non-bijective map, incomplete map).
    """
    from toolkit.structured_llm import structured_call

    user_prompt = _build_reskin_user_prompt(analysis, source_context, domain_context)

    result = await structured_call(
        llm_client,
        llm_config,
        tier,
        schema=RESKIN_SCHEMA,
        system_prompt=RESKIN_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        max_retries=2,
        purpose="narrative_reskin",
    )

    if not result.success:
        raise ValueError(f"Reskin failed: {result.error}")

    data = result.data
    relabel_map = data["relabel_map"]

    reskinned = apply_relabel(analysis, relabel_map)
    reskinned["logrolling"] = data["logrolling"]
    new_faction_names = list(relabel_map["factions"].values())
    reskinned["deception_tactics"] = {
        f: data["deception_tactics"].get(f, "")
        for f in new_faction_names
    }

    assert_structure_preserved(analysis, reskinned, relabel_map)

    return reskinned, data["narrative_md"]


def main() -> None:
    """CLI entry point: python -m scenario_authoring narrative [args]"""
    import argparse
    import asyncio
    import json
    import os
    import sys
    from pathlib import Path

    parser = argparse.ArgumentParser(
        prog="scenario_authoring narrative",
        description=(
            "Apply a themed LLM re-skin to a scenario_analysis.json. "
            "Emits scenario_analysis_reskinned.json + narrative.md."
        ),
    )
    parser.add_argument(
        "--analysis", required=True, metavar="PATH",
        help="Path to source scenario_analysis.json",
    )
    parser.add_argument(
        "--catalogue", metavar="PATH",
        help="Prose catalogue .md file (e.g. Multi-Party Negotiation Scenarios.md)",
    )
    parser.add_argument(
        "--catalogue-heading", metavar="HEADING",
        help=(
            "Markdown heading to extract from --catalogue "
            "(e.g. '#### Space Mission'). When omitted, the full "
            "catalogue text is used as source_context."
        ),
    )
    parser.add_argument(
        "--domain-context", default="", metavar="TEXT",
        help="Additional domain framing text (appended after source_context)",
    )
    parser.add_argument(
        "--domain-context-file", metavar="PATH",
        help="File containing domain context (alternative to --domain-context)",
    )
    parser.add_argument(
        "--output-dir", metavar="PATH",
        help="Output directory (default: same directory as --analysis)",
    )
    args = parser.parse_args()

    analysis_path = Path(args.analysis)
    if not analysis_path.exists():
        print(f"ERROR: analysis not found: {analysis_path}", file=sys.stderr)
        sys.exit(1)
    analysis = json.loads(analysis_path.read_text(encoding="utf-8"))

    domain_context = args.domain_context or ""
    if args.domain_context_file:
        dc_path = Path(args.domain_context_file)
        if not dc_path.exists():
            print(f"ERROR: domain context file not found: {dc_path}", file=sys.stderr)
            sys.exit(1)
        domain_context = dc_path.read_text(encoding="utf-8")

    source_context = ""
    if args.catalogue:
        cat_path = Path(args.catalogue)
        if not cat_path.exists():
            print(f"ERROR: catalogue not found: {cat_path}", file=sys.stderr)
            sys.exit(1)
        cat_text = cat_path.read_text(encoding="utf-8")
        if args.catalogue_heading:
            source_context = extract_catalogue_entry(cat_text, args.catalogue_heading)
        else:
            source_context = cat_text

    _src_root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(_src_root))
    try:
        from adapters import ToolkitLLMAdapter
        import toolkit.llm_client as llm_module
        from dotenv import load_dotenv

        load_dotenv(_src_root.parent / ".env")
        llm_client = ToolkitLLMAdapter(llm_module)
        llm_config = {
            "provider": "openai",
            "models": {"commodity": "gpt-4.1-mini"},
            "api_key": os.getenv("OPENAI_API_KEY", ""),
        }
    except ImportError:
        print("ERROR: toolkit not importable.", file=sys.stderr)
        sys.exit(1)

    output_dir = Path(args.output_dir) if args.output_dir else analysis_path.parent

    async def _run() -> None:
        print(f"Re-skinning: {analysis_path.name}")
        reskinned, narrative_md = await reskin_scenario(
            analysis,
            source_context,
            llm_client,
            llm_config,
            tier="commodity",
            domain_context=domain_context,
        )
        output_dir.mkdir(parents=True, exist_ok=True)
        out_analysis = output_dir / "scenario_analysis_reskinned.json"
        out_narrative = output_dir / "narrative.md"
        out_analysis.write_text(json.dumps(reskinned, indent=2), encoding="utf-8")
        out_narrative.write_text(narrative_md, encoding="utf-8")
        print(f"Reskinned analysis: {out_analysis}")
        print(f"Narrative: {out_narrative}")
        print(f"Factions: {', '.join(reskinned['factions'])}")

    asyncio.run(_run())
