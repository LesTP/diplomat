from __future__ import annotations

import json
import re
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


class RuleBasedExtractor:
    _FACTION = r"([A-Z][A-Za-z0-9_-]*)"
    _PROMISE_RE = re.compile(
        rf"\b{_FACTION}\s+promises?\s+{_FACTION}\s+(.+?)(?:[.!?]|$)",
    )
    _COALITION_RE = re.compile(
        rf"\b{_FACTION}\s+(?:and|&)\s+{_FACTION}\s+"
        r"(?:form|formed|are forming|announce|announced)\s+"
        r"(?:a\s+)?coalition(?:\s+(.+?))?(?:[.!?]|$)",
    )
    _INCONSISTENCY_RE = re.compile(
        rf"\b{_FACTION}\s+(?:contradicts?|contradicted|breaks?|broke|violates?|violated)\s+"
        r"(.+?)(?:[.!?]|$)",
    )

    def __init__(self, schema_path: str | Path) -> None:
        self.schema = load_schema(schema_path)

    async def extract(
        self, input_text: str, current_state: dict[str, Any], trigger_type: str
    ) -> ExtractionResult:
        patch_data = self._extract_patch(input_text)
        return ExtractionResult(
            success=True,
            patch=validate_state_patch(patch_data, self.schema),
        )

    def _extract_patch(self, input_text: str) -> dict[str, Any]:
        coalition_match = self._COALITION_RE.search(input_text)
        if coalition_match:
            faction_a, faction_b, basis = coalition_match.groups()
            return {
                "coalitions": [
                    {
                        "coalition_id": self._entity_id("coalition", input_text),
                        "faction_a": faction_a,
                        "faction_b": faction_b,
                        "confidence": 0.7,
                        "basis": basis.strip() if basis else "reported coalition",
                    }
                ]
            }

        inconsistency_match = self._INCONSISTENCY_RE.search(input_text)
        if inconsistency_match:
            faction_id, description = inconsistency_match.groups()
            return {
                "inconsistencies": [
                    {
                        "inconsistency_id": self._entity_id(
                            "inconsistency", input_text
                        ),
                        "faction_id": faction_id,
                        "description": description.strip(),
                        "leverage_value": 0.5,
                        "spent": False,
                    }
                ]
            }

        promise_match = self._PROMISE_RE.search(input_text)
        if promise_match:
            from_faction, to_faction, content = promise_match.groups()
            return {
                "promises": [
                    {
                        "promise_id": self._entity_id("promise", input_text),
                        "from_faction": from_faction,
                        "to_faction": to_faction,
                        "content": content.strip(),
                        "status": "pending",
                    }
                ]
            }

        return {}

    @staticmethod
    def _entity_id(prefix: str, text: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
        return f"{prefix}-{slug[:48] or 'unknown'}"


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
    "RuleBasedExtractor",
    "load_prompt",
    "load_schema",
    "parse_json_object",
    "validate_state_patch",
]
