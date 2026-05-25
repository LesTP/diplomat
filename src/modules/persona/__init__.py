from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


_ROUND_CONTEXT_MARKER = "## CURRENT ROUND CONTEXT"


@dataclass(frozen=True)
class CoachingContext:
    priorities: list[str]
    constraints: list[str]
    watch_items: list[str]
    tone_notes: list[str]


class FileBasedPersona:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._mtime_ns: int | None = None
        self._base_prompt: str | None = None

    async def get_base_prompt(self) -> str:
        stat_result = self.path.stat()
        if self._base_prompt is not None and self._mtime_ns == stat_result.st_mtime_ns:
            return self._base_prompt

        text = self.path.read_text(encoding="utf-8")
        self._base_prompt = _strip_round_context(text)
        self._mtime_ns = stat_result.st_mtime_ns
        return self._base_prompt

    async def build_round_context(
        self,
        round_number: int,
        rounds_remaining: int | None,
        coaching_context: CoachingContext,
    ) -> str:
        remaining = "unknown" if rounds_remaining is None else str(rounds_remaining)
        sections = [
            _ROUND_CONTEXT_MARKER,
            "",
            f"Round: {round_number}",
            f"Rounds remaining: {remaining}",
            "",
            "### Priorities",
            *_format_items(coaching_context.priorities),
            "",
            "### Constraints",
            *_format_items(coaching_context.constraints),
            "",
            "### Watch Items",
            *_format_items(coaching_context.watch_items),
            "",
            "### Tone Notes",
            *_format_items(coaching_context.tone_notes),
        ]
        return "\n".join(sections)


def _strip_round_context(text: str) -> str:
    before_marker, marker, _after_marker = text.partition(_ROUND_CONTEXT_MARKER)
    if not marker:
        return text.rstrip()
    return before_marker.rstrip()


def _format_items(items: list[str]) -> list[str]:
    if not items:
        return ["- (none)"]
    return [f"- {item}" for item in items]


__all__ = [
    "CoachingContext",
    "FileBasedPersona",
]
