from __future__ import annotations

from modules.review_gate.chunking import CONTINUATION_PREFIX, chunk_text


def test_chunk_text_returns_single_chunk_for_short_text():
    text = "Short review message."

    assert chunk_text(text, 80) == [text]


def test_chunk_text_splits_on_paragraph_boundaries():
    text = "Alpha paragraph.\n\nBeta paragraph."

    chunks = chunk_text(text, 25)

    assert len(chunks) >= 2
    assert chunks[0] == "Alpha paragraph.\n\n"
    assert all(
        chunk.startswith(CONTINUATION_PREFIX) for chunk in chunks[1:]
    )
    assert chunks[0] + "".join(
        chunk[len(CONTINUATION_PREFIX) :] for chunk in chunks[1:]
    ) == text


def test_chunk_text_falls_back_to_line_splitting():
    text = "Alpha line that is long\nBeta line that is also long"

    chunks = chunk_text(text, 25)

    assert len(chunks) >= 2
    assert all(
        chunk.startswith(CONTINUATION_PREFIX) for chunk in chunks[1:]
    )
    assert chunks[0] + "".join(
        chunk[len(CONTINUATION_PREFIX) :] for chunk in chunks[1:]
    ) == text


def test_chunk_text_falls_back_to_character_splitting():
    text = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"

    chunks = chunk_text(text, 20)

    assert len(chunks) >= 2
    assert all(chunk.startswith(CONTINUATION_PREFIX) for chunk in chunks[1:])
    assert "".join(
        [chunks[0]] + [chunk[len(CONTINUATION_PREFIX) :] for chunk in chunks[1:]]
    ) == text


def test_chunk_text_adds_continuation_marker_to_every_followup_chunk():
    text = "First paragraph is long enough to split.\n\nSecond paragraph is also long enough to split."

    chunks = chunk_text(text, 24)

    assert len(chunks) >= 2
    assert all(
        chunk.startswith(CONTINUATION_PREFIX) for chunk in chunks[1:]
    )


def test_chunk_text_round_trips_original_content():
    text = (
        "Alpha paragraph with a few words.\n\n"
        "Beta paragraph with a very long line that needs splitting into smaller pieces."
    )

    chunks = chunk_text(text, 28)
    restored = chunks[0] + "".join(
        chunk[len(CONTINUATION_PREFIX) :] for chunk in chunks[1:]
    )

    assert restored == text
