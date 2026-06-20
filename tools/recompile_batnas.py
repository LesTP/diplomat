"""Generate asymmetric-BATNA variants of an already-compiled scenario.

No LLM call — purely deterministic. Reads an existing scenario_analysis.json,
force-clamps BATNAs per the requested per-faction targets, writes a new
scenario_analysis.json + personas to a new output directory.

Usage:
    python tools/recompile_batnas.py \\
        --source tests/self_play/scenarios/water_rights_compiled \\
        --output-dir tests/self_play/scenarios/water_rights_alpha_squeezed \\
        --batna-fractions '{"alpha":0.70,"beta":0.40,"gamma":0.50}' \\
        --title "Clearwater River Basin"
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Allow `from scenario_authoring.scenario_compiler import ...` when invoked from project root.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT / "src"))

from scenario_authoring.scenario_compiler import (  # noqa: E402
    force_batna_targets,
    generate_persona,
    save_analysis,
    save_persona,
    validate_batna_pressure,
)


def _parse_fractions_arg(arg: str) -> dict[str, float]:
    """Accept JSON map, file path, or shorthand 'k=v,k=v'."""
    arg = arg.strip()
    p = Path(arg)
    if p.is_file():
        arg = p.read_text(encoding="utf-8").strip()
    if arg.startswith("{"):
        return {k: float(v) for k, v in json.loads(arg).items()}
    # Shorthand: k=v,k=v
    out: dict[str, float] = {}
    for chunk in arg.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        if "=" not in chunk:
            raise SystemExit(f"Bad shorthand piece (need k=v): {chunk!r}")
        k, v = chunk.split("=", 1)
        out[k.strip()] = float(v.strip())
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        required=True,
        help="Directory containing scenario_analysis.json to derive from",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        help="Directory to write the variant scenario_analysis.json + personas",
    )
    parser.add_argument(
        "--batna-fractions",
        required=True,
        help='JSON map of faction_id -> BATNA fraction (e.g. \'{"alpha":0.7,"beta":0.4,"gamma":0.5}\'), '
             'OR a shorthand "alpha=0.7,beta=0.4,gamma=0.5", '
             'OR a path to a JSON file containing the map.',
    )
    parser.add_argument(
        "--batna-fraction",
        type=float,
        default=0.50,
        help="Scalar fallback for factions not listed in --batna-fractions",
    )
    parser.add_argument("--title", default="a multi-party negotiation")
    args = parser.parse_args()

    src = Path(args.source) / "scenario_analysis.json"
    analysis = json.loads(src.read_text(encoding="utf-8"))
    fractions = _parse_fractions_arg(args.batna_fractions)

    new_analysis = force_batna_targets(
        analysis,
        target_fraction=args.batna_fraction,
        target_fractions=fractions,
    )

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    analysis_path = save_analysis(new_analysis, out_dir)
    print(f"Analysis saved: {analysis_path}")

    warnings = validate_batna_pressure(
        new_analysis,
        target_fraction=args.batna_fraction,
        target_fractions=fractions,
    )
    if warnings:
        print("BATNA pressure warnings:")
        for w in warnings:
            print(f"  - {w}")

    print(f"\nNew BATNAs:")
    for f in new_analysis["factions"]:
        scoring = new_analysis["scoring"][f]
        max_score = sum(max(v.values()) for v in scoring.values())
        batna = new_analysis["batna"][f]
        target = fractions.get(f, args.batna_fraction)
        print(f"  {f}: BATNA={batna}  max={max_score}  ratio={batna/max_score:.0%}  target={target:.0%}")

    for faction_id in new_analysis["factions"]:
        persona = generate_persona(faction_id, new_analysis, args.title)
        path = save_persona(faction_id, persona, out_dir)
        print(f"Persona saved: {path}")


if __name__ == "__main__":
    main()
