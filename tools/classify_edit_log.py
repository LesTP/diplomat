"""Classify review-gate edit logs into the Phase 33 edit categories.

Usage:
    python tools/classify_edit_log.py --db data/game.db
    python tools/classify_edit_log.py --db data/game.db --force
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from adapters import ToolkitLLMAdapter
from modules.edit_classifier import EditClassification, build_edit_classifier
from modules.state_manager import SQLiteStateManager

DEFAULT_PIPELINE_CONFIG = os.getenv("DIPLOMAT_PIPELINE_CONFIG", "config/pipeline.yaml")
DEFAULT_TIER = "commodity"
_UNAVAILABLE_ORIGINAL = "[original draft unavailable]"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, help="Path to the SQLite game DB")
    parser.add_argument(
        "--game-id",
        help="Optional game identifier for forward-compatible filtering",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Reclassify edited rows even if a classification already exists",
    )
    parser.add_argument(
        "--config",
        default=DEFAULT_PIPELINE_CONFIG,
        help="Pipeline config path used to resolve provider/model defaults",
    )
    parser.add_argument(
        "--tier",
        default=DEFAULT_TIER,
        help="LLM tier to use for edit classification",
    )
    parser.add_argument(
        "--provider",
        help="Override the primary provider name from pipeline.yaml",
    )
    parser.add_argument(
        "--model",
        help="Override the model used for the selected tier",
    )
    return parser.parse_args()


async def _run(args: argparse.Namespace) -> int:
    load_dotenv()

    config = _load_pipeline_config(Path(args.config))
    classifier = _build_classifier(config, args)
    state_manager = SQLiteStateManager(args.db, "config/schemas/state_patch.json")

    edited_rows = await _load_edited_rows(state_manager)
    classified_ids = set()
    if not args.force:
        classified_rows = await state_manager.get_edit_classifications(
            game_id=args.game_id
        )
        classified_ids = {row["review_gate_edit_id"] for row in classified_rows}

    to_classify = [
        row for row in edited_rows if args.force or row["id"] not in classified_ids
    ]

    for row in to_classify:
        classification = await classifier.classify(
            *_row_to_classifier_inputs(row),
        )
        await state_manager.store_edit_classification(row["id"], classification)

    summary_rows = await state_manager.get_edit_classifications(game_id=args.game_id)
    _print_summary(summary_rows)
    print(f"Classified {len(to_classify)} edited row(s).")
    return 0


def _load_pipeline_config(config_path: Path) -> dict[str, Any]:
    if not config_path.exists():
        raise FileNotFoundError(f"Pipeline config not found: {config_path}")
    config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    if not isinstance(config, dict):
        raise ValueError(f"Pipeline config must be a mapping: {config_path}")
    return config


def _build_classifier(config: dict[str, Any], args: argparse.Namespace) -> Any:
    providers = dict(config.get("llm_providers") or {})
    primary = dict(providers.get("primary") or {})
    if not primary:
        raise RuntimeError("Pipeline config missing llm_providers.primary")

    if args.provider:
        primary["provider"] = args.provider
    if args.model:
        models = dict(primary.get("models") or {})
        models[args.tier] = args.model
        primary["models"] = models

    llm_module = _load_toolkit_module("llm_client")
    llm_client = ToolkitLLMAdapter(llm_module)
    classifier = build_edit_classifier(
        llm_client=llm_client,
        llm_providers_config={"primary": primary},
        tier=args.tier,
        attribution="classify_edit_log",
    )
    if classifier is None:
        raise RuntimeError("Unable to build edit classifier from pipeline config")
    return classifier


def _load_toolkit_module(name: str) -> Any:
    try:
        return __import__(f"toolkit.{name}", fromlist=[name])
    except ImportError as exc:
        raise RuntimeError(
            f"Unable to import toolkit.{name}; install ../toolkit editable first"
        ) from exc


async def _load_edited_rows(state_manager: SQLiteStateManager) -> list[dict[str, Any]]:
    rows = await state_manager.query("review_gate_edits", {})
    return [row for row in rows if row.get("decision") == "edited"]


def _row_to_classifier_inputs(row: dict[str, Any]) -> tuple[str, str, str | None]:
    edited_text = (row.get("edit_text") or "").strip() or "[edited draft unavailable]"
    original_text = row.get("original_text")
    if isinstance(original_text, str) and original_text.strip():
        original_text = original_text.strip()
    else:
        original_text = _UNAVAILABLE_ORIGINAL

    revise_directives = row.get("revise_directives")
    if isinstance(revise_directives, list) and revise_directives:
        notes = "revise directives: " + "; ".join(str(item) for item in revise_directives)
    else:
        notes = None
    return original_text, edited_text, notes


def _print_summary(rows: list[dict[str, Any]]) -> None:
    by_category: dict[str, dict[str, Any]] = {}
    counts: defaultdict[str, int] = defaultdict(int)

    for row in rows:
        category = row["category"]
        counts[category] += 1
        current = by_category.get(category)
        if current is None or row["id"] > current["id"]:
            by_category[category] = row

    print("| category | count | most_recent_example_id |")
    print("| --- | ---: | ---: |")
    for category in sorted(counts):
        row = by_category[category]
        print(f"| {category} | {counts[category]} | {row['id']} |")


def main() -> None:
    args = _parse_args()
    raise SystemExit(asyncio.run(_run(args)))


if __name__ == "__main__":
    main()
