from __future__ import annotations

from datetime import datetime, timezone

import pytest

from modules.context_assembler import (
    CoachingEntry,
    DecisionContext,
    DefaultContextAssembler,
)
from modules.types import Divergence, InboundEvent, StoredEvent


NOW = datetime(2026, 5, 25, 12, 0, tzinfo=timezone.utc)


def _event(index: int, round_number: int = 3) -> StoredEvent:
    return StoredEvent(
        event_id=f"event-{index}",
        round_number=round_number,
        event=InboundEvent(
            timestamp=NOW,
            sender_faction=f"Faction {index}",
            channel="press",
            content=f"Message {index}",
        ),
    )


def _coaching(coaching_type: str, content: str) -> CoachingEntry:
    return CoachingEntry(coaching_type=coaching_type, content=content, timestamp=NOW)


async def _assemble(
    *,
    divergences: list[Divergence] | None = None,
    recent_events: list[StoredEvent] | None = None,
    coaching: list[CoachingEntry] | None = None,
    review_gate_enabled: bool = True,
    recent_events_limit: int = 30,
    bare_mode: bool = False,
) -> DecisionContext:
    assembler = DefaultContextAssembler(recent_events_limit=recent_events_limit)
    return await assembler.assemble(
        persona_prompt="Base persona",
        round_context="Round context",
        intelligence={"threat_level": 3, "key_leverage_points": ["Belgium"]},
        divergences=divergences or [],
        recent_events=recent_events or [_event(1)],
        free_coaching=coaching or [],
        review_gate_enabled=review_gate_enabled,
        bare_mode=bare_mode,
    )


@pytest.mark.asyncio
async def test_all_five_coaching_types_present_and_intel_excluded():
    context = await _assemble(
        coaching=[
            _coaching("PRIORITY", "Secure Belgium."),
            _coaching("CONSTRAINT", "Do not promise Munich."),
            _coaching("TONE", "Sound confident."),
            _coaching("WATCH", "Watch Russia."),
            _coaching("FREE", "Mention the convoy."),
            _coaching("INTEL", "France lied last round."),
        ]
    )

    assert "- PRIORITY: Secure Belgium." in context.user_prompt
    assert "- CONSTRAINT: Do not promise Munich." in context.user_prompt
    assert "- TONE: Sound confident." in context.user_prompt
    assert "- WATCH: Watch Russia." in context.user_prompt
    assert "- FREE: Mention the convoy." in context.user_prompt
    assert "France lied last round." not in context.user_prompt
    assert "INTEL notes excluded - already applied to database." in context.user_prompt
    assert context.metadata["coaching_count"] == 5


@pytest.mark.asyncio
async def test_divergences_present_vs_absent():
    absent = await _assemble(divergences=[])
    present = await _assemble(
        divergences=[
            Divergence(
                field="threat_level",
                primary_value="2",
                secondary_value="5",
                note="Large disagreement.",
            )
        ]
    )

    assert "No divergences. Both analysts agree." in absent.user_prompt
    assert "- threat_level: primary=2; secondary=5; note=Large disagreement." in (
        present.user_prompt
    )


@pytest.mark.asyncio
async def test_review_gate_enabled_vs_disabled_instruction_text():
    enabled = await _assemble(review_gate_enabled=True)
    disabled = await _assemble(review_gate_enabled=False)

    assert 'Return JSON with keys "response" and "reasoning"' in enabled.user_prompt
    assert "review gate can present both fields" in enabled.user_prompt
    assert "Return plain text containing only the message to send." in (
        disabled.user_prompt
    )


@pytest.mark.asyncio
async def test_recent_events_limit_truncation_applied():
    context = await _assemble(
        recent_events=[_event(1), _event(2), _event(3, round_number=4)],
        recent_events_limit=2,
    )

    assert "Message 1" not in context.user_prompt
    assert "[Round 3 | Faction 2 | press" in context.user_prompt
    assert "[Round 4 | Faction 3 | press" in context.user_prompt
    assert "--- RECENT TRANSCRIPT (last 2 messages) ---" in context.user_prompt
    assert context.metadata["event_count"] == 2
    assert context.metadata["round_number"] == 4


