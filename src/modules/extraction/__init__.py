from __future__ import annotations

import json
import re
from dataclasses import dataclass
from inspect import isawaitable
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


class OpenAIStructuredExtractor:
    def __init__(
        self,
        llm_client: Any,
        llm_config: Any,
        schema_path: str | Path,
        prompt_path: str | Path,
        tier: Any | None = None,
    ) -> None:
        self.llm_client = llm_client
        self.llm_config = llm_config
        self.schema = load_schema(schema_path)
        self.system_prompt = load_prompt(prompt_path)
        self.tier = tier if tier is not None else _commodity_tier()

    async def extract(
        self, input_text: str, current_state: dict[str, Any], trigger_type: str
    ) -> ExtractionResult:
        try:
            response_text = await self._complete(
                self._build_messages(input_text, current_state, trigger_type)
            )
            patch_data = parse_json_object(response_text)
            patch = validate_state_patch(patch_data, self.schema)
        except Exception as exc:
            return ExtractionResult(success=False, patch=None, error=str(exc))

        return ExtractionResult(success=True, patch=patch)

    async def _complete(self, messages: list[dict[str, str]]) -> str:
        response = self.llm_client.complete(
            messages=messages,
            config=self.llm_config,
            tier=self.tier,
        )
        if isawaitable(response):
            response = await response
        if not isinstance(response, str):
            raise ValueError("LLM response must be plain text")
        return response

    def _build_messages(
        self, input_text: str, current_state: dict[str, Any], trigger_type: str
    ) -> list[dict[str, str]]:
        if trigger_type not in {"message", "intel_correction"}:
            raise ValueError(f"Unsupported trigger_type: {trigger_type}")

        trigger_note = (
            "[OPERATOR INTEL] Treat this as a high-confidence correction."
            if trigger_type == "intel_correction"
            else "Treat this as an observed game message."
        )
        user_prompt = "\n\n".join(
            [
                trigger_note,
                "State patch JSON schema:",
                json.dumps(self.schema, sort_keys=True),
                "Current state snapshot:",
                json.dumps(current_state, sort_keys=True),
                "Input text:",
                input_text,
            ]
        )
        return [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": user_prompt},
        ]


def load_prompt(prompt_path: str | Path) -> str:
    return Path(prompt_path).read_text(encoding="utf-8").strip()


def load_schema(schema_path: str | Path) -> dict[str, Any]:
    text = Path(schema_path).read_text(encoding="utf-8")
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Schema file is not valid JSON: {exc.msg}") from exc
    if not isinstance(parsed, dict):
        raise ValueError("Schema file must be a JSON object")
    return parsed


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
        raise ValueError(
            f"State patch failed schema validation{location}: {exc.message}"
        ) from exc
    return StatePatch(patch_data)


def _commodity_tier() -> Any:
    try:
        from toolkit.llm_client import ModelTier
    except ImportError:
        return "commodity"
    return ModelTier.COMMODITY


__all__ = [
    "ExtractionResult",
    "OpenAIStructuredExtractor",
    "RuleBasedExtractor",
    "load_prompt",
    "load_schema",
    "parse_json_object",
    "validate_state_patch",
]
