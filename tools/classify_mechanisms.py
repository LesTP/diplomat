"""Classify self-play result JSONs by failure mechanism.

Usage:
    python tools/classify_mechanisms.py --results-dir tests/self_play/results
    python tools/classify_mechanisms.py --results-dir tests/self_play/results --dry-run
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from adapters import ToolkitLLMAdapter
from modules.mechanism_classifier import build_mechanism_classifier

DEFAULT_PIPELINE_CONFIG = os.getenv("DIPLOMAT_PIPELINE_CONFIG", "config/pipeline.yaml")
DEFAULT_TIER = "commodity"
DEFAULT_RESULTS_DIR = Path("tests/self_play/results")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--results-dir",
        "--input-dir",
        dest="input_dir",
        required=True,
        help="Directory containing result JSON files",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Optional output file path; defaults to stdout",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Use the zero-cost DryRunLLMClient instead of a real provider",
    )
    parser.add_argument(
        "--config",
        default=DEFAULT_PIPELINE_CONFIG,
        help="Pipeline config path used to resolve provider/model defaults",
    )
    parser.add_argument(
        "--tier",
        default=DEFAULT_TIER,
        help="LLM tier to use for mechanism classification",
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

    input_dir = Path(args.input_dir)
    result_paths = _discover_result_files(input_dir)
    if not result_paths:
        _write_output("No valid result JSON files found.\n", args.output)
        return 0

    classifier = _build_classifier(args)
    rows: list[dict[str, Any]] = []
    for path in result_paths:
        try:
            result = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        label = await classifier.classify(result)
        rows.append(_row_from_result(path.name, result, label))

    table = _render_table(rows)
    summary = _render_summary(rows)
    _write_output(f"{table}\n\n{summary}\n", args.output)
    return 0


def _discover_result_files(results_dir: Path) -> list[Path]:
    if not results_dir.exists() or not results_dir.is_dir():
        return []
    return sorted(path for path in results_dir.glob("*.json") if path.is_file())


def _build_classifier(args: argparse.Namespace) -> Any:
    config = _load_pipeline_config(Path(args.config))
    if args.dry_run:
        from tests.self_play.fake_llm_client import DryRunLLMClient

        llm_client = DryRunLLMClient()
        primary = _primary_provider(config, args)
        classifier = build_mechanism_classifier(
            llm_client=llm_client,
            llm_providers_config={"primary": primary},
            tier=args.tier,
            attribution="classify_mechanisms",
        )
        if classifier is None:
            raise RuntimeError("Unable to build mechanism classifier in dry-run mode")
        return classifier

    primary = _primary_provider(config, args)
    llm_module = _load_toolkit_module("llm_client")
    llm_client = ToolkitLLMAdapter(llm_module)
    classifier = build_mechanism_classifier(
        llm_client=llm_client,
        llm_providers_config={"primary": primary},
        tier=args.tier,
        attribution="classify_mechanisms",
    )
    if classifier is None:
        raise RuntimeError("Unable to build mechanism classifier from pipeline config")
    return classifier


def _primary_provider(config: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
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
    return primary


def _load_pipeline_config(config_path: Path) -> dict[str, Any]:
    if not config_path.exists():
        raise FileNotFoundError(f"Pipeline config not found: {config_path}")
    config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    if not isinstance(config, dict):
        raise ValueError(f"Pipeline config must be a mapping: {config_path}")
    return config


def _load_toolkit_module(name: str) -> Any:
    try:
        return __import__(f"toolkit.{name}", fromlist=[name])
    except ImportError as exc:
        raise RuntimeError(
            f"Unable to import toolkit.{name}; install ../toolkit editable first"
        ) from exc


def _row_from_result(filename: str, result: dict[str, Any], label: str) -> dict[str, Any]:
    q_values = _question_values(result)
    row = {"file": filename, "label": label, **q_values}
    return row


def _question_values(result: dict[str, Any]) -> dict[str, str]:
    source: dict[str, Any] | None = None
    candidates = [
        result.get("mechanism_judgment"),
        result.get("mechanism_classification"),
        result,
    ]
    for candidate in candidates:
        if isinstance(candidate, dict) and all(
            key in candidate for key in ("q1", "q2", "q3", "q4", "q5")
        ):
            source = candidate
            break

    values: dict[str, str] = {}
    for key in ("q1", "q2", "q3", "q4", "q5"):
        if source is None:
            values[key] = "n/a"
            continue
        value = source.get(key)
        if isinstance(value, bool):
            values[key] = "yes" if value else "no"
        else:
            values[key] = str(value)
    return values


def _render_table(rows: list[dict[str, Any]]) -> str:
    headers = ["file", "label", "q1", "q2", "q3", "q4", "q5"]
    lines = ["| " + " | ".join(headers) + " |"]
    lines.append("| " + " | ".join(["---"] + ["---"] + ["---"] * 5) + " |")
    for row in rows:
        lines.append(
            "| "
            + " | ".join(
                str(row.get(header, "")) for header in headers
            )
            + " |"
        )
    return "\n".join(lines)


def _render_summary(rows: list[dict[str, Any]]) -> str:
    counts = Counter(row["label"] for row in rows)
    parts = [f"{label}: {counts[label]}" for label in sorted(counts)]
    return "Summary: " + (", ".join(parts) if parts else "no labels")


def _write_output(text: str, output: str | None) -> None:
    if output:
        Path(output).write_text(text, encoding="utf-8")
    else:
        print(text, end="")


def main() -> None:
    args = _parse_args()
    raise SystemExit(asyncio.run(_run(args)))


if __name__ == "__main__":
    main()
