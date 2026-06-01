from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from toolkit.structured_llm import (
    Example,
    load_schema as _tk_load_schema,
    parse_json_response as _tk_parse_json,
    structured_call,
    structured_complete,
    validate_json_schema,
)

from modules.types import StatePatch


@dataclass(frozen=True)
class ExtractionResult:
    success: bool
    patch: StatePatch | None
    error: str | None = None


# ---------------------------------------------------------------------------
# Rule-based extractor (free, no LLM)
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# LLM-based extractor using structured_call
# ---------------------------------------------------------------------------


class OpenAIStructuredExtractor:
    def __init__(
        self,
        llm_client: Any,
        llm_config: Any,
        schema_path: str | Path,
        prompt_path: str | Path,
        examples_path: str | Path = "config/examples/extraction_examples.json",
        tier: Any | None = None,
    ) -> None:
        self.llm_client = llm_client
        self.llm_config = llm_config
        self.schema = load_schema(schema_path)
        self.system_prompt = load_prompt(prompt_path)
        self.examples = load_examples(examples_path)
        self.tier = tier if tier is not None else _commodity_tier()

    async def extract(
        self, input_text: str, current_state: dict[str, Any], trigger_type: str
    ) -> ExtractionResult:
        user_prompt = self._build_user_prompt(input_text, current_state, trigger_type)

        result = await structured_call(
            self.llm_client,
            self.llm_config,
            self.tier,
            schema=self.schema,
            system_prompt=self.system_prompt,
            user_prompt=user_prompt,
            examples=self.examples,
            max_retries=1,
            purpose="extraction",
        )

        if not result.success:
            return ExtractionResult(success=False, patch=None, error=result.error)

        return ExtractionResult(success=True, patch=StatePatch(result.data or {}))

    def _build_user_prompt(
        self, input_text: str, current_state: dict[str, Any], trigger_type: str
    ) -> str:
        trigger_note = (
            "[OPERATOR INTEL] Treat this as a high-confidence correction."
            if trigger_type == "intel_correction"
            else "Treat this as an observed game message."
        )
        return "\n\n".join(
            [
                trigger_note,
                "Current state snapshot:",
                json.dumps(current_state, sort_keys=True),
                "Input text:",
                input_text,
            ]
        )


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def load_prompt(prompt_path: str | Path) -> str:
    return Path(prompt_path).read_text(encoding="utf-8").strip()


def load_schema(schema_path: str | Path) -> dict[str, Any]:
    return _tk_load_schema(schema_path)


def load_examples(examples_path: str | Path) -> list[Example]:
    data = json.loads(Path(examples_path).read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("Extraction examples file must contain a JSON array")

    examples: list[Example] = []
    for index, item in enumerate(data):
        if not isinstance(item, dict):
            raise ValueError(f"Extraction example {index} must be an object")
        input_text = item.get("input")
        output = item.get("output")
        if not isinstance(input_text, str) or not isinstance(output, dict):
            raise ValueError(
                f"Extraction example {index} requires string input and object output"
            )
        examples.append(Example(input=input_text, output=output))
    return examples


def parse_json_object(response_text: str) -> dict[str, Any]:
    return _tk_parse_json(response_text)


def validate_state_patch(
    patch_data: dict[str, Any], schema: dict[str, Any]
) -> StatePatch:
    validate_json_schema(patch_data, schema, label="State patch failed schema validation")
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
    "load_examples",
    "load_prompt",
    "load_schema",
    "parse_json_object",
    "validate_state_patch",
]
