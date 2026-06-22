"""Position-rotation harness for the §3.5 rank-among-factions lens.

In an asymmetric scenario, a model's rank can depend on which faction *slot* it
plays — slots differ in priority issue, BATNA, and competitive position. To make
``mean_rank(model, scenario)`` a fair cross-model comparison, rotate which model
plays which slot so every model plays every slot the same number of times.

This module only *generates* the per-game ``faction -> model`` assignments.
``tools/ablation_multi.sh runrotate`` executes them via ``runmix``, and
``tests/self_play/rank_aggregator.py`` pools the results (it already attributes
rank to model via the persisted ``faction_models`` map, regardless of slot).

CLI (one ``faction=model,...`` spec per line, for the bash harness to loop):
    python -m tests.self_play.position_rotation \
        --analysis scenarios/succession_division_v1/scenario_analysis.json \
        --models "claude-sonnet-4-6,gpt-5.4-mini,deepseek/deepseek-chat"
"""

from __future__ import annotations

import argparse
import itertools
import json
from pathlib import Path


def cyclic_rotations(
    factions: list[str], models: list[str]
) -> list[dict[str, str]]:
    """N cyclic assignments; each model plays each slot exactly once.

    The minimal balanced rotation design: for N factions/models, N games suffice
    to give every model one turn in every slot.
    """
    if len(factions) != len(models):
        raise ValueError(
            f"need one model per faction: {len(factions)} factions, "
            f"{len(models)} models"
        )
    n = len(factions)
    return [
        {factions[i]: models[(i + r) % n] for i in range(n)}
        for r in range(n)
    ]


def all_permutations(
    factions: list[str], models: list[str]
) -> list[dict[str, str]]:
    """All N! assignments; each model plays each slot (N-1)! times (full control)."""
    if len(factions) != len(models):
        raise ValueError(
            f"need one model per faction: {len(factions)} factions, "
            f"{len(models)} models"
        )
    return [dict(zip(factions, perm)) for perm in itertools.permutations(models)]


def rotations(
    factions: list[str], models: list[str], scheme: str = "cyclic"
) -> list[dict[str, str]]:
    if scheme == "cyclic":
        return cyclic_rotations(factions, models)
    if scheme in ("all", "permutations"):
        return all_permutations(factions, models)
    raise ValueError(f"unknown scheme: {scheme!r} (expected cyclic | all)")


def spec_string(assignment: dict[str, str]) -> str:
    """Render a {faction: model} assignment as 'faction=model,faction=model'."""
    return ",".join(f"{faction}={model}" for faction, model in assignment.items())


def factions_from_analysis(path: str) -> list[str]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return list(data["factions"])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--analysis", help="scenario_analysis.json to read the faction list from"
    )
    parser.add_argument(
        "--factions", help="comma-separated faction ids (overrides --analysis)"
    )
    parser.add_argument(
        "--models", required=True, help="comma-separated models, one per faction"
    )
    parser.add_argument(
        "--scheme", default="cyclic", choices=["cyclic", "all", "permutations"]
    )
    args = parser.parse_args(argv)

    if args.factions:
        factions = [f.strip() for f in args.factions.split(",") if f.strip()]
    elif args.analysis:
        factions = factions_from_analysis(args.analysis)
    else:
        parser.error("need --analysis or --factions")

    models = [m.strip() for m in args.models.split(",") if m.strip()]

    try:
        assignments = rotations(factions, models, args.scheme)
    except ValueError as exc:
        parser.error(str(exc))

    for assignment in assignments:
        print(spec_string(assignment))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
