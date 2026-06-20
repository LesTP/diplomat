"""CLI runner for multi-agent self-play simulation.

Run on the Raspberry Pi where toolkit is installed:

    python -m tests.self_play.run_simulation --rounds 4

Output is a timestamped JSON file in tests/self_play/results/.
"""

from __future__ import annotations

import argparse
import asyncio
import copy
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

# Load .env so API keys for all providers (Anthropic, Google, etc.) are
# available to subprocess libraries that read from os.environ at call time.
# Without this, only env vars already in the parent shell would work — which
# typically only covers OPENAI_API_KEY on dev machines.
try:
    from dotenv import load_dotenv
    _env_path = Path(__file__).resolve().parent.parent.parent / ".env"
    if _env_path.is_file():
        load_dotenv(_env_path)
except ImportError:
    pass

# Ensure src/ is importable.
_project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_project_root / "src"))

from tests.self_play.game_environment import GameEnvironment


_GAME_MODE_CHOICES = ("cooperative", "competitive", "mixed")


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
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Replace the real LLM client with DryRunLLMClient (zero cost). "
            "All calls return canned schema-valid JSON. Use this to verify "
            "self-play infrastructure (round counter, message delivery, "
            "extraction/reconciliation call counts) before spending real money."
        ),
    )
    parser.add_argument(
        "--per-faction-providers",
        type=str,
        default=None,
        help=(
            'JSON map of faction_id -> {"provider":"...","model":"..."} '
            'that overrides the Generator provider/model for that faction. '
            'Only the Generator is affected; all other modules stay on the '
            'shared (primary/secondary) providers. '
            'Example: \'{"alpha":{"provider":"openai","model":"gpt-4.1-mini"},'
            '"beta":{"provider":"anthropic","model":"claude-haiku-4-5"},'
            '"gamma":{"provider":"google","model":"gemini-2.5-flash-lite"}}\''
        ),
    )
    parser.add_argument(
        "--analysis-json",
        type=str,
        default=None,
        help=(
            "Path to a pre-compiled scenario_analysis.json. When provided, "
            "skips the live LLM compile step and uses this analysis to "
            "generate personas and seed post-game scoring. Requires --scenario "
            "to also be provided (for the seed message text)."
        ),
    )
    parser.add_argument(
        "--batna-fraction",
        type=float,
        default=None,
        help=(
            "Target BATNA as fraction of each faction's max possible score "
            "during scenario compilation (default: tools/scenario_compiler "
            "DEFAULT_BATNA_FRACTION = 0.50). Higher = more pressure toward "
            "Pareto-optimal deals; lower = easier to fall back to BATNA. "
            "Ignored when --analysis-json is used."
        ),
    )
    parser.add_argument(
        "--batna-fractions",
        type=str,
        default=None,
        help=(
            'JSON map of faction_id -> BATNA fraction for scenario compilation. '
            'Overrides --batna-fraction for listed factions; unlisted factions '
            'use the scalar fallback. Ignored when --analysis-json is used. '
            'Example: \'{"alpha":0.65,"beta":0.35,"gamma":0.50}\''
        ),
    )
    parser.add_argument(
        "--game-mode",
        choices=_GAME_MODE_CHOICES,
        default=None,
        help=(
            "Runtime override for compiled scenario game_mode. Applies to "
            "temporary personas generated for this run without changing the "
            "source scenario_analysis.json."
        ),
    )
    parser.add_argument(
        "--bare-prompt",
        action="store_true",
        help=(
            "Enable bare-prompt ablation mode. Disables Extraction, Analyst, "
            "Divergence, Reconciliation, Adversarial, and Coaching modules. "
            "Each agent responds using only its persona prompt and the raw "
            "message transcript. Enables ablation comparison against full mode. "
            "Results JSON will include bare_mode=true in metadata."
        ),
    )
    return parser.parse_args()


