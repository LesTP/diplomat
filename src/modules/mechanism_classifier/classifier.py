from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping


DEFAULT_PROMPT_PATH = "config/prompts/mechanism_classifier.txt"
DEFAULT_SCHEMA_PATH = "config/schemas/mechanism_classifier.json"


def derive_label(answers: Mapping[str, Any]) -> str:
    """Derive the final mechanism label from the judge's five boolean answers."""
    q1 = bool(answers.get("q1", False))
    q2 = bool(answers.get("q2", False))
    q3 = bool(answers.get("q3", False))
    q4 = bool(answers.get("q4", False))
    q5 = bool(answers.get("q5", False))

    if q5:
        return "closed"
    if q4:
        return "incoherence"
    if q3 and q1:
        return "strategic_refusal"
    if q2 and q1:
        return "near_miss"
    return "breakdown"


def schema_path() -> Path:
    """Return the packaged schema location for the mechanism judge."""
    return Path(DEFAULT_SCHEMA_PATH)
