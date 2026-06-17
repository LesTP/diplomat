#!/usr/bin/env python3
"""Regenerate the Diplomat negotiation-outcome dashboards.

    python tools/build_viz.py

Add a scenario by appending a (analysis, title, output) tuple to JOBS.
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "tests/self_play/results"

JOBS = [
    (
        "tests/self_play/scenarios/water_rights_beta_squeezed/scenario_analysis.json",
        "Water Rights (beta-squeezed)",
        "viz_wrbeta.html",
    ),
    (
        "tests/self_play/scenarios/joint_space_mission_v1/scenario_analysis.json",
        "Joint Space Mission v1",
        "viz_jsm1.html",
    ),
]


def main() -> int:
    for analysis, title, out in JOBS:
        subprocess.run(
            [
                sys.executable,
                str(ROOT / "tools" / "viz.py"),
                "--analysis", str(ROOT / analysis),
                "--results-dir", str(RESULTS),
                "--title", title,
                "--output", str(ROOT / out),
            ],
            check=True,
        )
    print("Done ->", ", ".join(out for _, _, out in JOBS))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