def _apply_game_mode_override(
    analysis: dict[str, Any],
    game_mode: str | None,
) -> dict[str, Any]:
    """Return scenario analysis with an optional runtime game_mode override."""
    if game_mode is None:
        return analysis
    if game_mode not in _GAME_MODE_CHOICES:
        raise ValueError(
            f"game_mode must be one of {', '.join(_GAME_MODE_CHOICES)}; got {game_mode}"
        )
    updated = copy.deepcopy(analysis)
    updated["game_mode"] = game_mode
    return updated


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
    batna_fraction: float | None = None,
    batna_fractions: dict[str, float] | None = None,
    game_mode_override: str | None = None,
) -> dict[str, Path]:
    """Compile a scenario file into per-faction persona files via LLM."""
    from scenario_authoring.scenario_compiler import (
        DEFAULT_BATNA_FRACTION,
        analyze_scenario,
        generate_persona,
        save_analysis,
        save_persona,
        validate_batna_pressure,
    )

    scenario_path = Path(scenario_path_str)
    if not scenario_path.is_file():
        print(f"ERROR: scenario file not found: {scenario_path}", file=sys.stderr)
        sys.exit(1)

    scenario_text = scenario_path.read_text(encoding="utf-8")

    from modules.reconciliation import subsystem_llm_config
    _compile_primary = {
        "provider": "openai",
        "models": {"commodity": "gpt-4.1-mini"},
        "api_key_env": "OPENAI_API_KEY",
    }
    llm_config = subsystem_llm_config(_compile_primary)

    effective_fraction = (
        batna_fraction if batna_fraction is not None else DEFAULT_BATNA_FRACTION
    )

    print(f"Compiling scenario: {scenario_path.name}")
    if batna_fractions:
        print(f"  BATNA scalar fallback: {effective_fraction:.0%} of max score")
        print(f"  BATNA per-faction targets: {batna_fractions}")
    else:
        print(f"  BATNA target fraction: {effective_fraction:.0%} of each faction's max score")
    analysis = await analyze_scenario(
        scenario_text, llm_client, llm_config,
        tier="commodity",
        batna_fraction=effective_fraction,
        batna_fractions=batna_fractions,
    )
    analysis = _apply_game_mode_override(analysis, game_mode_override)
    if game_mode_override:
        print(f"  Game mode override: {game_mode_override}")

    # Save analysis for inspection
    personas_dir = tmp_dir / "personas"
    save_analysis(analysis, personas_dir)

    # Warn if BATNAs landed below the target floor. Common enough across
    # Runs 4-8 to deserve an inline diagnostic; operator can hand-patch
    # via --analysis-json or rerun with a higher --batna-fraction.
    warnings = validate_batna_pressure(
        analysis,
        target_fraction=effective_fraction,
        target_fractions=batna_fractions,
    )
    if warnings:
        print("\nBATNA pressure warnings:")
        for w in warnings:
            print(f"  - {w}")

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


def _load_precompiled_analysis(
    analysis_path_str: str,
    faction_ids: list[str],
    tmp_dir: Path,
    scenario_title: str,
    game_mode_override: str | None = None,
) -> tuple[dict[str, Path], dict[str, Any]]:
    """Load a pre-compiled scenario_analysis.json and regenerate personas from it.

    Used to preserve hand-tuned BATNAs or any other manual edits to the
    analysis JSON between compile and live run. No LLM call.
    """
    from scenario_authoring.scenario_compiler import generate_persona, save_persona

    analysis_path = Path(analysis_path_str)
    if not analysis_path.is_file():
        print(f"ERROR: analysis JSON not found: {analysis_path}", file=sys.stderr)
        sys.exit(1)

    analysis = json.loads(analysis_path.read_text(encoding="utf-8"))
    analysis = _apply_game_mode_override(analysis, game_mode_override)
    available_factions = analysis["factions"]
    print(f"Loaded pre-compiled analysis from {analysis_path.name}")
    print(f"  Factions in analysis: {', '.join(available_factions)}")
    if game_mode_override:
        print(f"  Game mode override: {game_mode_override}")
    print(f"  BATNAs: {analysis['batna']}")

    # Auto-use the factions from the analysis if caller didn't override.
    if set(faction_ids) == {"alpha", "beta", "gamma"} and set(available_factions) != {"alpha", "beta", "gamma"}:
        faction_ids = available_factions[:3]
        print(f"  Using factions from analysis: {', '.join(faction_ids)}")

    personas_dir = tmp_dir / "personas"
    personas: dict[str, Path] = {}
    for fid in faction_ids:
        if fid not in analysis["scoring"]:
            print(f"WARNING: faction '{fid}' not in analysis, skipping")
            continue
        persona_text = generate_persona(fid, analysis, scenario_title)
        path = save_persona(fid, persona_text, personas_dir)
        personas[fid] = path
        print(f"  Regenerated persona: {fid}")

    print(f"  Logrolling: {analysis.get('logrolling', [])}")
    return personas, analysis


