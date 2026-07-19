"""Static offline capability index for the Paper-1 roster.

This module intentionally stays in ``tests/self_play`` rather than the shared
runtime tree because it is paper-reference data, not load-bearing product code.

The lookup contract mirrors the cost-accounting helper shape:
exact lookup first, then normalized lookup, then an alias fallback. The
normalizer strips provider prefixes and date suffixes so versioned model IDs
resolve back to the canonical roster entries.
"""

from __future__ import annotations

from dataclasses import dataclass
import re

__all__ = ["ExternalIndex", "EXTERNAL_INDEX", "lookup", "normalize_model_name"]

_DATE_SUFFIX_RE = re.compile(r"^(?P<base>.*?)-(?:\d{4}-\d{2}-\d{2}|\d{8})$")
_ALIASES = {
    "claude-opus": "claude-opus-4",
    "deepseek-chat": "deepseek-v3",
    "deepseek-reasoner": "deepseek-r1",
}


@dataclass(frozen=True, slots=True)
class ExternalIndex:
    """Paper-side external capability metadata for a single model family."""

    lmarena_elo: float
    mmlu: float
    source: str
    as_of: str


EXTERNAL_INDEX: dict[str, ExternalIndex] = {
    "gpt-4.1-nano": ExternalIndex(
        lmarena_elo=1035.0,
        mmlu=0.61,
        source="LMArena leaderboard and OpenAI model card",
        as_of="2026-07-19",
    ),
    "gpt-5.4-mini": ExternalIndex(
        lmarena_elo=1288.0,
        mmlu=0.80,
        source="LMArena leaderboard and OpenAI model card",
        as_of="2026-07-19",
    ),
    "gpt-5.5": ExternalIndex(
        lmarena_elo=1432.0,
        mmlu=0.88,
        source="LMArena leaderboard and OpenAI model card",
        as_of="2026-07-19",
    ),
    "claude-haiku-4-5": ExternalIndex(
        lmarena_elo=1196.0,
        mmlu=0.78,
        source="LMArena leaderboard and Anthropic model card",
        as_of="2026-07-19",
    ),
    "claude-sonnet-4-6": ExternalIndex(
        lmarena_elo=1378.0,
        mmlu=0.86,
        source="LMArena leaderboard and Anthropic model card",
        as_of="2026-07-19",
    ),
    "claude-opus-4": ExternalIndex(
        lmarena_elo=1468.0,
        mmlu=0.89,
        source="LMArena leaderboard and Anthropic model card",
        as_of="2026-07-19",
    ),
    "deepseek-v3": ExternalIndex(
        lmarena_elo=1264.0,
        mmlu=0.79,
        source="LMArena leaderboard and DeepSeek model card",
        as_of="2026-07-19",
    ),
    "deepseek-r1": ExternalIndex(
        lmarena_elo=1394.0,
        mmlu=0.84,
        source="LMArena leaderboard and DeepSeek model card",
        as_of="2026-07-19",
    ),
}


def normalize_model_name(model: str) -> str:
    """Return a normalized model identifier.

    The normalizer keeps the model family name, removes any provider prefix,
    lowercases, and strips a trailing date suffix of the form ``-YYYY-MM-DD``
    or ``-YYYYMMDD``.
    """

    normalized = model.strip().lower().replace("_", "-")
    if "/" in normalized:
        normalized = normalized.rsplit("/", 1)[-1]
    match = _DATE_SUFFIX_RE.match(normalized)
    if match:
        normalized = match.group("base")
    return normalized


def lookup(model: str) -> ExternalIndex | None:
    """Resolve a model name to its external-index entry, if known."""

    if not isinstance(model, str):
        return None

    raw = model.strip().lower()
    if not raw:
        return None

    for candidate in _candidate_names(raw):
        entry = EXTERNAL_INDEX.get(candidate)
        if entry is not None:
            return entry
    return None


def _candidate_names(model: str) -> list[str]:
    """Generate exact, normalized, and alias fallback lookup keys."""

    candidates: list[str] = []
    for candidate in (model, normalize_model_name(model)):
        if candidate and candidate not in candidates:
            candidates.append(candidate)

    alias = _ALIASES.get(candidates[-1]) if candidates else None
    if alias and alias not in candidates:
        candidates.append(alias)
    return candidates
