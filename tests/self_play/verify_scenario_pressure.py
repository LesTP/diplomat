"""Verify BATNA-pressure invariants on a compiled scenario analysis.

Checks that a scenario's pressure profile actually creates deadline-driven
pressure:
- deadlines are present and surfaced when priority collision is enabled
- effective BATNA drops by at least the requested fraction by each deadline
- the deadline round renders as a final-round / accept-or-bust context

Usage:
    python -m tests.self_play.verify_scenario_pressure \
        --analysis tests/self_play/scenarios/scenario_analysis.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from modules.persona import CoachingContext, render_round_context_section
from scenario_authoring.scenario_compiler import max_possible_score


def effective_batna(
    base_batna: float,
    *,
    round_cost_decay: float,
    penalty_floor_offset: float,
    round_number: int,
) -> float:
    """Return the round-N effective BATNA under the configured pressure."""
    return base_batna - ((round_number - 1) * round_cost_decay) - penalty_floor_offset


def deadline_context(
    analysis: dict[str, Any],
    faction_id: str,
) -> str:
    """Render the deadline-round context for one faction.

    We intentionally set total_rounds == deadline so the verifier exercises the
    same final-round branch the persona uses when a deadline becomes the last
    chance to reach agreement.
    """
    pressure = analysis["pressure"]
    deadline = pressure["asymmetric_clocks"][faction_id]
    base_batna = float(analysis["batna"][faction_id])
    current_best_offer = float(max_possible_score(analysis, faction_id))
    return render_round_context_section(
        round_number=deadline,
        rounds_remaining=0,
        total_rounds=deadline,
        coaching_context=CoachingContext(
            priorities=[],
            constraints=[],
            watch_items=[],
            tone_notes=[],
        ),
        pressure=pressure,
        priority_collision=str(analysis.get("priority_collision") or "none"),
        faction_id=faction_id,
        base_batna=base_batna,
        current_best_offer=current_best_offer,
    )


def verify_pressure_profile(
    analysis: dict[str, Any],
    *,
    min_drop_pct: float = 0.20,
) -> tuple[list[str], list[str]]:
    """Return (report_lines, failures) for a scenario pressure analysis."""
    report_lines: list[str] = []
    failures: list[str] = []

    pressure = analysis.get("pressure")
    if not isinstance(pressure, dict):
        return report_lines, ["scenario analysis is missing a pressure object"]

    round_cost_decay = float(pressure.get("round_cost_decay", 0.0))
    penalty_floor_offset = float(pressure.get("penalty_floor_offset", 0.0))
    asymmetric_clocks = pressure.get("asymmetric_clocks", {})
    priority_collision = str(analysis.get("priority_collision") or "none")
    factions = list(analysis.get("factions", []))
    batnas = analysis.get("batna", {})

    if not isinstance(asymmetric_clocks, dict):
        return report_lines, ["pressure.asymmetric_clocks must be an object"]
    if not asymmetric_clocks:
        failures.append("pressure.asymmetric_clocks is empty; no deadline pressure to verify")
    if asymmetric_clocks and priority_collision == "none":
        failures.append(
            "pressure deadlines are present but priority_collision is 'none', so "
            "the deadline pressure will not surface in persona round context"
        )

    report_lines.append(
        "Pressure: "
        f"round_cost_decay={round_cost_decay:g}, "
        f"penalty_floor_offset={penalty_floor_offset:g}, "
        f"priority_collision={priority_collision}"
    )
    if asymmetric_clocks:
        deadline_bits = ", ".join(
            f"{faction}→round {deadline}"
            for faction, deadline in sorted(asymmetric_clocks.items(), key=lambda item: (item[1], item[0]))
        )
        report_lines.append(f"Deadlines: {deadline_bits}")

    for faction_id in factions:
        deadline = asymmetric_clocks.get(faction_id)
        if deadline is None:
            continue

        base_batna = float(batnas.get(faction_id, 0.0))
        max_score = float(max_possible_score(analysis, faction_id))
        if base_batna <= 0:
            failures.append(f"{faction_id}: BATNA must be positive to evaluate pressure")
            continue
        if max_score <= 0:
            failures.append(f"{faction_id}: max possible score is zero; cannot verify pressure")
            continue

        effective = effective_batna(
            base_batna,
            round_cost_decay=round_cost_decay,
            penalty_floor_offset=penalty_floor_offset,
            round_number=int(deadline),
        )
        drop_pct = (base_batna - effective) / base_batna
        report_lines.append(
            f"  {faction_id}: BATNA={base_batna:g}, deadline={deadline}, "
            f"effective={effective:g} ({drop_pct:.0%} drop of BATNA, "
            f"{effective / max_score:.0%} of max)"
        )

        if drop_pct < min_drop_pct:
            failures.append(
                f"{faction_id}: effective BATNA falls by only {drop_pct:.0%} at round {deadline}; "
                f"need at least {min_drop_pct:.0%} pressure"
            )

        context = deadline_context(analysis, faction_id)
        if (
            "### FINAL ROUND" not in context
            or "Current best offer" not in context
            or "No deal =" not in context
        ):
            failures.append(
                f"{faction_id}: deadline round does not render an accept-or-bust final-round context"
            )

    return report_lines, failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--analysis", required=True, help="Path to scenario_analysis.json")
    parser.add_argument(
        "--min-drop-pct",
        type=float,
        default=0.20,
        help="Minimum BATNA drop required by each deadline (default: 0.20)",
    )
    args = parser.parse_args()

    analysis_path = Path(args.analysis)
    if not analysis_path.is_file():
        print(f"ERROR: {analysis_path} not found", file=sys.stderr)
        return 1

    analysis = json.loads(analysis_path.read_text(encoding="utf-8"))
    factions = analysis.get("factions", [])

    print("=" * 70)
    print(f"PRESSURE VERIFICATION: {analysis_path}")
    print("=" * 70)
    print(f"\nFactions: {', '.join(factions)}")

    report_lines, failures = verify_pressure_profile(
        analysis,
        min_drop_pct=args.min_drop_pct,
    )

    for line in report_lines:
        print(line)

    print("\n--- Deadline Context Check ---")
    pressure = analysis.get("pressure") or {}
    asymmetric_clocks = pressure.get("asymmetric_clocks", {})
    if isinstance(asymmetric_clocks, dict) and asymmetric_clocks:
        for faction_id in sorted(asymmetric_clocks, key=lambda fid: (asymmetric_clocks[fid], fid)):
            context = deadline_context(analysis, faction_id)
            first_lines = context.splitlines()[:6]
            print(f"  {faction_id}:")
            for line in first_lines:
                print(f"    {line}")
    else:
        print("  (no deadlines to inspect)")

    print("\n--- VERDICT ---")
    if failures:
        print(f"FAIL — {len(failures)} pressure invariants violated:\n")
        for failure in failures:
            print(f"  * {failure}")
        return 2

    print("PASS — deadline pressure is surfaced and meaningful.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