async def _run(args: argparse.Namespace) -> None:
    faction_ids = [f.strip() for f in args.factions.split(",") if f.strip()]

    from scenario_authoring.scenario_compiler import parse_batna_fractions_json

    # Parse --batna-fractions JSON early so bad inputs fail before any LLM cost.
    try:
        batna_fractions = (
            parse_batna_fractions_json(args.batna_fractions)
            if args.batna_fractions
            else None
        )
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    # Parse --per-faction-providers JSON early so we fail before any LLM cost.
    per_faction_providers: dict[str, dict[str, str]] | None = None
    if args.per_faction_providers:
        try:
            per_faction_providers = json.loads(args.per_faction_providers)
        except json.JSONDecodeError as exc:
            print(f"ERROR: --per-faction-providers is not valid JSON: {exc}", file=sys.stderr)
            sys.exit(1)
        if not isinstance(per_faction_providers, dict):
            print("ERROR: --per-faction-providers must be a JSON object", file=sys.stderr)
            sys.exit(1)
        for fid, cfg in per_faction_providers.items():
            if not isinstance(cfg, dict):
                print(f"ERROR: per-faction-providers[{fid}] must be an object", file=sys.stderr)
                sys.exit(1)
            if "provider" not in cfg or "model" not in cfg:
                print(
                    f"ERROR: per-faction-providers[{fid}] missing 'provider' or 'model'",
                    file=sys.stderr,
                )
                sys.exit(1)
        # Warn about factions in the map that don't match the simulation's faction list.
        # We don't fail because scenario-driven runs auto-rename factions in _compile_scenario.
        unknown = set(per_faction_providers.keys()) - set(faction_ids)
        if unknown and not args.scenario:
            print(
                f"WARNING: per-faction-providers has factions not in --factions: {sorted(unknown)}",
                file=sys.stderr,
            )

    if args.dry_run:
        # Zero-cost path: wrap a DryRunLLMClient with the same LoggingLLMClient
        # so the existing llm_call_log machinery still records every call.
        from tests.self_play.fake_llm_client import DryRunLLMClient
        from tests.self_play.game_environment import LoggingLLMClient
        from tests.helpers.factories import FakeCostAccountant

        print("=" * 60)
        print("  DRY RUN MODE — no real LLM calls, no cost")
        print("=" * 60)
        accountant = None
        llm_client = LoggingLLMClient(DryRunLLMClient())
        cost_accountant = FakeCostAccountant()
    else:
        # Single accountant shared between adapter and cost gate.
        accountant = _build_raw_accountant()
        llm_client = _build_llm_client(cost_accountant=accountant)
        cost_accountant = _build_cost_accountant(accountant=accountant)

    with tempfile.TemporaryDirectory(
        prefix="diplomat_selfplay_", ignore_cleanup_errors=True
    ) as tmp:
        tmp_dir = Path(tmp)

        # Pre-game: compile scenario into personas if --scenario provided,
        # OR load pre-compiled analysis JSON if --analysis-json provided.
        seed_message = None
        round_updates = None
        scenario_analysis = None
        if args.analysis_json:
            if not args.scenario:
                print(
                    "ERROR: --analysis-json requires --scenario (for the seed message text)",
                    file=sys.stderr,
                )
                sys.exit(1)
            personas, scenario_analysis = _load_precompiled_analysis(
                args.analysis_json,
                faction_ids,
                tmp_dir,
                args.scenario_title,
                game_mode_override=args.game_mode,
            )
            seed_message = Path(args.scenario).read_text(encoding="utf-8")
            round_updates = {
                1: "Opening positions are on the table. Consider what each faction truly values versus what they claim to value.",
                2: "Midpoint: assess whether proposals reflect genuine priorities or strategic positioning. Look for trades that create mutual value.",
                3: "Pressure is building. The cost of no deal is rising. Consider whether to escalate, concede, or propose a new framework.",
                4: "Final round. All commitments are binding. This is your last chance to secure favorable terms.",
            }
        elif args.scenario:
            personas, scenario_analysis = await _compile_scenario(
                args.scenario, faction_ids, tmp_dir, llm_client, args.scenario_title,
                batna_fraction=args.batna_fraction,
                batna_fractions=batna_fractions,
                game_mode_override=args.game_mode,
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

        if args.bare_prompt:
            print("=" * 60)
            print("  BARE-PROMPT MODE — Extraction/Analyst/Adversarial/Coaching disabled")
            print("=" * 60)

        env = GameEnvironment(
            faction_personas=personas,
            llm_client=llm_client,
            cost_accountant=cost_accountant,
            base_path=_project_root,
            tmp_dir=tmp_dir,
            seed_message=seed_message,
            round_updates=round_updates,
            scenario_analysis=scenario_analysis,
            per_faction_providers=per_faction_providers,
            bare_mode=args.bare_prompt,
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
    from tests.self_play.analysis import compute_process_signatures

    results["process_signatures"] = compute_process_signatures(results)

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
