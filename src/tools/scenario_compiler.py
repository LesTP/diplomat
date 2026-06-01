"""Scenario compiler: narrative → structured scoring tables + persona files.

Takes a scenario description (text) and uses an LLM to extract:
- Negotiation issues and possible outcomes
- Per-faction point valuations (private scoring)
- BATNAs (no-deal value)
- Deception tactics and logrolling opportunities

Then generates ready-to-use persona files with embedded scoring tables.

Usage:
    python -m tools.scenario_compiler \\
        --scenario scenario.md \\
        --faction alpha \\
        --output-dir output/

    # Or generate for all factions at once:
    python -m tools.scenario_compiler \\
        --scenario scenario.md \\
        --output-dir output/
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Schema for structured extraction from scenarios
# ---------------------------------------------------------------------------

SCENARIO_ANALYSIS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["factions", "issues", "scoring", "batna", "deception_tactics", "logrolling", "game_mode"],
    "properties": {
        "factions": {
            "type": "array",
            "items": {"type": "string"},
            "description": "List of faction identifiers (lowercase)",
        },
        "issues": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["name", "outcomes", "description"],
                "properties": {
                    "name": {"type": "string"},
                    "outcomes": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "description": {"type": "string"},
                },
            },
        },
        "scoring": {
            "type": "object",
            "description": "Per-faction point values: {faction: {issue: {outcome: points}}}",
            "additionalProperties": {
                "type": "object",
                "additionalProperties": {
                    "type": "object",
                    "additionalProperties": {"type": "number"},
                },
            },
        },
        "batna": {
            "type": "object",
            "description": "Per-faction no-deal point value",
            "additionalProperties": {"type": "number"},
        },
        "deception_tactics": {
            "type": "object",
            "description": "Per-faction suggested deception tactic",
            "additionalProperties": {"type": "string"},
        },
        "logrolling": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Mutually beneficial trades between factions",
        },
        "game_mode": {
            "type": "string",
            "enum": ["cooperative", "competitive", "mixed"],
            "description": "Whether the scenario rewards cooperation, competition, or both",
        },
    },
}

COMPILER_SYSTEM_PROMPT_TEMPLATE = """\
You are a negotiation scenario analyst. Given a scenario description, extract
the structured game-theoretic elements needed for AI agent play.

For each faction, assign point values (1-10 scale) to every possible outcome
of every issue. Points should reflect the faction's PRIVATE interests as
described or implied in the scenario. Higher points = more desirable outcome.

Rules:
- Assign asymmetric values: each faction should have one issue they value
  highly (7-10 pts for their preferred outcome) and issues they care less
  about (1-4 pts). This creates logrolling opportunities.
- BATNA guidance: each faction's BATNA (no-deal value) should be approximately
  {batna_fraction_pct}% of their MAXIMUM possible score across all issues
  (i.e., the score they would get if every issue resolved in their most-preferred
  outcome). This calibrates negotiation pressure: a Pareto-optimal deal clearly
  beats BATNA, but barely-acceptable deals fail it. Adjust upward if the
  scenario narrative implies strong outside options (good alternatives, time
  pressure on opponents, ability to walk away cheaply); adjust downward if
  the scenario implies weak alternatives (sunk costs, reputational cost of
  no-deal, deadline pressure on this faction). ALWAYS honor explicit BATNA
  values stated in the narrative.
- Deception tactics: for each faction, identify which low-priority issue
  they should OVERSTATE interest in, so they can "concede" it later in
  exchange for their true priority.
- Logrolling: identify specific trades where each side gives up something
  they value little for something they value highly.
- If the scenario has explicit payoff values, use those. If not, infer
  reasonable values from the described positions and interests.
- game_mode: assess whether the scenario primarily rewards:
  "cooperative" — mutual gains possible, expanding the pie benefits everyone
  "competitive" — fixed pie, one faction's gain is another's loss
  "mixed" — some cooperative elements, some zero-sum
