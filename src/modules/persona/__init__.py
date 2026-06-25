from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from scenario_authoring.round_context import (
    CoachingContext,
    _strip_round_context,
    render_round_context_section,
)


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
        *,
        pressure: Mapping[str, Any] | None = None,
        priority_collision: str = "none",
        faction_id: str | None = None,
        base_batna: float | int | None = None,
        current_best_offer: float | int | None = None,
    ) -> str:
        return render_round_context_section(
            round_number=round_number,
            rounds_remaining=rounds_remaining,
            coaching_context=coaching_context,
            total_rounds=total_rounds,
            pressure=pressure,
            priority_collision=priority_collision,
            faction_id=faction_id,
            base_batna=base_batna,
            current_best_offer=current_best_offer,
        )


__all__ = [
    "CoachingContext",
    "FileBasedPersona",
    "render_round_context_section",
]