@pytest.mark.asyncio
async def test_metadata_fields_event_count_and_coaching_count():
    context = await _assemble(
        recent_events=[_event(1), _event(2)],
        coaching=[_coaching("FREE", "Keep it short."), _coaching("INTEL", "Ignore.")],
    )

    assert context.metadata == {
        "round_number": 3,
        "event_count": 2,
        "coaching_count": 1,
    }


@pytest.mark.asyncio
async def test_empty_coaching_queue_placeholder():
    context = await _assemble(coaching=[])

    assert "No additional coaching this round." in context.user_prompt


@pytest.mark.asyncio
async def test_section_order_matches_template():
    context = await _assemble()

    assert context.system_prompt == "Base persona"
    assert context.user_prompt.index("Round context") < context.user_prompt.index(
        "--- INTELLIGENCE SUMMARY ---"
    )
    assert context.user_prompt.index("--- INTELLIGENCE SUMMARY ---") < (
        context.user_prompt.index("--- ANALYST DIVERGENCES ---")
    )
    assert context.user_prompt.index("--- ANALYST DIVERGENCES ---") < (
        context.user_prompt.index("--- RECENT TRANSCRIPT")
    )
    assert context.user_prompt.index("--- RECENT TRANSCRIPT") < (
        context.user_prompt.index("--- COACHING FROM OPERATOR ---")
    )
    assert context.user_prompt.index("--- COACHING FROM OPERATOR ---") < (
        context.user_prompt.index("--- TASK ---")
    )


@pytest.mark.asyncio
async def test_bare_mode_omits_intel_divergences_coaching():
    context = await _assemble(
        bare_mode=True,
        divergences=[
            Divergence(field="threat_level", primary_value="2", secondary_value="5", note="Disagree.")
        ],
        coaching=[_coaching("PRIORITY", "Secure Belgium.")],
    )

    assert "--- INTELLIGENCE SUMMARY ---" not in context.user_prompt
    assert "--- ANALYST DIVERGENCES ---" not in context.user_prompt
    assert "--- COACHING FROM OPERATOR ---" not in context.user_prompt
    assert "Round context" not in context.user_prompt
    assert "threat_level" not in context.user_prompt
    assert "Secure Belgium." not in context.user_prompt


@pytest.mark.asyncio
async def test_bare_mode_includes_persona_and_transcript():
    context = await _assemble(
        bare_mode=True,
        recent_events=[_event(1), _event(2, round_number=4)],
    )

    assert context.system_prompt == "Base persona"
    assert "--- TRANSCRIPT ---" in context.user_prompt
    assert "Message 1" in context.user_prompt
    assert "Message 2" in context.user_prompt
    assert "--- TASK ---" in context.user_prompt


@pytest.mark.asyncio
async def test_bare_mode_skips_recent_events_filtering():
    events = [_event(i) for i in range(5)]
    context = await _assemble(
        bare_mode=True,
        recent_events=events,
        recent_events_limit=2,
    )

    # bare mode uses all events, not just the last `recent_events_limit`
    assert context.metadata["event_count"] == 5
    for i in range(5):
        assert f"Message {i}" in context.user_prompt


@pytest.mark.asyncio
async def test_bare_mode_metadata_marks_bare():
    context = await _assemble(bare_mode=True)

    assert context.metadata["bare_mode"] is True
    assert context.metadata["coaching_count"] == 0


@pytest.mark.asyncio
async def test_bare_mode_false_produces_full_context():
    context = await _assemble(bare_mode=False)

    assert "--- INTELLIGENCE SUMMARY ---" in context.user_prompt
    assert "--- ANALYST DIVERGENCES ---" in context.user_prompt
    assert "--- COACHING FROM OPERATOR ---" in context.user_prompt
    assert "bare_mode" not in context.metadata
