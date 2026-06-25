"""Per-scenario brief: declare intended structural features, then check the
measured scenario structure against them.

A brief is a small JSON artifact (`brief.json`) declaring the *discriminating
properties* a scenario is supposed to have, plus an optional prose companion
(`brief.md`). `check_brief` measures the actual structure of a
`scenario_analysis.json` and reports PASS/FAIL per declared feature — the
machine-checkable gate that earlier benchmark runs lacked (a constant-sum
distributive scenario that still had a behavioral focal point, and a
hard-collision variant that deadlocked, both shipped to live runs undetected).

All structural math is reused from `verify_scenario_optimum` and
`scenario_fitness`; this module adds only the brief schema, the per-feature
comparison, and the auto-doc renderer. It depends only on those two sibling
modules + stdlib (no toolkit, no pipeline).

Usage:
    python -m scenario_authoring.scenario_brief \\
        --analysis scenarios/foo_v1/scenario_analysis.json \\
        --brief scenarios/foo_v1/brief.json \\
        --doc scenarios/foo_v1/README.md
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from scenario_authoring.scenario_fitness import _priority_collision_level
from scenario_authoring.verify_scenario_optimum import (
    beats_batna,
    compute_focal_deal,
    enumerate_deals,
    faction_score,
    format_deal,
)

# Tolerance for treating two floating-point deal sums as equal.
_SUM_TOLERANCE = 1e-9

_COLLISION_VALUES = {"none", "soft", "hard"}


# ---------------------------------------------------------------------------
# Brief loading / validation
# ---------------------------------------------------------------------------


def _validate_bool(value: Any, *, label: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{label} must be a boolean")
    return value


def _validate_collision(value: Any, *, label: str) -> str:
    if value not in _COLLISION_VALUES:
        raise ValueError(f"{label} must be one of {sorted(_COLLISION_VALUES)}")
    return value


def _validate_winner_spread(value: Any, *, label: str) -> dict[str, int]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object with 'min_per_faction'")
    if "min_per_faction" not in value:
        raise ValueError(f"{label} must declare 'min_per_faction'")
    minimum = value["min_per_faction"]
    if isinstance(minimum, bool) or not isinstance(minimum, int) or minimum < 0:
        raise ValueError(f"{label}.min_per_faction must be a non-negative integer")
    return {"min_per_faction": minimum}


def _validate_batna_clearing_count(value: Any, *, label: str) -> dict[str, int]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object with 'min' and/or 'max'")
    bounds: dict[str, int] = {}
    for key in ("min", "max"):
        if key in value:
            bound = value[key]
            if isinstance(bound, bool) or not isinstance(bound, int) or bound < 0:
                raise ValueError(f"{label}.{key} must be a non-negative integer")
            bounds[key] = bound
    if not bounds:
        raise ValueError(f"{label} must declare at least one of 'min' / 'max'")
    if "min" in bounds and "max" in bounds and bounds["min"] > bounds["max"]:
        raise ValueError(f"{label} requires min <= max")
    return bounds


# Maps each supported feature key to its validator. Adding a feature here +
# a branch in check_brief is all it takes to extend the brief vocabulary.
_FEATURE_VALIDATORS = {
    "constant_sum": _validate_bool,
    "no_focal_point": _validate_bool,
    "no_exact_ties": _validate_bool,
    "priority_collision": _validate_collision,
    "winner_spread": _validate_winner_spread,
    "batna_clearing_count": _validate_batna_clearing_count,
}


def load_brief(path: str | Path) -> dict[str, Any]:
    """Load and validate a brief.json into a normalized dict.

    Returns a dict with keys ``features`` (validated) and ``prose`` (the
    optional free-text 'goal' string, defaulting to ""). Raises ValueError on
    unknown feature keys or malformed feature shapes.
    """
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("brief JSON must be an object")
    features = data.get("features", {})
    if not isinstance(features, dict) or not features:
        raise ValueError("brief must declare a non-empty 'features' object")

    validated: dict[str, Any] = {}
    for name, value in features.items():
        validator = _FEATURE_VALIDATORS.get(name)
        if validator is None:
            raise ValueError(
                f"unknown brief feature: {name!r}; "
                f"supported: {sorted(_FEATURE_VALIDATORS)}"
            )
        validated[name] = validator(value, label=f"features.{name}")

    prose = data.get("goal", "")
    if not isinstance(prose, str):
        raise ValueError("brief 'goal' must be a string")
    return {"features": validated, "goal": prose}


# ---------------------------------------------------------------------------
# Brief checking
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FeatureCheck:
    """Result of comparing one declared feature against measured structure."""

    name: str
    expected: Any
    observed: Any
    passed: bool


@dataclass(frozen=True)
class BriefResult:
    """Aggregate result of checking a scenario against a brief."""

    checks: list[FeatureCheck]

    @property
    def all_passed(self) -> bool:
        return all(check.passed for check in self.checks)

    @property
    def failed_features(self) -> list[str]:
        return [check.name for check in self.checks if not check.passed]


def _deal_sums(analysis: dict[str, Any], deals: list[dict[str, str]]) -> list[float]:
    factions = analysis["factions"]
    return [
        sum(faction_score(analysis, f, deal) for f in factions) for deal in deals
    ]


def _is_constant_sum(analysis: dict[str, Any], deals: list[dict[str, str]]) -> bool:
    sums = _deal_sums(analysis, deals)
    if not sums:
        return False
    return max(sums) - min(sums) <= _SUM_TOLERANCE


def _clearing_deals(
    analysis: dict[str, Any], deals: list[dict[str, str]]
) -> list[dict[str, float]]:
    """Per-faction score dicts for the deals that beat every BATNA."""
    factions = analysis["factions"]
    clearing: list[dict[str, float]] = []
    for deal in deals:
        scores = {f: faction_score(analysis, f, deal) for f in factions}
        if beats_batna(analysis, scores):
            clearing.append(scores)
    return clearing


def _winner_counts(
    analysis: dict[str, Any], clearing: list[dict[str, float]]
) -> dict[str, int]:
    """Count, over BATNA-clearing contest deals, how many each faction wins
    outright (strict single highest score). Tied-top deals award no winner.
    """
    counts = {f: 0 for f in analysis["factions"]}
    for scores in clearing:
        top = max(scores.values())
        winners = [f for f, v in scores.items() if v == top]
        if len(winners) == 1:
            counts[winners[0]] += 1
    return counts


def _has_exact_tie(clearing: list[dict[str, float]]) -> bool:
    """True when any contest deal's top score is shared by >= 2 factions."""
    for scores in clearing:
        top = max(scores.values())
        if sum(1 for v in scores.values() if v == top) >= 2:
            return True
    return False


