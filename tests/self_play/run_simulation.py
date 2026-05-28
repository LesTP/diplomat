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

        ledger_path = _project_root / "data" / "selfplay_cost_ledger.jsonl"
        ledger_path.parent.mkdir(parents=True, exist_ok=True)
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


async def _run(args: argparse.Namespace) -> None:
    faction_ids = [f.strip() for f in args.factions.split(",") if f.strip()]
    personas = _resolve_personas(faction_ids)
    # Single accountant shared between adapter and cost gate.
    accountant = _build_raw_accountant()
    llm_client = _build_llm_client(cost_accountant=accountant)
    cost_accountant = _build_cost_accountant(accountant=accountant)

    with tempfile.TemporaryDirectory(
        prefix="diplomat_selfplay_", ignore_cleanup_errors=True
    ) as tmp:
        tmp_dir = Path(tmp)
        env = GameEnvironment(
            faction_personas=personas,
            llm_client=llm_client,
            cost_accountant=cost_accountant,
            base_path=_project_root,
            tmp_dir=tmp_dir,
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
