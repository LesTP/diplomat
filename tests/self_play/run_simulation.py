"""CLI runner for multi-agent self-play simulation.

Run on the Raspberry Pi where toolkit is installed:

    python -m tests.self_play.run_simulation --rounds 4

Output is a timestamped JSON file in tests/self_play/results/.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

# Ensure src/ is importable.
_project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_project_root / "src"))

from tests.self_play.game_environment import GameEnvironment


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a Diplomat multi-agent self-play simulation."
    )
    parser.add_argument(
        "--rounds",
        type=int,
        default=4,
        help="Number of rounds to play (default: 4)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output JSON file path (default: auto-timestamped)",
    )
    parser.add_argument(
        "--factions",
        type=str,
        default="alpha,beta,gamma",
        help="Comma-separated faction IDs (default: alpha,beta,gamma)",
    )
    parser.add_argument(
        "--scenario",
        type=str,
        default=None,
        help="Path to scenario description — auto-compiles personas via LLM",
    )
    parser.add_argument(
        "--scenario-title",
        type=str,
        default="a multi-party negotiation",
        help="Title for compiled persona headers",
    )
    return parser.parse_args()


def _build_llm_client(cost_accountant=None):
    """Build a LoggingLLMClient wrapping ToolkitLLMAdapter with cost accountant."""
    try:
        from adapters import ToolkitLLMAdapter

        import toolkit.llm_client as llm_module

        from tests.self_play.game_environment import LoggingLLMClient

        adapter = ToolkitLLMAdapter(llm_module, cost_accountant=cost_accountant)
        return LoggingLLMClient(adapter)
    except ImportError:
        print(
            "ERROR: toolkit not importable. "
            "Install it with: pip install -e ../toolkit",
            file=sys.stderr,
        )
        sys.exit(1)


def _build_raw_accountant():
    """Build the toolkit CostAccountant directly (for adapter injection)."""
    try:
        from toolkit.cost_accountant import CostAccountant
        from toolkit.cost_accountant.types import CostBudget

        # Use a local path for the ledger to avoid UNC path issues on
        # network shares (the resolved project root can produce doubled
        # path segments like \\host\shared\shared\...).
        ledger_dir = Path(tempfile.gettempdir()) / "diplomat_selfplay"
        ledger_dir.mkdir(parents=True, exist_ok=True)
        ledger_path = ledger_dir / "cost_ledger.jsonl"
        default_budget = CostBudget(
            operation_name="self_play",
            operation_budget_usd=10.0,
            session_budget_usd=20.0,
            per_call_max_usd=1.0,
        )
        return CostAccountant(ledger_path=ledger_path, default_budget=default_budget)
    except ImportError:
        return None


def _build_cost_accountant(accountant=None):
    """Build a DiplomatCostGate for cost tracking."""
    try:
        from adapters import DiplomatCostGate

        if accountant is None:
            accountant = _build_raw_accountant()
        if accountant is None:
            from tests.helpers.factories import FakeCostAccountant
            return FakeCostAccountant()
        return DiplomatCostGate(accountant, per_round_budget_usd=2.0)
    except ImportError:
        from tests.helpers.factories import FakeCostAccountant
        return FakeCostAccountant()


def _resolve_personas(faction_ids: list[str]) -> dict[str, Path]:
    """Map faction IDs to persona file paths."""
    persona_dir = Path(__file__).resolve().parent / "personas"
    personas: dict[str, Path] = {}
    for fid in faction_ids:
        path = persona_dir / f"{fid}.txt"
        if not path.is_file():
            print(f"ERROR: persona file not found: {path}", file=sys.stderr)
            sys.exit(1)
        personas[fid] = path
    return personas


async def _compile_scenario(
    scenario_path_str: str,
    faction_ids: list[str],
    tmp_dir: Path,
    llm_client: Any,
    scenario_title: str,
) -> dict[str, Path]:
    """Compile a scenario file into per-faction persona files via LLM."""
    from tools.scenario_compiler import (
        analyze_scenario,
        generate_persona,
        save_analysis,
        save_persona,
    )

    scenario_path = Path(scenario_path_str)
    if not scenario_path.is_file():
        print(f"ERROR: scenario file not found: {scenario_path}", file=sys.stderr)
        sys.exit(1)

    scenario_text = scenario_path.read_text(encoding="utf-8")

    # The llm_client here is a LoggingLLMClient wrapping the adapter.
    # We need to get the inner adapter for the compiler call.
    inner = getattr(llm_client, "_inner", llm_client)
    import os
    llm_config = {
        "provider": "openai",
        "models": {"commodity": "gpt-4.1-mini"},
        "api_key": os.getenv("OPENAI_API_KEY", ""),
    }

    print(f"Compiling scenario: {scenario_path.name}")
    analysis = await analyze_scenario(scenario_text, inner, llm_config, tier="commodity")

    # Save analysis for inspection
    personas_dir = tmp_dir / "personas"
    save_analysis(analysis, personas_dir)

    # Use factions from analysis if caller didn't override
    available_factions = analysis["factions"]
    if set(faction_ids) == {"alpha", "beta", "gamma"} and set(available_factions) != {"alpha", "beta", "gamma"}:
        # Auto-use the factions from the analysis
        faction_ids = available_factions[:3]
        print(f"Using factions from scenario: {', '.join(faction_ids)}")

    personas: dict[str, Path] = {}
    for fid in faction_ids:
        if fid not in analysis["scoring"]:
            print(f"WARNING: faction '{fid}' not in analysis, skipping")
            continue
        persona_text = generate_persona(fid, analysis, scenario_title)
        path = save_persona(fid, persona_text, personas_dir)
        personas[fid] = path
        print(f"  Generated persona: {fid}")

    print(f"Logrolling: {analysis.get('logrolling', [])}")
    return personas, analysis


async def _run(args: argparse.Namespace) -> None:
    faction_ids = [f.strip() for f in args.factions.split(",") if f.strip()]
    # Single accountant shared between adapter and cost gate.
    accountant = _build_raw_accountant()
    llm_client = _build_llm_client(cost_accountant=accountant)
    cost_accountant = _build_cost_accountant(accountant=accountant)

    with tempfile.TemporaryDirectory(
        prefix="diplomat_selfplay_", ignore_cleanup_errors=True
    ) as tmp:
        tmp_dir = Path(tmp)

        # Pre-game: compile scenario into personas if --scenario provided.
        seed_message = None
        round_updates = None
        scenario_analysis = None
        if args.scenario:
            personas, scenario_analysis = await _compile_scenario(
                args.scenario, faction_ids, tmp_dir, llm_client, args.scenario_title
            )
            # Use the scenario text as the seed message.
            seed_message = Path(args.scenario).read_text(encoding="utf-8")
            # Generic round updates for compiled scenarios.
            round_updates = {
                1: "Opening positions are on the table. Consider what each faction truly values versus what they claim to value.",
                2: "Midpoint: assess whether proposals reflect genuine priorities or strategic positioning. Look for trades that create mutual value.",
                3: "Pressure is building. The cost of no deal is rising. Consider whether to escalate, concede, or propose a new framework.",
                4: "Final round. All commitments are binding. This is your last chance to secure favorable terms.",
            }
        else:
            personas = _resolve_personas(faction_ids)

        env = GameEnvironment(
            faction_personas=personas,
            llm_client=llm_client,
            cost_accountant=cost_accountant,
            base_path=_project_root,
            tmp_dir=tmp_dir,
            seed_message=seed_message,
            round_updates=round_updates,
            scenario_analysis=scenario_analysis,
        )

        await env.setup()
        results = None
        try:
            results = await env.run_game(total_rounds=args.rounds)
        finally:
            # Write results BEFORE teardown so crashes in shutdown don't lose data.
            if results is not None:
                _write_results(results, args.output)
            await env.teardown()


def _write_results(results: dict, output_path: str | None) -> None:
    if output_path is None:
        results_dir = Path(__file__).resolve().parent / "results"
        results_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        output_path = str(results_dir / f"run_{ts}.json")

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_text(
        json.dumps(results, indent=2, sort_keys=True, default=str),
        encoding="utf-8",
    )
    print(f"\nResults written to: {output_path}")


def main() -> None:
    args = _parse_args()
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()
