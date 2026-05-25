from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from modules.types import Divergence, StoredEvent


@dataclass(frozen=True)
class CoachingEntry:
    coaching_type: str
    content: str
    timestamp: datetime

    def __post_init__(self) -> None:
        if self.timestamp.tzinfo is None:
            object.__setattr__(
                self, "timestamp", self.timestamp.replace(tzinfo=timezone.utc)
            )


@dataclass(frozen=True)
class DecisionContext:
    system_prompt: str
    user_prompt: str
    metadata: dict[str, Any]


class DefaultContextAssembler:
    INCLUDED_COACHING_TYPES = frozenset(
        {"PRIORITY", "CONSTRAINT", "TONE", "WATCH", "FREE"}
    )

    def __init__(self, recent_events_limit: int = 30) -> None:
        if recent_events_limit < 0:
            raise ValueError("recent_events_limit must be non-negative")
        self.recent_events_limit = recent_events_limit

    async def assemble(
        self,
        persona_prompt: str,
        round_context: str,
        intelligence: dict[str, Any],
        divergences: list[Divergence],
        recent_events: list[StoredEvent],
        free_coaching: list[CoachingEntry],
        review_gate_enabled: bool,
    ) -> DecisionContext:
        included_events = self._limit_recent_events(recent_events)
        included_coaching = self._filter_coaching(free_coaching)

        user_prompt = "\n\n".join(
            [
                round_context.strip(),
                "--- INTELLIGENCE SUMMARY ---\n"
                + json.dumps(intelligence, indent=2, sort_keys=True),
                "--- ANALYST DIVERGENCES ---\n"
                + self._format_divergences(divergences),
                f"--- RECENT TRANSCRIPT (last {self.recent_events_limit} messages) ---\n"
                + self._format_recent_events(included_events),
                "--- COACHING FROM OPERATOR ---\n"
                + self._format_coaching(included_coaching),
                "--- TASK ---\n"
                "Generate your faction's next message for the diplomatic channel.\n"
                "Treat analyst divergences as genuinely uncertain.\n"
                + self._format_output_instruction(review_gate_enabled),
            ]
        )

        return DecisionContext(
            system_prompt=persona_prompt.strip(),
            user_prompt=user_prompt,
            metadata={
                "round_number": self._round_number(included_events),
                "event_count": len(included_events),
                "coaching_count": len(included_coaching),
            },
        )

    def _limit_recent_events(self, events: list[StoredEvent]) -> list[StoredEvent]:
        if self.recent_events_limit == 0:
            return []
        return events[-self.recent_events_limit :]

    def _filter_coaching(self, entries: list[CoachingEntry]) -> list[CoachingEntry]:
        return [
            entry
            for entry in entries
            if entry.coaching_type.upper() in self.INCLUDED_COACHING_TYPES
        ]

    def _format_divergences(self, divergences: list[Divergence]) -> str:
        if not divergences:
            return "No divergences. Both analysts agree."

        return "\n".join(
            (
                f"- {divergence.field}: primary={divergence.primary_value}; "
                f"secondary={divergence.secondary_value}; note={divergence.note}"
            )
            for divergence in divergences
        )

    def _format_recent_events(self, events: list[StoredEvent]) -> str:
        if not events:
            return "No recent transcript events."

        separator = " \u2014 "
        return "\n".join(
            (
                f"[Round {stored.round_number} | "
                f"{stored.event.sender_faction} | {stored.event.channel}"
                f"{separator}{stored.event.content}]"
            )
            for stored in events
        )

    def _format_coaching(self, entries: list[CoachingEntry]) -> str:
        exclusion_note = "INTEL notes excluded - already applied to database."
        if not entries:
            return f"{exclusion_note}\nNo additional coaching this round."

        lines = [exclusion_note]
        lines.extend(
            f"- {entry.coaching_type.upper()}: {entry.content}" for entry in entries
        )
        return "\n".join(lines)

    def _format_output_instruction(self, review_gate_enabled: bool) -> str:
        if review_gate_enabled:
            return (
                'Return JSON with keys "response" and "reasoning" so the review '
                "gate can present both fields."
            )
        return "Return plain text containing only the message to send."

    def _round_number(self, events: list[StoredEvent]) -> int | None:
        if not events:
            return None
        return events[-1].round_number


__all__ = ["CoachingEntry", "DecisionContext", "DefaultContextAssembler"]
