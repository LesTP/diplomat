"""Unit tests for coalition scoring in game_environment.py.

Covers _find_coalition_value (sorted-set match / miss / empty-or-missing) and
_resolve_deal_scores across every scoring path:
  - AB / AC / BC partial coalition with matching coalition_values
  - Grand coalition (members == all factions) uses faction_score(), not coalition_values
  - Unknown coalition subset -> no-deal (partial_coalition_without_coalition_values)
  - Below-BATNA deal -> no-deal (deal_below_batna_for_some_faction)
  - deal_reached with no agreed_outcomes -> no-deal (deal_reached_without_agreed_outcomes)
  - deal_reached False -> all BATNA

Fixture: scenarios/three_party_coalition_v1/scenario_analysis.json
  coalition_values: a+b->{a:6,b:7}, a+c->{a:5,c:6}, b+c->{b:4,c:3}, grand->{a:7,b:6,c:5}
  BATNAs: a=0, b=0, c=0

No live LLM — functions are imported directly from game_environment.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.self_play.game_environment import _find_coalition_value, _resolve_deal_scores


_FIXTURE = Path(__file__).parent.parent.parent / "scenarios" / "three_party_coalition_v1" / "scenario_analysis.json"


@pytest.fixture
def analysis() -> dict:
    return json.loads(_FIXTURE.read_text())


# ---------------------------------------------------------------------------
# _find_coalition_value
# ---------------------------------------------------------------------------


class TestFindCoalitionValue:
    def test_ab_match(self, analysis: dict) -> None:
        entry = _find_coalition_value(analysis, ["a", "b"])
        assert entry is not None
        assert entry["values"] == {"a": 6, "b": 7}

    def test_ab_match_reversed_order(self, analysis: dict) -> None:
        # Sorted-set equality: input order doesn't matter.
        entry = _find_coalition_value(analysis, ["b", "a"])
        assert entry is not None
        assert entry["values"] == {"a": 6, "b": 7}

    def test_ac_match(self, analysis: dict) -> None:
        entry = _find_coalition_value(analysis, ["a", "c"])
        assert entry is not None
        assert entry["values"] == {"a": 5, "c": 6}

    def test_bc_match(self, analysis: dict) -> None:
        entry = _find_coalition_value(analysis, ["b", "c"])
        assert entry is not None
        assert entry["values"] == {"b": 4, "c": 3}

    def test_grand_coalition_match(self, analysis: dict) -> None:
        entry = _find_coalition_value(analysis, ["a", "b", "c"])
        assert entry is not None
        assert entry["values"] == {"a": 7, "b": 6, "c": 5}

    def test_unknown_subset_returns_none(self, analysis: dict) -> None:
        assert _find_coalition_value(analysis, ["x", "y"]) is None

    def test_single_member_not_in_fixture_returns_none(self, analysis: dict) -> None:
        assert _find_coalition_value(analysis, ["a"]) is None

    def test_empty_coalition_values_list(self) -> None:
        assert _find_coalition_value({"coalition_values": []}, ["a", "b"]) is None

    def test_missing_coalition_values_key(self) -> None:
        assert _find_coalition_value({}, ["a", "b"]) is None


# ---------------------------------------------------------------------------
# _resolve_deal_scores
# ---------------------------------------------------------------------------


class TestResolveDealScores:

    # --- Partial coalition with matching coalition_values ---

    def test_ab_coalition_members_get_values_excluded_gets_batna(self, analysis: dict) -> None:
        score_data = {
            "deal_reached": True,
            "agreed_outcomes": {"coalition_formation": "a_b"},
            "coalition_members": ["a", "b"],
        }
        result = _resolve_deal_scores(analysis, score_data)
        assert result["deal_reached"] is True
        assert "no_deal_reason" not in result
        assert result["faction_scores"]["a"]["points"] == 6.0
        assert result["faction_scores"]["b"]["points"] == 7.0
        assert result["faction_scores"]["c"]["points"] == 0.0  # excluded -> BATNA
        assert result["faction_scores"]["a"]["batna"] == 0.0
        assert result["faction_scores"]["b"]["batna"] == 0.0
        assert result["faction_scores"]["c"]["batna"] == 0.0

    def test_ac_coalition(self, analysis: dict) -> None:
        score_data = {
            "deal_reached": True,
            "agreed_outcomes": {"coalition_formation": "a_c"},
            "coalition_members": ["a", "c"],
        }
        result = _resolve_deal_scores(analysis, score_data)
        assert result["deal_reached"] is True
        assert "no_deal_reason" not in result
        assert result["faction_scores"]["a"]["points"] == 5.0
        assert result["faction_scores"]["c"]["points"] == 6.0
        assert result["faction_scores"]["b"]["points"] == 0.0  # excluded -> BATNA

    def test_bc_coalition(self, analysis: dict) -> None:
        score_data = {
            "deal_reached": True,
            "agreed_outcomes": {"coalition_formation": "b_c"},
            "coalition_members": ["b", "c"],
        }
        result = _resolve_deal_scores(analysis, score_data)
        assert result["deal_reached"] is True
        assert "no_deal_reason" not in result
        assert result["faction_scores"]["b"]["points"] == 4.0
        assert result["faction_scores"]["c"]["points"] == 3.0
        assert result["faction_scores"]["a"]["points"] == 0.0  # excluded -> BATNA

    # --- Grand coalition path ---

    def test_grand_coalition_uses_faction_score_not_coalition_values(self, analysis: dict) -> None:
        # Grand coalition (members == all factions) => is_partial is False =>
        # full-agreement path: faction_score() on agreed_outcomes.
        # coalition_values entry {a:7,b:6,c:5} is NOT used here.
        score_data = {
            "deal_reached": True,
            "agreed_outcomes": {"coalition_formation": "a_b_c"},
            "coalition_members": ["a", "b", "c"],
        }
        result = _resolve_deal_scores(analysis, score_data)
        assert result["deal_reached"] is True
        assert "no_deal_reason" not in result
        # scoring["a"]["coalition_formation"]["a_b_c"] = 10  (not 7 from coalition_values)
        assert result["faction_scores"]["a"]["points"] == 10.0
        # scoring["b"]["coalition_formation"]["a_b_c"] = 7
        assert result["faction_scores"]["b"]["points"] == 7.0
        # scoring["c"]["coalition_formation"]["a_b_c"] = 7
        assert result["faction_scores"]["c"]["points"] == 7.0

    def test_full_deal_no_coalition_members_uses_faction_score(self, analysis: dict) -> None:
        # Empty coalition_members => not partial => faction_score() path.
        score_data = {
            "deal_reached": True,
            "agreed_outcomes": {"coalition_formation": "a_b"},
            "coalition_members": [],
        }
        result = _resolve_deal_scores(analysis, score_data)
        assert result["deal_reached"] is True
        assert "no_deal_reason" not in result
        # scoring["a"]["coalition_formation"]["a_b"] = 9
        assert result["faction_scores"]["a"]["points"] == 9.0
        # scoring["b"]["coalition_formation"]["a_b"] = 10
        assert result["faction_scores"]["b"]["points"] == 10.0
        # scoring["c"]["coalition_formation"]["a_b"] = 1
        assert result["faction_scores"]["c"]["points"] == 1.0

    # --- No-deal: partial coalition without matching coalition_values ---

    def test_unknown_coalition_subset_becomes_no_deal(self, analysis: dict) -> None:
        # Single-member coalition has no entry in coalition_values -> no-deal.
        score_data = {
            "deal_reached": True,
            "agreed_outcomes": {"coalition_formation": "a_b"},
            "coalition_members": ["a"],
        }
        result = _resolve_deal_scores(analysis, score_data)
        assert result["deal_reached"] is False
        assert result["no_deal_reason"] == "partial_coalition_without_coalition_values"
        assert result["faction_scores"]["a"]["points"] == 0.0
        assert result["faction_scores"]["b"]["points"] == 0.0
        assert result["faction_scores"]["c"]["points"] == 0.0

    # --- No-deal: below BATNA ---

    def test_below_batna_coalition_becomes_no_deal(self) -> None:
        # A coalition member's value below its BATNA triggers rationality rejection.
        below_batna_analysis = {
            "factions": ["a", "b", "c"],
            "batna": {"a": 5, "b": 2, "c": 0},
            "coalition_values": [
                # a gets 3, which is below a's BATNA of 5
                {"members": ["a", "b"], "values": {"a": 3, "b": 8}},
            ],
            "issues": [{"name": "x", "outcomes": ["y"]}],
            "scoring": {
                "a": {"x": {"y": 3}},
                "b": {"x": {"y": 8}},
                "c": {"x": {"y": 0}},
            },
        }
        score_data = {
            "deal_reached": True,
            "agreed_outcomes": {"x": "y"},
            "coalition_members": ["a", "b"],
        }
        result = _resolve_deal_scores(below_batna_analysis, score_data)
        assert result["deal_reached"] is False
        assert result["no_deal_reason"] == "deal_below_batna_for_some_faction"
        # All factions revert to BATNA
        assert result["faction_scores"]["a"]["points"] == 5.0
        assert result["faction_scores"]["b"]["points"] == 2.0
        assert result["faction_scores"]["c"]["points"] == 0.0

    # --- No-deal: deal_reached without agreed_outcomes ---

    def test_deal_reached_without_agreed_outcomes_normalized_to_no_deal(self, analysis: dict) -> None:
        score_data = {
            "deal_reached": True,
            "agreed_outcomes": {},
            "coalition_members": [],
        }
        result = _resolve_deal_scores(analysis, score_data)
        assert result["deal_reached"] is False
        assert result["no_deal_reason"] == "deal_reached_without_agreed_outcomes"
        assert result["faction_scores"]["a"]["points"] == 0.0
        assert result["faction_scores"]["b"]["points"] == 0.0
        assert result["faction_scores"]["c"]["points"] == 0.0

    def test_deal_reached_none_agreed_outcomes_normalized_to_no_deal(self, analysis: dict) -> None:
        score_data = {
            "deal_reached": True,
            "agreed_outcomes": None,
            "coalition_members": [],
        }
        result = _resolve_deal_scores(analysis, score_data)
        assert result["deal_reached"] is False
        assert result["no_deal_reason"] == "deal_reached_without_agreed_outcomes"

    # --- No-deal: deal_reached False ---

    def test_deal_reached_false_gives_all_batna(self, analysis: dict) -> None:
        score_data = {
            "deal_reached": False,
            "agreed_outcomes": {},
            "coalition_members": [],
        }
        result = _resolve_deal_scores(analysis, score_data)
        assert result["deal_reached"] is False
        assert result["faction_scores"]["a"]["points"] == 0.0
        assert result["faction_scores"]["b"]["points"] == 0.0
        assert result["faction_scores"]["c"]["points"] == 0.0
        assert result["faction_scores"]["a"]["batna"] == 0.0
