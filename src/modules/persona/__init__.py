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
        total_rounds: int | None = None,
    ) -> str:
        # If total_rounds is given, derive rounds_remaining authoritatively from it.
        if total_rounds is not None:
            effective_remaining: int | None = total_rounds - round_number
            round_line = f"Round: {round_number} of {total_rounds}"
            remaining_display = str(effective_remaining)
        else:
            effective_remaining = rounds_remaining
            round_line = f"Round: {round_number}"
            remaining_display = (
                "unknown" if rounds_remaining is None else str(rounds_remaining)
            )

        sections: list[str] = [
            _ROUND_CONTEXT_MARKER,
            "",
            round_line,
            f"Rounds remaining: {remaining_display}",
            "",
        ]

        # Endgame reminder fires only in the last two rounds (penultimate + final).
        if effective_remaining is not None and effective_remaining <= 1:
            if effective_remaining == 0:
                sections.extend(
                    [
                        "### FINAL ROUND",
                        "This is the last round. Your standing offer at the end of this round "
                        "is what gets scored against your private table. State your final "
                        "proposal clearly. There are no more chances to adjust.",
                        "",
                    ]
                )
            else:  # effective_remaining == 1
                sections.extend(
                    [
                        "### PENULTIMATE ROUND",
                        "Only one round remains after this. Move toward concrete commitments "
                        "now. Whatever offer you carry into the final round is what gets "
                        "scored — don't leave your best terms for too late.",
                        "",
                    ]
                )

        sections.extend(
            [
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
        )
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
