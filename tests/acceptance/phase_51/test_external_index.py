"""Phase 51, Item 2 — External capability-index lookup.

Contract: tests/self_play/external_index.py provides a static offline lookup
table pairing every Paper-1 roster model with its LMArena Elo and MMLU scores.
The lookup() function mirrors toolkit's normalize_model_name resolution
(exact → date-suffix stripped → None) so date-versioned model IDs from the
API resolve to the same entry as the canonical name.
"""

from __future__ import annotations

import pytest

# All tests in this file are expected to fail (red) until external_index.py
# is implemented. ImportError at collection time would swallow all test names,
# so we gate on import availability and xfail individually.
try:
    from tests.self_play.external_index import (
        EXTERNAL_INDEX,
        ExternalIndex,
        lookup,
    )
    _AVAILABLE = True
except ImportError:
    _AVAILABLE = False
    # Stubs so the rest of the file parses cleanly.
    lookup = lambda m: None  # noqa: E731
    EXTERNAL_INDEX = {}

    class ExternalIndex:  # type: ignore[no-redef]
        pass


_need_impl = pytest.mark.xfail(
    not _AVAILABLE,
    reason="tests/self_play/external_index.py not implemented yet",
    strict=False,
)

# Paper-1 roster of models that must be covered.
PAPER_ROSTER = [
    "gpt-4.1-nano",
    "gpt-5.4-mini",
    "gpt-5.5",
    "claude-haiku-4-5",
    "claude-sonnet-4-6",
    "claude-opus-4",
    "deepseek-v3",
    "deepseek-r1",
]


@_need_impl
class TestRosterCoverage:
    """AC 1 — every Paper-1 roster model resolves via lookup()."""

    @pytest.mark.parametrize("model", PAPER_ROSTER)
    def test_roster_model_resolves(self, model: str) -> None:
        """lookup(model) must return a non-None ExternalIndex for every roster entry."""
        result = lookup(model)
        assert result is not None, f"lookup('{model}') returned None — model not in index"

    @pytest.mark.parametrize("model", PAPER_ROSTER)
    def test_roster_model_resolves_with_openai_date_suffix(self, model: str) -> None:
        """Date-suffixed OpenAI variants (YYYY-MM-DD) must resolve to the same entry."""
        dated = f"{model}-2026-01-15"
        result = lookup(dated)
        canonical = lookup(model)
        if canonical is None:
            pytest.skip(f"canonical lookup('{model}') is None — covered by test_roster_model_resolves")
        assert result is not None, (
            f"lookup('{dated}') returned None; expected same entry as '{model}'"
        )
        assert result.lmarena_elo == canonical.lmarena_elo

    @pytest.mark.parametrize("model", PAPER_ROSTER)
    def test_roster_model_resolves_with_anthropic_date_suffix(self, model: str) -> None:
        """Packed Anthropic date suffixes (YYYYMMDD) must resolve to the same entry."""
        dated = f"{model}-20260115"
        result = lookup(dated)
        canonical = lookup(model)
        if canonical is None:
            pytest.skip(f"canonical lookup('{model}') is None — covered by test_roster_model_resolves")
        assert result is not None, (
            f"lookup('{dated}') returned None; expected same entry as '{model}'"
        )
        assert result.lmarena_elo == canonical.lmarena_elo


@_need_impl
class TestIndexStructure:
    """AC 2 — every entry carries both indices in sane ranges with non-empty provenance."""

    @pytest.mark.parametrize("model", PAPER_ROSTER)
    def test_entry_has_elo_in_sane_range(self, model: str) -> None:
        """LMArena Elo must be in [800, 1600] — values outside are almost certainly wrong."""
        entry = lookup(model)
        if entry is None:
            pytest.xfail(f"lookup('{model}') returned None")
        assert 800 <= entry.lmarena_elo <= 1600, (
            f"'{model}' lmarena_elo={entry.lmarena_elo} outside sane range [800, 1600]"
        )

    @pytest.mark.parametrize("model", PAPER_ROSTER)
    def test_entry_has_mmlu_in_sane_range(self, model: str) -> None:
        """MMLU score must be in [0.0, 1.0]."""
        entry = lookup(model)
        if entry is None:
            pytest.xfail(f"lookup('{model}') returned None")
        assert 0.0 <= entry.mmlu <= 1.0, (
            f"'{model}' mmlu={entry.mmlu} outside [0.0, 1.0]"
        )

    @pytest.mark.parametrize("model", PAPER_ROSTER)
    def test_entry_has_nonempty_source(self, model: str) -> None:
        """source field must be non-empty (provenance is mandatory)."""
        entry = lookup(model)
        if entry is None:
            pytest.xfail(f"lookup('{model}') returned None")
        assert entry.source and entry.source.strip(), (
            f"'{model}' has empty or blank source field"
        )

    @pytest.mark.parametrize("model", PAPER_ROSTER)
    def test_entry_has_nonempty_as_of(self, model: str) -> None:
        """as_of field must be non-empty (provenance is mandatory)."""
        entry = lookup(model)
        if entry is None:
            pytest.xfail(f"lookup('{model}') returned None")
        assert entry.as_of and entry.as_of.strip(), (
            f"'{model}' has empty or blank as_of field"
        )

    def test_external_index_is_frozen_dataclass(self) -> None:
        """ExternalIndex must be a frozen dataclass (immutable)."""
        entry = lookup(PAPER_ROSTER[0])
        if entry is None:
            pytest.xfail("lookup returned None — roster coverage issue")
        with pytest.raises((AttributeError, TypeError)):
            entry.lmarena_elo = 9999.0  # type: ignore[misc]


@_need_impl
class TestUnknownModelFallback:
    """AC 3 — unknown model returns None without crashing."""

    def test_unknown_model_returns_none(self) -> None:
        """lookup() must return None (not raise) for a model not in the index."""
        result = lookup("unknown-model-xyz-9999")
        assert result is None

    def test_empty_string_returns_none(self) -> None:
        """lookup() must handle an empty string gracefully."""
        result = lookup("")
        assert result is None

    def test_completely_garbled_id_returns_none(self) -> None:
        """lookup() must handle garbled input without raising."""
        result = lookup("!!!not-a-model-$$$")
        assert result is None