def check_brief(analysis: dict[str, Any], brief: dict[str, Any]) -> BriefResult:
    """Measure ``analysis`` structure and compare against ``brief`` features.

    Only declared features are checked. Each produces one FeatureCheck. Reuses
    the canonical deal/structure math from verify_scenario_optimum +
    scenario_fitness; nothing here re-derives Pareto / BATNA / collision logic.
    """
    features = brief["features"]
    deals = enumerate_deals(analysis)
    clearing = _clearing_deals(analysis, deals)
    checks: list[FeatureCheck] = []

    if "constant_sum" in features:
        expected = features["constant_sum"]
        observed = _is_constant_sum(analysis, deals)
        checks.append(FeatureCheck("constant_sum", expected, observed, observed == expected))

    if "priority_collision" in features:
        expected = features["priority_collision"]
        observed = _priority_collision_level(analysis)
        checks.append(
            FeatureCheck("priority_collision", expected, observed, observed == expected)
        )

    if "no_focal_point" in features:
        expected = features["no_focal_point"]
        focal = compute_focal_deal(analysis)
        if focal is None:
            focal_clears = False
        else:
            scores = {f: faction_score(analysis, f, focal) for f in analysis["factions"]}
            focal_clears = beats_batna(analysis, scores)
        observed = not focal_clears
        checks.append(
            FeatureCheck("no_focal_point", expected, observed, observed == expected)
        )

    if "winner_spread" in features:
        minimum = features["winner_spread"]["min_per_faction"]
        counts = _winner_counts(analysis, clearing)
        observed_min = min(counts.values()) if counts else 0
        passed = observed_min >= minimum
        checks.append(
            FeatureCheck(
                "winner_spread",
                {"min_per_faction": minimum},
                {"per_faction": counts, "min": observed_min},
                passed,
            )
        )

    if "batna_clearing_count" in features:
        bounds = features["batna_clearing_count"]
        observed = len(clearing)
        passed = ("min" not in bounds or observed >= bounds["min"]) and (
            "max" not in bounds or observed <= bounds["max"]
        )
        checks.append(
            FeatureCheck("batna_clearing_count", bounds, observed, passed)
        )

    if "no_exact_ties" in features:
        expected = features["no_exact_ties"]
        observed = not _has_exact_tie(clearing)
        checks.append(
            FeatureCheck("no_exact_ties", expected, observed, observed == expected)
        )

    return BriefResult(checks=checks)


