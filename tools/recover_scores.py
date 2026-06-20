"""Recover scores from a self-play run whose scorer LLM emitted arithmetic
expressions in faction_scores.points (invalid JSON).

When the scoring structured_call gets a response like:
    "faction_scores": {
      "alpha": {"points": 3 + 10 + 3, "batna": 9},
      ...
    }
the JSON parser barfs at `+` and the entire scores section ends up as
{"error": "Scoring failed: ..."}. The actual game outcome is intact in
the LLM response (visible in llm_call_log) — just needs the arithmetic
evaluated and re-injected.

This script:
  1. Loads the failed run JSON.
  2. Reads the last llm_call_log entry (the failed scoring call's response).
  3. Regex-extracts faction_scores.points / batna expressions, evaluates
     the arithmetic (restricted-namespace eval — only ints + - * /).
  4. Reconstructs a clean scores dict (deal_reached, agreed_outcomes,
     faction_scores, reasoning).
  5. Computes derived Phase 27 + Phase 29 metrics by importing the same
     game_environment helpers used in live scoring.
  6. Writes results back to the same JSON file.

Usage:
    python3 tools/recover_scores.py \\
        --results tests/self_play/results/run14_full_gpt54mini_beta_squeezed_2.json \\
        --analysis scenarios/water_rights_beta_squeezed/scenario_analysis.json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tests.self_play.game_environment import (
    _compute_baselines,
    _pareto_efficiency_metrics,
)


_SAFE_NS = {"__builtins__": {}}


def _safe_eval_arith(expr: str) -> float:
    """Evaluate a simple arithmetic expression of integer/float literals.

    Restricted: no names, no builtins, no function calls. Only the
    operators + - * / (and unary -). Raises ValueError on anything else.
    """
    if not re.fullmatch(r"[\s0-9+\-*/.()]+", expr):
        raise ValueError(f"unsafe characters in {expr!r}")
    return eval(expr, _SAFE_NS, {})  # noqa: S307 - sandbox above


def _recover_score_data_from_response(response_text: str) -> dict:
    """Patch arithmetic expressions in faction_scores into computed numbers,
    then parse the result as JSON."""
    patched = re.sub(
        r'("points"\s*:\s*)([0-9+\-*/.\s]+?)(\s*,)',
        lambda m: f'{m.group(1)}{_safe_eval_arith(m.group(2))}{m.group(3)}',
        response_text,
    )
    patched = re.sub(
        r'("batna"\s*:\s*)([0-9+\-*/.\s]+?)(\s*[,\}])',
        lambda m: f'{m.group(1)}{_safe_eval_arith(m.group(2))}{m.group(3)}',
        patched,
    )
    return json.loads(patched)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", required=True)
    parser.add_argument("--analysis", required=True)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print recovered scores but don't write back to the JSON.",
    )
    args = parser.parse_args()

    results_path = Path(args.results)
    analysis_path = Path(args.analysis)

    results = json.loads(results_path.read_text(encoding="utf-8"))
    analysis = json.loads(analysis_path.read_text(encoding="utf-8"))

    calls = results.get("llm_call_log", [])
    if not calls:
        print("ERROR: no llm_call_log in results", file=sys.stderr)
        sys.exit(2)

    # Last call is the scoring call (per game_environment ordering).
    last_call = calls[-1]
    response_text = last_call.get("response_text") or last_call.get("response", "")
    if not response_text:
        print("ERROR: last llm call has no response text", file=sys.stderr)
        sys.exit(2)

    try:
        score_data = _recover_score_data_from_response(response_text)
    except Exception as e:
        print(f"ERROR recovering scores: {e}", file=sys.stderr)
        print(f"Response was:\n{response_text[:1000]}", file=sys.stderr)
        sys.exit(2)

    # Compute the derived metrics the live path would have added.
    score_data.update(_pareto_efficiency_metrics(analysis, score_data))
    score_data.update(_compute_baselines(analysis, score_data))

    print("Recovered scores:")
    for key in (
        "deal_reached",
        "faction_scores",
        "pareto_efficiency",
        "negotiated_surplus_share",
        "delta_above_batna_sum",
        "faction_deltas",
        "skill_premium_vs_batna",
    ):
        print(f"  {key}: {score_data.get(key)}")

    if args.dry_run:
        print("\n[dry-run] Not writing back.")
        return

    results["scores"] = score_data
    # Add a marker so the audit trail is clear about what happened.
    results.setdefault("metadata", {}).setdefault("recovery", []).append(
        {
            "tool": "tools/recover_scores.py",
            "reason": "scoring LLM emitted arithmetic expressions in points/batna",
            "method": "regex + restricted-eval of points/batna; re-ran _pareto_efficiency_metrics + _compute_baselines",
        }
    )
    results_path.write_text(
        json.dumps(results, indent=2, sort_keys=False),
        encoding="utf-8",
    )
    print(f"\nWrote recovered scores back to {results_path}")


if __name__ == "__main__":
    main()
