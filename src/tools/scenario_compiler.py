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

COMPILER_SYSTEM_PROMPT = """\
You are a negotiation scenario analyst. Given a scenario description, extract
the structured game-theoretic elements needed for AI agent play.

For each faction, assign point values (1-10 scale) to every possible outcome
of every issue. Points should reflect the faction's PRIVATE interests as
described or implied in the scenario. Higher points = more desirable outcome.

Rules:
- Assign asymmetric values: each faction should have one issue they value
  highly (7-10 pts for their preferred outcome) and issues they care less
  about (1-4 pts). This creates logrolling opportunities.
- BATNAs should be low enough (typically 4-8 total across all issues) that
  a reasonable deal beats no deal, but high enough that truly bad deals
  are rejected.
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
) -> dict[str, Any]:
    """Parse a scenario description into structured scoring data."""
    from toolkit.structured_llm import structured_call

    result = await structured_call(
        llm_client,
        llm_config,
        tier,
        schema=SCENARIO_ANALYSIS_SCHEMA,
        system_prompt=COMPILER_SYSTEM_PROMPT,
        user_prompt=f"Analyze the following negotiation scenario:\n\n{scenario_text}",
        max_retries=2,
    )

    if not result.success:
        raise ValueError(f"Scenario analysis failed: {result.error}")

    return result.data


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

    print(f"Analyzing scenario: {scenario_path.name}")
    analysis = await analyze_scenario(
        scenario_text, llm_client, llm_config, tier="commodity"
    )

    analysis_path = save_analysis(analysis, output_dir)
    print(f"Analysis saved: {analysis_path}")
    print(f"Factions: {', '.join(analysis['factions'])}")
    print(f"Issues: {', '.join(i['name'] for i in analysis['issues'])}")

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