# ---------------------------------------------------------------------------
# Auto-doc
# ---------------------------------------------------------------------------


def build_brief_readme(
    analysis: dict[str, Any],
    brief: dict[str, Any],
    result: BriefResult,
    *,
    title: str = "Scenario",
    viz_rel_path: str | None = None,
) -> str:
    """Render a per-scenario README markdown: goal -> required features ->
    measured result -> link to the deal-explorer viz.
    """
    factions = ", ".join(analysis.get("factions", []))
    issues = ", ".join(i["name"] for i in analysis.get("issues", []))
    lines = [
        f"# {title}",
        "",
        f"- **Factions:** {factions}",
        f"- **Issues:** {issues}",
        f"- **Game mode:** {analysis.get('game_mode', '?')}",
        "",
    ]
    goal = brief.get("goal", "")
    if goal:
        lines += ["## Goal", "", goal.strip(), ""]

    lines += [
        "## Brief check",
        "",
        f"**Result: {'PASS' if result.all_passed else 'FAIL'}**",
        "",
        "| Feature | Expected | Observed | Result |",
        "|---|---|---|---|",
    ]
    for check in result.checks:
        mark = "PASS" if check.passed else "FAIL"
        lines.append(
            f"| {check.name} | {check.expected!r} | {check.observed!r} | {mark} |"
        )
    lines.append("")

    focal = compute_focal_deal(analysis)
    if focal is not None:
        lines += [
            "## 'Everyone-gets-priority' focal deal",
            "",
            f"`{format_deal(focal)}`",
            "",
        ]

    if viz_rel_path:
        lines += [f"[Deal explorer]({viz_rel_path})", ""]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--analysis", required=True, help="Path to scenario_analysis.json"
    )
    parser.add_argument("--brief", required=True, help="Path to brief.json")
    parser.add_argument(
        "--doc",
        default=None,
        metavar="PATH",
        help="Optional: also write a per-scenario README.md to PATH.",
    )
    parser.add_argument(
        "--title", default="Scenario", help="Scenario title for the doc header."
    )
    parser.add_argument(
        "--viz-rel-path",
        default=None,
        help="Optional relative path to a deal-explorer HTML to link from the doc.",
    )
    args = parser.parse_args()

    analysis_path = Path(args.analysis)
    brief_path = Path(args.brief)
    if not analysis_path.is_file():
        print(f"ERROR: {analysis_path} not found", file=sys.stderr)
        return 1
    if not brief_path.is_file():
        print(f"ERROR: {brief_path} not found", file=sys.stderr)
        return 1

    analysis = json.loads(analysis_path.read_text(encoding="utf-8"))
    brief = load_brief(brief_path)
    result = check_brief(analysis, brief)

    print(f"BRIEF CHECK: {analysis_path}")
    for check in result.checks:
        mark = "PASS" if check.passed else "FAIL"
        print(
            f"  [{mark}] {check.name}: "
            f"expected={check.expected!r} observed={check.observed!r}"
        )

    if args.doc:
        doc_text = build_brief_readme(
            analysis,
            brief,
            result,
            title=args.title,
            viz_rel_path=args.viz_rel_path,
        )
        doc_path = Path(args.doc)
        doc_path.parent.mkdir(parents=True, exist_ok=True)
        doc_path.write_text(doc_text, encoding="utf-8")
        print(f"Wrote doc: {doc_path}")

    if not result.all_passed:
        print(f"-> BRIEF FAILED: {', '.join(result.failed_features)}")
        return 2
    print("-> BRIEF PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
