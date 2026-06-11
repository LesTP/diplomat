from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


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


def _strip_round_context(text: str) -> str:
    before_marker, marker, _after_marker = text.partition(_ROUND_CONTEXT_MARKER)
    if not marker:
        return text.rstrip()
    return before_marker.rstrip()


def _format_items(items: list[str]) -> list[str]:
    if not items:
        return ["- (none)"]
    return [f"- {item}" for item in items]


def _format_number(value: float | int) -> str:
    return f"{value:g}"


def _format_pressure_lines(pressure: Mapping[str, Any] | None) -> list[str]:
    if not pressure:
        return []

    lines: list[str] = []
    round_cost_decay = pressure.get("round_cost_decay", 0.0)
    penalty_floor_offset = pressure.get("penalty_floor_offset", 0.0)
    asymmetric_clocks = pressure.get("asymmetric_clocks", {})

    if round_cost_decay or penalty_floor_offset or asymmetric_clocks:
        lines.append("### Pressure")
        if round_cost_decay:
            lines.append(
                f"- Round cost decay: {_format_number(round_cost_decay)} points per round"
            )
        if penalty_floor_offset:
            lines.append(
                f"- Penalty floor offset: {_format_number(penalty_floor_offset)} points"
            )
        if not round_cost_decay and not penalty_floor_offset:
            lines.append("- (no round cost decay or penalty floor offset)")
        lines.append("")
    return lines


def _format_deadline_lines(
    pressure: Mapping[str, Any] | None,
    *,
    priority_collision: str,
    faction_id: str | None,
) -> list[str]:
    if not pressure or priority_collision == "none":
        return []

    asymmetric_clocks = pressure.get("asymmetric_clocks", {})
    if not isinstance(asymmetric_clocks, dict) or not asymmetric_clocks:
        return []

    deadlines: list[tuple[str, Any]] = []
    for other_faction, deadline in asymmetric_clocks.items():
        if faction_id is not None and other_faction == faction_id:
            continue
        deadlines.append((other_faction, deadline))
    if not deadlines:
        return []

    deadlines.sort(key=lambda item: (item[1], item[0]))
    label = "### Opponent Deadlines" if faction_id is not None else "### Deadlines"
    lines = [label]
    for other_faction, deadline in deadlines:
        lines.append(f"- {other_faction}: round {deadline}")
    lines.append("")
    return lines


def _format_effective_batna_line(
    *,
    base_batna: float | int | None,
    round_number: int,
    pressure: Mapping[str, Any] | None,
    rounds_remaining: int | None,
    total_rounds: int | None,
) -> str | None:
    if not pressure:
        return None

    round_cost_decay = pressure.get("round_cost_decay", 0.0)
    penalty_floor_offset = pressure.get("penalty_floor_offset", 0.0)
    if base_batna is None:
        return (
            "Effective BATNA: BATNA - "
            f"(({round_number} - 1) * {_format_number(round_cost_decay)}) - "
            f"{_format_number(penalty_floor_offset)}"
        )

    effective_batna = base_batna - ((round_number - 1) * round_cost_decay) - penalty_floor_offset
    if rounds_remaining == 0 or (total_rounds is not None and total_rounds - round_number == 0):
        prefix = "Effective BATNA this round"
    elif rounds_remaining == 1 or (total_rounds is not None and total_rounds - round_number == 1):
        prefix = "Effective BATNA next round"
    else:
        prefix = "Effective BATNA"
    return (
        f"{prefix}: {_format_number(effective_batna)} points "
        f"(BATNA - (({round_number} - 1) * {_format_number(round_cost_decay)}) - "
        f"{_format_number(penalty_floor_offset)})"
    )


def _format_final_round_lines(
    *,
    base_batna: float | int | None,
    current_best_offer: float | int | None,
    round_number: int,
    pressure: Mapping[str, Any] | None,
    rounds_remaining: int | None,
    total_rounds: int | None,
) -> list[str]:
    if base_batna is None and current_best_offer is None:
        return []

    lines: list[str] = []
    if base_batna is not None and current_best_offer is not None:
        lines.append(
            "No deal = "
            f"{_format_number(base_batna)} pts (your BATNA); "
            f"current best offer = {_format_number(current_best_offer)} pts; "
            f"walking away costs you {_format_number(current_best_offer - base_batna)} pts."
        )
    if base_batna is not None:
        lines.append(f"No deal = {_format_number(base_batna)} points (your BATNA).")
    if current_best_offer is not None:
        lines.append(f"Current best offer = {_format_number(current_best_offer)} points.")
    if base_batna is not None and current_best_offer is not None:
        lines.append(
            f"Walking away costs you {_format_number(current_best_offer - base_batna)} points."
        )

    if pressure:
        effective_batna_line = _format_effective_batna_line(
            base_batna=base_batna,
            round_number=round_number,
            pressure=pressure,
            rounds_remaining=rounds_remaining,
            total_rounds=total_rounds,
        )
        if effective_batna_line:
            lines.append(effective_batna_line)
    return lines


def render_round_context_section(
    *,
    round_number: int,
    rounds_remaining: int | None,
    coaching_context: CoachingContext,
    total_rounds: int | None = None,
    pressure: Mapping[str, Any] | None = None,
    priority_collision: str = "none",
    faction_id: str | None = None,
    base_batna: float | int | None = None,
    current_best_offer: float | int | None = None,
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

    pressure_lines = _format_pressure_lines(pressure)
    if pressure_lines:
        sections.extend(pressure_lines)

    # Endgame reminder fires only in the last two rounds (penultimate + final).
    if effective_remaining is not None and effective_remaining <= 1:
        if effective_remaining == 0:
            sections.extend(
                [
                    "### FINAL ROUND",
                    "This is the last round. Your standing offer at the end of this round "
                    "is what gets scored against your private table. No deal = your "
                    "BATNA; compare the current best offer against that baseline and "
                    "state your final proposal clearly. There are no more chances to "
                    "adjust.",
                ]
            )
            final_round_lines = _format_final_round_lines(
                base_batna=base_batna,
                current_best_offer=current_best_offer,
                round_number=round_number,
                pressure=pressure,
                rounds_remaining=effective_remaining,
                total_rounds=total_rounds,
            )
            sections.extend(final_round_lines)
            sections.append("")
        else:  # effective_remaining == 1
            effective_batna_line = _format_effective_batna_line(
                base_batna=base_batna,
                round_number=round_number,
                pressure=pressure,
                rounds_remaining=effective_remaining,
                total_rounds=total_rounds,
            )
            sections.extend(
                [
                    "### PENULTIMATE ROUND",
                    "Only one round remains after this. Move toward concrete commitments "
                    "now. Whatever offer you carry into the final round is what gets "
                    "scored — don't leave your best terms for too late.",
                ]
            )
            if effective_batna_line:
                sections.append(effective_batna_line)
            sections.append("")

    deadline_lines = _format_deadline_lines(
        pressure,
        priority_collision=priority_collision,
        faction_id=faction_id,
    )
    if deadline_lines:
        sections.extend(deadline_lines)

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


__all__ = [
    "CoachingContext",
    "FileBasedPersona",
    "render_round_context_section",
]
