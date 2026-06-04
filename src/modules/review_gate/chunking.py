from __future__ import annotations

CONTINUATION_PREFIX = "[continued ...]\n\n"


def chunk_text(text: str, max_chars: int) -> list[str]:
    if max_chars <= len(CONTINUATION_PREFIX):
        raise ValueError("max_chars must exceed the continuation prefix length")
    if len(text) <= max_chars:
        return [text]

    first_chunks = _split_segment(text, max_chars, "")
    if len(first_chunks) <= 1:
        return first_chunks

    first_chunk = first_chunks[0]
    remainder = text[len(first_chunk) :]
    tail_limit = max_chars - len(CONTINUATION_PREFIX)
    tail_chunks = _split_segment(remainder, tail_limit, "")
    return [first_chunk] + [CONTINUATION_PREFIX + chunk for chunk in tail_chunks]


def _split_segment(text: str, max_chars: int, trailing_sep: str) -> list[str]:
    if len(text) + len(trailing_sep) <= max_chars:
        return [text + trailing_sep]

    if "\n\n" in text:
        pieces: list[str] = []
        paragraphs = text.split("\n\n")
        for index, paragraph in enumerate(paragraphs):
            sep = "\n\n" if index < len(paragraphs) - 1 else trailing_sep
            pieces.extend(_split_segment(paragraph, max_chars, sep))
        return _pack_pieces(pieces, max_chars)

    if "\n" in text:
        pieces = []
        lines = text.split("\n")
        for index, line in enumerate(lines):
            sep = "\n" if index < len(lines) - 1 else trailing_sep
            pieces.extend(_split_segment(line, max_chars, sep))
        return _pack_pieces(pieces, max_chars)

    if len(trailing_sep) >= max_chars:
        raise ValueError("max_chars is too small for the requested separator")

    content_limit = max_chars - len(trailing_sep)
    pieces = [text[i : i + content_limit] for i in range(0, len(text), content_limit)]
    pieces[-1] += trailing_sep
    return pieces


def _pack_pieces(pieces: list[str], max_chars: int) -> list[str]:
    packed: list[str] = []
    current = ""
    for piece in pieces:
        if not piece:
            continue
        if current and len(current) + len(piece) <= max_chars:
            current += piece
            continue
        if current:
            packed.append(current)
        current = piece
    if current:
        packed.append(current)
    return packed