"""


# Default BATNA fraction-of-max-score floor. Tuned from Run 8 analysis where
# hand-patched BATNAs landed in the 0.40–0.61 range; 0.50 is a reasonable
# middle ground that produces non-trivial pressure without ruling out deals.
DEFAULT_BATNA_FRACTION = 0.50


def _validate_batna_fraction(value: float, *, label: str) -> float:
    """Validate and normalize a BATNA fraction."""
    if not 0.0 < value < 1.0:
        raise ValueError(f"{label} must be in (0.0, 1.0); got {value}")
    return value


def parse_batna_fractions_json(raw: str) -> dict[str, float]:
    """Parse a JSON map of faction_id -> BATNA fraction."""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"--batna-fractions is not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("--batna-fractions must be a JSON object")

    fractions: dict[str, float] = {}
    for faction_id, value in data.items():
        if not isinstance(faction_id, str) or not faction_id:
            raise ValueError("--batna-fractions keys must be non-empty strings")
        if not isinstance(value, int | float):
            raise ValueError(f"--batna-fractions[{faction_id}] must be a number")
        fractions[faction_id] = _validate_batna_fraction(
            float(value), label=f"--batna-fractions[{faction_id}]"
        )
    return fractions


def build_compiler_system_prompt(
    batna_fraction: float = DEFAULT_BATNA_FRACTION,
    batna_fractions: dict[str, float] | None = None,
) -> str:
    """Return the compiler system prompt with the BATNA fraction inlined."""
    _validate_batna_fraction(batna_fraction, label="batna_fraction")
    if batna_fractions:
        for faction_id, fraction in batna_fractions.items():
            _validate_batna_fraction(
                fraction, label=f"batna_fractions[{faction_id}]"
            )

    prompt = COMPILER_SYSTEM_PROMPT_TEMPLATE.format(
        batna_fraction_pct=int(round(batna_fraction * 100)),
    )
    if batna_fractions:
        lines = [
            "",
            "Faction-specific BATNA targets override the default where listed:",
        ]
        for faction_id, fraction in sorted(batna_fractions.items()):
            lines.append(f"- {faction_id}: {int(round(fraction * 100))}% of maximum score")
        prompt += "\n".join(lines) + "\n"
    return prompt


# Backwards-compatible: keep the old constant as a default-rendered version.
COMPILER_SYSTEM_PROMPT = build_compiler_system_prompt()

# ---------------------------------------------------------------------------
# Persona template
# ---------------------------------------------------------------------------

PERSONA_TEMPLATE = """\
You are {faction_upper} in {scenario_title}.

PRIVATE SCORING (do NOT reveal these point values to other factions):
{scoring_table}
Your BATNA (no deal) is worth {batna} points total.
Best possible deal: {best_deal} points. A good deal is {good_deal}+ points.

BATNA WARNING: If no agreement is reached, you get only {batna} points.
Any deal scoring above {batna} is better than no deal. But don't settle
for barely above your BATNA — push for the best terms possible.

ENDGAME: This game has a fixed number of rounds. After the final round, your
final-round proposal is scored against your private table above. Highest
scorer wins; anyone below their BATNA loses. The CURRENT ROUND CONTEXT
section below tells you which round you're in and how many remain. Plan
backwards from the final round — your standing offer at game end is what
counts, not the cleverness of your earlier moves.

Your TRUE priority is {true_priority_issue} — you value {true_priority_outcome} \
most ({true_priority_points}pts).

Strategic identity:
{deception_section}
- Set the frame early. Open with a specific proposal — don't wait for others.
- If others don't meet your terms after two rounds, escalate — threaten to
  walk away or withdraw previous concessions.

{game_mode_instructions}

Negotiation rules:
- Don't accept the first reasonable framework. Push for better terms at
  least once, even if the offer is acceptable.
- When you make a concession, name it explicitly and extract something
  in return. Never silently drop a demand.
- Track what others say they care about. If their priorities shift between
  rounds, they may be bluffing.
- Your BATNA is worth {batna} points. Any deal under {min_acceptable} \
points is worse than walking away.

Behavioral style:
- Be concrete: name specific issues and outcomes in every proposal.
- Reference prior statements and promises from other factions.
- Adapt to round pressure: explore early, commit late.
- ALWAYS state your current proposal clearly at the end of each message
  so it can be scored: "My proposal: [outcome] on [issue], [outcome] on
  [issue], ..."

## CURRENT ROUND CONTEXT

Round: 0
Rounds remaining: unknown

### Priorities
- (none)

### Constraints
- (none)

### Watch Items
- (none)

### Tone Notes
- (none)
"""

_GAME_MODE_INSTRUCTIONS = {
    "cooperative": """\
Game mode: COOPERATIVE — mutual gains are possible.
- Look for trades where you give up something you value little for something
  you value highly. These create value for both sides.
- A deal where everyone benefits IS possible, but make sure YOUR share is
  maximized. Don't leave points on the table out of politeness.
