from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, ValidationError

from modules.types import StatePatch


@dataclass(frozen=True)
class ExtractionResult:
    success: bool
    patch: StatePatch | None
    error: str | None = None


def load_prompt(prompt_path: str | Path) -> str:
    return Path(prompt_path).read_text(encoding="utf-8").strip()


def load_schema(schema_path: str | Path) -> dict[str, Any]:
    return parse_json_object(Path(schema_path).read_text(encoding="utf-8"))


def parse_json_object(response_text: str) -> dict[str, Any]:
    try:
        parsed = json.loads(response_text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"LLM response was not valid JSON: {exc.msg}") from exc

    if not isinstance(parsed, dict):
        raise ValueError("LLM response JSON must be an object")
    return parsed


def validate_state_patch(
    patch_data: dict[str, Any], schema: dict[str, Any]
) -> StatePatch:
    try:
        Draft202012Validator(schema).validate(patch_data)
    except ValidationError as exc:
        path = ".".join(str(part) for part in exc.absolute_path)
        location = f" at {path}" if path else ""
        raise ValueError(f"State patch failed schema validation{location}: {exc.message}") from exc
    return StatePatch(patch_data)


__all__ = [
    "ExtractionResult",
    "load_prompt",
    "load_schema",
    "parse_json_object",
    "validate_state_patch",
]
