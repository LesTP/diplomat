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
