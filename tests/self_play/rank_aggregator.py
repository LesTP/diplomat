"""Cross-game mean_rank aggregator (§3.5 rank-among-factions, cross-game half).

Reads self-play result JSON files — each carrying per-game
``scores.faction_ranks`` (from ``game_environment._rank_among_factions``) and
``faction_models`` (from ``game_environment._resolve_faction_models``) — and
computes:

    mean_rank(model, scenario) = average within-game rank a model achieved,
                                 pooled over every faction slot it played
                                 across all matching games.

Lower is better (1 = won the game). Because the model is read from the
per-faction ``faction_models`` map (not the filename), this works for both
homogeneous tier runs and heterogeneous mixed-model games.

No-deal games (``scores.deal_reached`` is False -> every faction at BATNA, so
ranks are degenerate) are excluded by default; pass ``--include-no-deal`` to
keep them.

CLI:
    python -m tests.self_play.rank_aggregator \
        --results "tests/self_play/results/run17_*.json"
"""

from __future__ import annotations

import argparse
import glob
import json
import re
import statistics
from pathlib import Path
from typing import Any

# run17_<mode>_<modeltag>_<scenario>_<n>.json  (modeltag is dot/dash-stripped)
_RESULT_NAME_RE = re.compile(r"run17_(full|bare)_(.+?)_([a-z0-9]+)_(\d+)")


def model_label(entry: dict[str, str] | None) -> str:
    """Render a faction_models entry as a stable 'provider/model' key."""
    if not entry:
        return "unknown"
    return f"{entry.get('provider', '?')}/{entry.get('model', '?')}"


def scenario_key(result: dict[str, Any], filename: str | None = None) -> str:
    """Scenario identity: the run17 filename's scenario field if parseable,
    else a signature derived from the analysis's issue names."""
    if filename:
        match = _RESULT_NAME_RE.search(Path(filename).name)
        if match:
            return match.group(3)
    issues = result.get("scenario_analysis", {}).get("issues", [])
    names = sorted(issue.get("name", "?") for issue in issues)
    return "+".join(names) if names else "unknown"


def extract_samples(
    result: dict[str, Any], filename: str | None = None
) -> list[tuple[str, str, int]]:
    """One ``(scenario, model_label, rank)`` sample per faction in the result.

    Returns [] for results that predate the rank lens (no ``faction_ranks``).
    """
    faction_ranks = result.get("scores", {}).get("faction_ranks", {})
    if not faction_ranks:
        return []
    faction_models = result.get("faction_models", {})
    scenario = scenario_key(result, filename)
    return [
        (scenario, model_label(faction_models.get(faction)), int(rank))
        for faction, rank in faction_ranks.items()
    ]


def aggregate(
    samples: list[tuple[str, str, int]]
) -> dict[tuple[str, str], dict[str, Any]]:
    """Pool rank samples into mean_rank / win_rate per (scenario, model)."""
    grouped: dict[tuple[str, str], list[int]] = {}
    for scenario, model, rank in samples:
        grouped.setdefault((scenario, model), []).append(rank)
    return {
        key: {
            "n": len(ranks),
            "mean_rank": statistics.mean(ranks),
            "win_rate": sum(1 for r in ranks if r == 1) / len(ranks),
        }
        for key, ranks in grouped.items()
    }


def is_no_deal(result: dict[str, Any]) -> bool:
    """True when the game explicitly reached no deal (``deal_reached`` is False).

    In that case every faction is scored at BATNA, so the ranks are
    BATNA-determined rather than negotiated. Missing/True deal_reached -> kept.
    """
    return result.get("scores", {}).get("deal_reached") is False


def aggregate_files(
    paths: list[str],
    include_no_deal: bool = False,
) -> tuple[dict[tuple[str, str], dict[str, Any]], int, int, int]:
    """Aggregate result-file paths.

    Returns (agg, n_used, n_skipped, n_no_deal_excluded). No-deal games
    (deal_reached=False) are excluded by default since their ranks are
    BATNA-determined; pass include_no_deal=True to keep them.
    """
    samples: list[tuple[str, str, int]] = []
    used = 0
    skipped = 0
    no_deal_excluded = 0
    for path in paths:
        try:
            result = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            skipped += 1
            continue
        file_samples = extract_samples(result, path)
        if not file_samples:
            skipped += 1
            continue
        if not include_no_deal and is_no_deal(result):
            no_deal_excluded += 1
            continue
        samples.extend(file_samples)
        used += 1
    return aggregate(samples), used, skipped, no_deal_excluded


def render(agg: dict[tuple[str, str], dict[str, Any]]) -> str:
    """Markdown-ish table, grouped by scenario, best mean_rank first."""
    lines = [
        "| scenario | model | n | mean_rank | win_rate |",
        "|---|---|---|---|---|",
    ]
    for (scenario, model), stats in sorted(
        agg.items(), key=lambda kv: (kv[0][0], kv[1]["mean_rank"], kv[0][1])
    ):
        lines.append(
            f"| {scenario} | {model} | {stats['n']} | "
            f"{stats['mean_rank']:.2f} | {stats['win_rate']:.2f} |"
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--results",
        nargs="+",
        default=["tests/self_play/results/run17_*.json"],
        help="Result JSON file paths or globs (default: run17_*.json).",
    )
    parser.add_argument(
        "--include-no-deal",
        action="store_true",
        help=(
            "Include no-deal games (deal_reached=False). Excluded by default "
            "because their ranks are BATNA-determined, not negotiated."
        ),
    )
    args = parser.parse_args(argv)

    paths: list[str] = []
    for pattern in args.results:
        paths.extend(sorted(glob.glob(pattern)))

    if not paths:
        print("No result files matched.")
        return 1

    agg, used, skipped, no_deal = aggregate_files(
        paths, include_no_deal=args.include_no_deal
    )
    if not agg:
        print(
            f"Matched {len(paths)} file(s) but none usable for ranking "
            f"(skipped {skipped}, {no_deal} no-deal excluded). Re-run games "
            f"after the rank-lens commit, or pass --include-no-deal."
        )
        return 1

    note = "" if args.include_no_deal else f", {no_deal} no-deal excluded"
    print(f"Aggregated {used} game result(s) ({skipped} skipped{note}).\n")
    print(render(agg))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