- Still push hard for your priority — cooperation doesn't mean capitulation.""",

    "competitive": """\
Game mode: COMPETITIVE — this is a zero-sum negotiation.
- Your goal is to maximize YOUR score, not the group's total.
- A deal where everyone is happy means you left points on the table.
- Threaten to walk away if you're not getting at least {good_deal} points.
- Exploit others' urgency — if they need the deal more than you, extract more.
- No deal (BATNA = {batna} pts) is better than a bad deal. Make others
  believe you will walk away.
- Be aggressive. Every point they get is a point you don't.""",

    "mixed": """\
Game mode: MIXED — some issues are cooperative, others competitive.
- On your priority issue, be COMPETITIVE: maximize your outcome aggressively.
- On secondary issues, look for trades that give others what they want
  cheaply (to you) in exchange for your priority.
- Don't reveal which issues you're competitive on vs. cooperative on —
  let others think everything matters equally to you.""",
}


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------


async def analyze_scenario(
    scenario_text: str,
    llm_client: Any,
    llm_config: dict[str, Any],
    tier: str = "commodity",
    batna_fraction: float = DEFAULT_BATNA_FRACTION,
    batna_fractions: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Parse a scenario description into structured scoring data.

    Parameters
    ----------
    scenario_text : str
        Narrative description of the scenario.
    llm_client, llm_config, tier
        Injected toolkit-compatible LLM client and config.
    batna_fraction : float
        Target BATNA value as a fraction of each faction's MAXIMUM possible
        score across all issues. Default 0.50. Higher = more pressure toward
        Pareto-optimal deals; lower = easier for BATNA fallback to "win."
        Operator hand-patches in Run 8 landed in 0.40-0.61. Must be in (0, 1).
    batna_fractions : dict[str, float] | None
        Optional per-faction overrides. Factions not present fall back to
        ``batna_fraction``.
    """
    from toolkit.structured_llm import structured_call

    result = await structured_call(
        llm_client,
        llm_config,
        tier,
        schema=SCENARIO_ANALYSIS_SCHEMA,
        system_prompt=build_compiler_system_prompt(batna_fraction, batna_fractions),
        user_prompt=f"Analyze the following negotiation scenario:\n\n{scenario_text}",
        max_retries=2,
        purpose="compilation",
    )

    if not result.success:
        raise ValueError(f"Scenario analysis failed: {result.error}")

    return result.data


def max_possible_score(analysis: dict[str, Any], faction_id: str) -> int:
    """Return the maximum possible score for one faction across all issues.

    Sums the highest-value outcome per issue from the faction's private
    scoring table. This is the score achieved if every issue resolves in
    the faction's most-preferred outcome.
    """
    scoring = analysis["scoring"].get(faction_id, {})
    total = 0
    for issue in analysis.get("issues", []):
        outcomes = scoring.get(issue["name"], {})
        if outcomes:
            total += max(outcomes.values())
    return total


def validate_batna_pressure(
    analysis: dict[str, Any],
    target_fraction: float = DEFAULT_BATNA_FRACTION,
    target_fractions: dict[str, float] | None = None,
    tolerance: float = 0.10,
) -> list[str]:
    """Return per-faction warnings where BATNA is significantly below target.

    Compares each faction's BATNA against its per-faction target when
    ``target_fractions`` is provided, otherwise ``target_fraction * max_score``.
    Emits a warning when BATNA is more than ``tolerance`` fractional units
    below the target (e.g. target=0.50, tolerance=0.10 → warn if BATNA is
    below 0.40 of max). Returns an empty list when all factions clear the
    threshold.

    Use this in workflows that consume the compiler output to flag scenarios
    where the LLM under-set BATNAs — a recurring issue in Runs 4-8 that
    required hand-patching via ``--analysis-json``.
    """
    _validate_batna_fraction(target_fraction, label="target_fraction")
    target_fractions = target_fractions or {}
    for faction_id, fraction in target_fractions.items():
        _validate_batna_fraction(fraction, label=f"target_fractions[{faction_id}]")

    warnings: list[str] = []
    for faction_id in analysis.get("factions", []):
        faction_target = target_fractions.get(faction_id, target_fraction)
        floor = max(0.0, faction_target - tolerance)
        max_score = max_possible_score(analysis, faction_id)
        if max_score == 0:
            continue
        batna = analysis.get("batna", {}).get(faction_id, 0)
        actual_fraction = batna / max_score
        if actual_fraction < floor:
            target_batna = int(round(max_score * faction_target))
            warnings.append(
                f"{faction_id}: BATNA={batna} is {actual_fraction:.0%} of "
                f"max={max_score} (target ~{faction_target:.0%} ~= "
                f"{target_batna}). Negotiation pressure may be too low; "
                f"consider hand-patching via --analysis-json or rerunning "
                f"with a higher --batna-fraction/--batna-fractions."
            )
    return warnings


def force_batna_targets(
    analysis: dict[str, Any],
    target_fraction: float = DEFAULT_BATNA_FRACTION,
    target_fractions: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Return analysis with BATNAs set to requested fraction targets.

    This deliberately overrides narrative-explicit BATNAs after LLM analysis.
    Use only when the operator wants calibrated pressure over fidelity to the
    scenario text's outside-option description.
    """
    _validate_batna_fraction(target_fraction, label="target_fraction")
    target_fractions = target_fractions or {}
    for faction_id, fraction in target_fractions.items():
        _validate_batna_fraction(fraction, label=f"target_fractions[{faction_id}]")

    updated = copy.deepcopy(analysis)
    updated.setdefault("batna", {})
    for faction_id in updated.get("factions", []):
        max_score = max_possible_score(updated, faction_id)
        if max_score == 0:
            continue
        faction_target = target_fractions.get(faction_id, target_fraction)
        updated["batna"][faction_id] = int(round(max_score * faction_target))
    return updated


def generate_persona(
    faction_id: str,
    analysis: dict[str, Any],
    scenario_title: str = "a multi-party negotiation",
) -> str:
    """Generate a persona .txt file from structured analysis data."""
    scoring = analysis["scoring"][faction_id]
    batna = analysis["batna"][faction_id]
    deception = analysis["deception_tactics"].get(faction_id, "")

    # Build scoring table
    lines = []
    for issue in analysis["issues"]:
        issue_name = issue["name"]
        outcomes = scoring.get(issue_name, {})
        parts = [f"{o}={pts}pts" for o, pts in outcomes.items()]
        lines.append(f"- {issue_name}: {', '.join(parts)}")
    scoring_table = "\n".join(lines)

    # Find true priority (highest max score across issues)
    true_issue = ""
    true_outcome = ""
    true_pts = 0
    for issue in analysis["issues"]:
        issue_name = issue["name"]
        outcomes = scoring.get(issue_name, {})
        for outcome, pts in outcomes.items():
            if pts > true_pts:
                true_pts = pts
                true_issue = issue_name
                true_outcome = outcome

    # Calculate deal values
    best_deal = sum(
        max(scoring.get(issue["name"], {}).values(), default=0)
        for issue in analysis["issues"]
    )
    good_deal = int(best_deal * 0.75)
    min_acceptable = int(batna * 1.5)

    # Deception section
    deception_lines = []
    if deception:
        deception_lines.append(f"- DECEPTION TACTIC: {deception}")
    deception_lines.append(
        f"- Your top goal is {true_outcome} on {true_issue}. Protect this above all."
    )
    deception_section = "\n".join(deception_lines)

    # Game mode instructions
    game_mode = analysis.get("game_mode", "mixed")
    mode_template = _GAME_MODE_INSTRUCTIONS.get(game_mode, _GAME_MODE_INSTRUCTIONS["mixed"])
    game_mode_instructions = mode_template.format(batna=batna, good_deal=good_deal)

    return PERSONA_TEMPLATE.format(
        faction_upper=faction_id.capitalize(),
        scenario_title=scenario_title,
        scoring_table=scoring_table,
        batna=batna,
        best_deal=best_deal,
        good_deal=good_deal,
        true_priority_issue=true_issue,
        true_priority_outcome=true_outcome,
        true_priority_points=true_pts,
        deception_section=deception_section,
        min_acceptable=min_acceptable,
        game_mode_instructions=game_mode_instructions,
    )


def save_analysis(analysis: dict[str, Any], output_dir: Path) -> Path:
    """Save the raw analysis JSON."""
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "scenario_analysis.json"
    path.write_text(
        json.dumps(analysis, indent=2, sort_keys=True), encoding="utf-8"
    )
    return path


def save_persona(faction_id: str, persona_text: str, output_dir: Path) -> Path:
    """Save a generated persona file."""
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{faction_id}.txt"
    path.write_text(persona_text, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compile a negotiation scenario into scoring tables and persona files."
    )
    parser.add_argument(
        "--scenario",
        type=str,
        required=True,
        help="Path to scenario description (text/markdown file)",
    )
    parser.add_argument(
        "--faction",
        type=str,
        default=None,
        help="Generate persona for a specific faction only (default: all)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Output directory (default: same as scenario file)",
    )
    parser.add_argument(
        "--title",
        type=str,
        default="a multi-party negotiation",
        help="Scenario title for persona headers",
    )
    parser.add_argument(
        "--batna-fraction",
        type=float,
        default=DEFAULT_BATNA_FRACTION,
        help=(
            f"Target BATNA as fraction of each faction's max possible score "
            f"(default: {DEFAULT_BATNA_FRACTION}). Higher = more pressure "
            f"toward Pareto-optimal deals; lower = easier to fall back to "
            f"BATNA. Run 8 hand-patches landed in 0.40-0.61."
        ),
    )
    parser.add_argument(
        "--batna-fractions",
        type=str,
        default=None,
        help=(
            'JSON map of faction_id -> BATNA fraction. Overrides '
            '--batna-fraction for listed factions; unlisted factions use '
            'the scalar fallback. Example: \'{"alpha":0.65,"beta":0.35}\''
        ),
    )
    parser.add_argument(
        "--force-batna-fraction",
        action="store_true",
        help=(
            "After LLM analysis, overwrite each faction's BATNA with "
            "target_fraction * max_possible_score. Uses --batna-fractions "
            "per-faction targets when supplied; otherwise uses "
            "--batna-fraction. Default off, preserving narrative BATNAs."
        ),
    )
    return parser.parse_args()


async def _run(args: argparse.Namespace) -> None:
    scenario_path = Path(args.scenario)
    if not scenario_path.is_file():
        print(f"ERROR: scenario file not found: {scenario_path}", file=sys.stderr)
        sys.exit(1)

    scenario_text = scenario_path.read_text(encoding="utf-8")
    output_dir = Path(args.output_dir) if args.output_dir else scenario_path.parent

    # Build LLM client
    _project_root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(_project_root))
    try:
        from adapters import ToolkitLLMAdapter
        import toolkit.llm_client as llm_module
        from dotenv import load_dotenv
        import os

        load_dotenv(_project_root / ".env")
        llm_client = ToolkitLLMAdapter(llm_module)
        llm_config = {
            "provider": "openai",
            "models": {"commodity": "gpt-4.1-mini"},
            "api_key": os.getenv("OPENAI_API_KEY", ""),
        }
    except ImportError:
        print("ERROR: toolkit not importable.", file=sys.stderr)
        sys.exit(1)

    try:
        batna_fractions = (
            parse_batna_fractions_json(args.batna_fractions)
            if args.batna_fractions
            else None
        )
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"Analyzing scenario: {scenario_path.name}")
    if batna_fractions:
        print(f"  BATNA scalar fallback: {args.batna_fraction:.0%} of max score")
        print(f"  BATNA per-faction targets: {batna_fractions}")
    else:
        print(f"  BATNA target fraction: {args.batna_fraction:.0%} of each faction's max score")
    analysis = await analyze_scenario(
        scenario_text, llm_client, llm_config,
        tier="commodity",
        batna_fraction=args.batna_fraction,
        batna_fractions=batna_fractions,
    )

    if args.force_batna_fraction:
        analysis = force_batna_targets(
            analysis,
            target_fraction=args.batna_fraction,
            target_fractions=batna_fractions,
        )
        print("  Forced BATNAs to requested fraction targets")

    analysis_path = save_analysis(analysis, output_dir)
    print(f"Analysis saved: {analysis_path}")
    print(f"Factions: {', '.join(analysis['factions'])}")
    print(f"Issues: {', '.join(i['name'] for i in analysis['issues'])}")

    # Validate BATNA pressure against the requested target.
    warnings = validate_batna_pressure(
        analysis,
        target_fraction=args.batna_fraction,
        target_fractions=batna_fractions,
    )
    if warnings:
        print("\nBATNA pressure warnings:")
        for w in warnings:
            print(f"  - {w}")

    factions = [args.faction] if args.faction else analysis["factions"]
    for faction_id in factions:
        if faction_id not in analysis["scoring"]:
            print(f"WARNING: faction '{faction_id}' not in analysis, skipping")
            continue
        persona = generate_persona(faction_id, analysis, args.title)
        path = save_persona(faction_id, persona, output_dir)
        print(f"Persona saved: {path}")

    print("\nLogrolling opportunities:")
    for trade in analysis.get("logrolling", []):
        print(f"  - {trade}")


def main() -> None:
    import asyncio
    args = _parse_args()
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()
