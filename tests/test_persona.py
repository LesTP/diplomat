from __future__ import annotations

import os

import pytest

from modules.persona import CoachingContext, FileBasedPersona


def test_public_exports_include_persona_types():
    import modules.persona as persona

    assert persona.CoachingContext is CoachingContext
    assert persona.FileBasedPersona is FileBasedPersona


@pytest.mark.asyncio
async def test_get_base_prompt_raises_file_not_found(tmp_path):
    persona = FileBasedPersona(tmp_path / "missing_prompt.txt")

    with pytest.raises(FileNotFoundError):
        await persona.get_base_prompt()


@pytest.mark.asyncio
async def test_get_base_prompt_reads_file(tmp_path):
    prompt_path = tmp_path / "faction_prompt.txt"
    prompt_path.write_text("Faction identity\nGoal: survive\n", encoding="utf-8")

    assert await FileBasedPersona(prompt_path).get_base_prompt() == (
        "Faction identity\nGoal: survive"
    )


@pytest.mark.asyncio
async def test_get_base_prompt_reloads_when_mtime_changes(tmp_path):
    prompt_path = tmp_path / "faction_prompt.txt"
    prompt_path.write_text("Initial identity\n", encoding="utf-8")
    persona = FileBasedPersona(prompt_path)

    assert await persona.get_base_prompt() == "Initial identity"

    prompt_path.write_text("Updated identity\n", encoding="utf-8")
    stat_result = prompt_path.stat()
    os.utime(prompt_path, ns=(stat_result.st_atime_ns, stat_result.st_mtime_ns + 1))

    assert await persona.get_base_prompt() == "Updated identity"


@pytest.mark.asyncio
async def test_get_base_prompt_uses_cache_when_mtime_unchanged(tmp_path):
    prompt_path = tmp_path / "faction_prompt.txt"
    prompt_path.write_text("Cached identity\n", encoding="utf-8")
    stat_result = prompt_path.stat()
    persona = FileBasedPersona(prompt_path)

    assert await persona.get_base_prompt() == "Cached identity"

    prompt_path.write_text("Changed without mtime\n", encoding="utf-8")
    os.utime(prompt_path, ns=(stat_result.st_atime_ns, stat_result.st_mtime_ns))

    assert await persona.get_base_prompt() == "Cached identity"


@pytest.mark.asyncio
async def test_get_base_prompt_strips_current_round_context_section(tmp_path):
    prompt_path = tmp_path / "faction_prompt.txt"
    prompt_path.write_text(
        """
You are England.

## CURRENT ROUND CONTEXT

Round: 3
This section should not be part of the stable persona.
""".strip(),
        encoding="utf-8",
    )

    assert await FileBasedPersona(prompt_path).get_base_prompt() == "You are England."


@pytest.mark.asyncio
async def test_build_round_context_formats_all_fields(tmp_path):
    persona = FileBasedPersona(tmp_path / "unused.txt")

    context = await persona.build_round_context(
        round_number=4,
        rounds_remaining=6,
        coaching_context=CoachingContext(
            priorities=["Secure Beta alliance", "Hold the center"],
            constraints=["Do not promise territory"],
            watch_items=["Delta credibility dropping"],
            tone_notes=["More assertive this round"],
        ),
    )

    assert context == "\n".join(
        [
            "## CURRENT ROUND CONTEXT",
            "",
            "Round: 4",
            "Rounds remaining: 6",
            "",
            "### Priorities",
            "- Secure Beta alliance",
            "- Hold the center",
            "",
            "### Constraints",
            "- Do not promise territory",
            "",
            "### Watch Items",
            "- Delta credibility dropping",
            "",
            "### Tone Notes",
            "- More assertive this round",
        ]
    )


@pytest.mark.asyncio
async def test_build_round_context_formats_empty_fields(tmp_path):
    persona = FileBasedPersona(tmp_path / "unused.txt")

    context = await persona.build_round_context(
        round_number=1,
        rounds_remaining=9,
        coaching_context=CoachingContext(
            priorities=[],
            constraints=[],
            watch_items=[],
            tone_notes=[],
        ),
    )

    assert "### Priorities\n- (none)" in context
    assert "### Constraints\n- (none)" in context
    assert "### Watch Items\n- (none)" in context
    assert "### Tone Notes\n- (none)" in context


@pytest.mark.asyncio
async def test_build_round_context_formats_unknown_rounds_remaining(tmp_path):
    persona = FileBasedPersona(tmp_path / "unused.txt")

    context = await persona.build_round_context(
        round_number=2,
        rounds_remaining=None,
        coaching_context=CoachingContext(
            priorities=[],
            constraints=[],
            watch_items=[],
            tone_notes=[],
        ),
    )

    assert "Rounds remaining: unknown" in context


@pytest.mark.asyncio
async def test_build_round_context_with_total_rounds_renders_x_of_y(tmp_path):
    persona = FileBasedPersona(tmp_path / "unused.txt")

    context = await persona.build_round_context(
        round_number=2,
        rounds_remaining=None,
        coaching_context=CoachingContext(
            priorities=[], constraints=[], watch_items=[], tone_notes=[]
        ),
        total_rounds=4,
    )

    assert "Round: 2 of 4" in context
    assert "Rounds remaining: 2" in context  # derived from total_rounds
    assert "FINAL ROUND" not in context
    assert "PENULTIMATE ROUND" not in context


