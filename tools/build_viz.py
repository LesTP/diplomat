#!/usr/bin/env python3
"""Regenerate the Diplomat deal-explorer dashboards.

    python tools/build_viz.py

Each job renders ``deal_explorer.html`` into its own scenario folder (the
narrative .md is auto-detected by ``tools/viz.py`` via ``find_narrative``).
Add a scenario by appending a (scenario_dir, title) tuple to JOBS.
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "tests/self_play/results"

# (scenario_dir relative to scenarios/, h1 title)
JOBS = [
    ("water_rights_beta_squeezed", "Water Rights (beta-squeezed)"),
    ("joint_space_mission_v1", "Joint Space Mission v1"),
    ("succession_division_v3", "succ-v3 — Verdanian Succession (Resolvable Contest)"),
    ("succession_division_v3b", "succ3b — Verdanian Succession (Two-Way Heartland)"),
]


def main() -> int:
    outputs = []
    for scenario_dir, title in JOBS:
        sdir = ROOT / "scenarios" / scenario_dir
        out = sdir / "deal_explorer.html"
        subprocess.run(
            [
                sys.executable,
                str(ROOT / "tools" / "viz.py"),
                "--analysis", str(sdir / "scenario_analysis.json"),
                "--results-dir", str(RESULTS),
                "--title", title,
                "--output", str(out),
            ],
            check=True,
        )
        outputs.append(str(out.relative_to(ROOT)))
    print("Done ->", ", ".join(outputs))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
