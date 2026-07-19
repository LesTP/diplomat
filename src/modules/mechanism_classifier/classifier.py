from __future__ import annotations

from pathlib import Path


DEFAULT_PROMPT_PATH = "config/prompts/mechanism_classifier.txt"
DEFAULT_SCHEMA_PATH = "config/schemas/mechanism_classifier.json"


def schema_path() -> Path:
    """Return the packaged schema location for the mechanism judge."""
    return Path(DEFAULT_SCHEMA_PATH)