@pytest.mark.asyncio
async def test_build_round_context_total_rounds_overrides_rounds_remaining(tmp_path):
    """When both are given, total_rounds wins (authoritative source)."""
    persona = FileBasedPersona(tmp_path / "unused.txt")

    context = await persona.build_round_context(
        round_number=2,
        rounds_remaining=99,  # stale/wrong
        coaching_context=CoachingContext(
            priorities=[], constraints=[], watch_items=[], tone_notes=[]
        ),
        total_rounds=4,
    )

    assert "Rounds remaining: 2" in context
    assert "Rounds remaining: 99" not in context


@pytest.mark.asyncio
async def test_build_round_context_penultimate_round_emits_warning(tmp_path):
    persona = FileBasedPersona(tmp_path / "unused.txt")

    # Via rounds_remaining directly.
    context_rr = await persona.build_round_context(
        round_number=3,
        rounds_remaining=1,
        coaching_context=CoachingContext(
            priorities=[], constraints=[], watch_items=[], tone_notes=[]
        ),
    )
    assert "### PENULTIMATE ROUND" in context_rr
    assert "Only one round remains after this" in context_rr
    assert "FINAL ROUND" not in context_rr

    # Via total_rounds derivation (round 3 of 4 → 1 remaining).
    context_tr = await persona.build_round_context(
        round_number=3,
        rounds_remaining=None,
        coaching_context=CoachingContext(
            priorities=[], constraints=[], watch_items=[], tone_notes=[]
        ),
        total_rounds=4,
    )
    assert "### PENULTIMATE ROUND" in context_tr


@pytest.mark.asyncio
async def test_build_round_context_final_round_emits_warning(tmp_path):
    persona = FileBasedPersona(tmp_path / "unused.txt")

    # Via rounds_remaining directly.
    context_rr = await persona.build_round_context(
        round_number=4,
        rounds_remaining=0,
        coaching_context=CoachingContext(
            priorities=[], constraints=[], watch_items=[], tone_notes=[]
        ),
        base_batna=11,
        current_best_offer=18,
    )
    assert "### FINAL ROUND" in context_rr
    assert (
        "No deal = 11 pts (your BATNA); current best offer = 18 pts; walking away costs you 7 pts."
        in context_rr
    )
    assert "No deal = 11 points (your BATNA)." in context_rr
    assert "Current best offer = 18 points." in context_rr
    assert "Walking away costs you 7 points." in context_rr
    assert "PENULTIMATE ROUND" not in context_rr

    # Via total_rounds derivation (round 4 of 4 → 0 remaining).
    context_tr = await persona.build_round_context(
        round_number=4,
        rounds_remaining=None,
        coaching_context=CoachingContext(
            priorities=[], constraints=[], watch_items=[], tone_notes=[]
        ),
        total_rounds=4,
        base_batna=11,
        current_best_offer=18,
    )
    assert "### FINAL ROUND" in context_tr
    assert (
        "No deal = 11 pts (your BATNA); current best offer = 18 pts; walking away costs you 7 pts."
        in context_tr
    )


@pytest.mark.asyncio
async def test_build_round_context_no_endgame_in_early_rounds(tmp_path):
    """Endgame reminders must NOT fire in early rounds (rounds_remaining >= 2)."""
    persona = FileBasedPersona(tmp_path / "unused.txt")

    for remaining in (2, 5, 10):
        context = await persona.build_round_context(
            round_number=1,
            rounds_remaining=remaining,
            coaching_context=CoachingContext(
                priorities=[], constraints=[], watch_items=[], tone_notes=[]
            ),
        )
        assert "FINAL ROUND" not in context
        assert "PENULTIMATE ROUND" not in context


@pytest.mark.asyncio
async def test_build_round_context_renders_pressure_and_deadlines(tmp_path):
    persona = FileBasedPersona(tmp_path / "unused.txt")

    context = await persona.build_round_context(
        round_number=4,
        rounds_remaining=None,
        coaching_context=CoachingContext(
            priorities=[], constraints=[], watch_items=[], tone_notes=[]
        ),
        total_rounds=4,
        pressure={
            "round_cost_decay": 1.5,
            "asymmetric_clocks": {"alpha": 4, "beta": 2, "gamma": 3},
            "penalty_floor_offset": 2.0,
        },
        priority_collision="soft",
        faction_id="alpha",
        base_batna=18,
        current_best_offer=24,
    )

    assert "### Pressure" in context
    assert "Round cost decay: 1.5 points per round" in context
    assert "Penalty floor offset: 2 points" in context
    assert "### FINAL ROUND" in context
    assert "No deal = 18 points (your BATNA)." in context
    assert "Current best offer = 24 points." in context
    assert "Walking away costs you 6 points." in context
    assert "Effective BATNA this round: 11.5 points" in context
    assert "### Opponent Deadlines" in context
    assert "- beta: round 2" in context
    assert "- gamma: round 3" in context
