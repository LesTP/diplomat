"""Backfill cost metadata on historical self-play run JSONs.

For each result JSON that lacks a ``metadata.cost_source``, re-estimates the
per-run LLM spend from ``llm_call_log`` (token ≈ len(text)/4, priced via
toolkit/cost_accountant's DEFAULT_PRICING table for consistency with live runs)
and writes:

    metadata.cost_usd      float  estimated total spend in USD
    metadata.cost_source   str    "estimated_from_log"
    metadata.n_llm_calls   int    number of log entries processed

Idempotent: skips runs already carrying ``cost_source = "metered"``.
Existing metadata keys (e.g. ``recovery``, ``bare_mode``) are preserved.

Note: accuracy is bounded by toolkit/cost_accountant's pricing table at
run time.  Model names are resolved from ``faction_models`` when present
(set by the per-faction-providers path); unknown factions fall back to
per-provider commodity defaults.

Usage:
    python tools/backfill_cost.py --results tests/self_play/results/*.json
    python tools/backfill_cost.py --results tests/self_play/results/run12_symmetric_live.json --write-back
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Provider → default commodity model for calls without faction_models.
# Chosen to match the most common model used per provider in diplomat runs.
_PROVIDER_DEFAULTS: dict[str, str] = {
    "openai": "gpt-4.1-mini",
    "anthropic": "claude-haiku-4-5",
    "google": "gemini-2.5-flash-lite",
    "openrouter": "deepseek/deepseek-v3",
}

# Mid-range fallback when provider is unknown.
_FALLBACK_MODEL = "gpt-4.1-mini"


def _resolve_model(
    faction_id: str,
    config_provider: str,
    faction_models: dict[str, Any],
) -> str:
    """Return the best-guess model name for one log entry."""
    if faction_id and faction_id != "unknown" and faction_id in faction_models:
        model = faction_models[faction_id].get("model")
        if model:
            return model
    return _PROVIDER_DEFAULTS.get(config_provider.lower(), _FALLBACK_MODEL)


def _entry_cost_usd(
    entry: dict[str, Any],
    faction_models: dict[str, Any],
    pricing: dict[str, Any],
    normalize_fn: Any,
) -> float:
    """Return estimated USD cost for one llm_call_log entry."""
    model = _resolve_model(
        entry.get("faction_id", "unknown"),
        entry.get("config_provider", ""),
        faction_models,
    )

    messages = entry.get("messages", [])
    input_tokens = sum(len(m.get("content", "")) for m in messages) // 4
    output_tokens = max(len(entry.get("response", "")) // 4, 1)

    model_pricing = pricing.get(model)
    if model_pricing is None:
        normalized = normalize_fn(model)
        if normalized != model:
            model_pricing = pricing.get(normalized)
    if model_pricing is None:
        # Match CostAccountant's conservative fallback for unknown models.
        from toolkit.cost_accountant.types import ModelPricing
        model_pricing = ModelPricing(input_per_mtok=15.0, output_per_mtok=75.0)

    return (
        input_tokens * model_pricing.input_per_mtok / 1_000_000
        + output_tokens * model_pricing.output_per_mtok / 1_000_000
    )


def estimate_cost_from_log(result: dict[str, Any]) -> tuple[float, int]:
    """Return (estimated_cost_usd, n_llm_calls) for a result dict.

    Importable by tests — does not write anything.
    """
    try:
        from toolkit.cost_accountant.core import normalize_model_name
        from toolkit.cost_accountant.types import DEFAULT_PRICING
    except ImportError:
        print(
            "ERROR: toolkit not importable. Install with: pip install -e ../toolkit",
            file=sys.stderr,
        )
        sys.exit(1)

    log = result.get("llm_call_log") or []
    faction_models = result.get("faction_models") or {}
    total = 0.0
    for entry in log:
        total += _entry_cost_usd(entry, faction_models, DEFAULT_PRICING, normalize_model_name)
    return total, len(log)


def backfill_result(
    result: dict[str, Any],
    write_back: bool,
    path: Path,
) -> str:
    """Apply cost metadata to one result dict. Returns a human-readable status line."""
    meta = dict(result.get("metadata") or {})
    if meta.get("cost_source") == "metered":
        return "skipped (already metered)"

    cost_usd, n_calls = estimate_cost_from_log(result)

    meta["cost_usd"] = cost_usd
    meta["cost_source"] = "estimated_from_log"
    meta["n_llm_calls"] = n_calls
    result["metadata"] = meta

    if write_back:
        path.write_text(
            json.dumps(result, indent=2, sort_keys=False),
            encoding="utf-8",
        )
        return f"wrote ${cost_usd:.4f} ({n_calls} calls)"

    return f"estimated ${cost_usd:.4f} ({n_calls} calls)"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--results",
        nargs="+",
        required=True,
        metavar="FILE",
        help="One or more result JSON file paths (shell glob expansion supported)",
    )
    parser.add_argument(
        "--write-back",
        action="store_true",
        help="Write updated metadata back into each result JSON (default: dry run)",
    )
    args = parser.parse_args()

    paths = [Path(p) for p in args.results]
    missing = [p for p in paths if not p.is_file()]
    if missing:
        for p in missing:
            print(f"ERROR: file not found: {p}", file=sys.stderr)
        sys.exit(2)

    print(f"\n{'='*60}")
    print(f"  COST BACKFILL — {len(paths)} file(s)")
    print(f"  mode: {'write-back' if args.write_back else 'dry run'}")
    print(f"{'='*60}\n")

    total_estimated = 0.0
    skipped = 0
    for path in sorted(paths):
        result = json.loads(path.read_text(encoding="utf-8"))
        status = backfill_result(result, args.write_back, path)
        print(f"  {path.name}: {status}")
        if "skipped" not in status:
            total_estimated += result["metadata"]["cost_usd"]
        else:
            skipped += 1

    processed = len(paths) - skipped
    print(f"\n  Processed: {processed}  Skipped (metered): {skipped}")
    print(f"  Estimated total: ${total_estimated:.4f}")
    if not args.write_back:
        print("  (dry run — pass --write-back to update files)")


if __name__ == "__main__":
    main()
