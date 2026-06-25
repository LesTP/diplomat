"""Tests for scenario_narrative.py — apply_relabel + assert_structure_preserved.

All tests are deterministic (no LLM).  Standalone: stdlib + scenario_authoring
sibling imports only.
"""

from __future__ import annotations

import copy

import pytest

from scenario_authoring.scenario_narrative import (
    apply_relabel,
    assert_structure_preserved,
)


# ---------------------------------------------------------------------------
# Minimal fixture — two factions, two issues, two outcomes each, plus coalition
# ---------------------------------------------------------------------------

_BASE_ANALYSIS = {
    "factions": ["alpha", "beta"],
    "issues": [
        {
            "name": "trade",
            "outcomes": ["open", "closed"],
            "description": "Trade policy",
        },
        {
            "name": "security",
            "outcomes": ["allied", "neutral"],
            "description": "Security stance",
        },
    ],
    "scoring": {
        "alpha": {
            "trade": {"open": 8, "closed": 2},
            "security": {"allied": 6, "neutral": 3},
        },
        "beta": {
            "trade": {"open": 3, "closed": 7},
            "security": {"allied": 5, "neutral": 4},
        },
    },
    "batna": {"alpha": 5, "beta": 4},
    "deception_tactics": {"alpha": "tactic-a", "beta": "tactic-b"},
    "logrolling": ["alpha trades open for allied"],
    "game_mode": "mixed",
    "pressure": {
        "round_cost_decay": 1.0,
        "asymmetric_clocks": {"alpha": 3, "beta": 5},
        "penalty_floor_offset": 0.0,
    },
    "pressure_profile": {"time_pressure": "medium", "external_shock": "low"},
    "coalition_values": [
        {
            "members": ["alpha"],
            "values": {"alpha": 10},
        }
    ],
}

_IDENTITY_MAP: dict[str, dict[str, str]] = {
    "factions": {"alpha": "alpha", "beta": "beta"},
    "issues": {"trade": "trade", "security": "security"},
    "outcomes": {"open": "open", "closed": "closed", "allied": "allied", "neutral": "neutral"},
}

_THEMED_MAP: dict[str, dict[str, str]] = {
    "factions": {"alpha": "EmpireOfDawn", "beta": "FreeStates"},
    "issues": {"trade": "CommerceAct", "security": "DefensePact"},
    "outcomes": {
        "open": "FreeMarket",
        "closed": "Protectionist",
        "allied": "MutualDefense",
        "neutral": "NonAlignment",
    },
}


# ---------------------------------------------------------------------------
# Helper to apply themed relabel and return (original, relabeled)
# ---------------------------------------------------------------------------

def _themed():
    src = copy.deepcopy(_BASE_ANALYSIS)
    res = apply_relabel(src, _THEMED_MAP)
    return src, res


# ---------------------------------------------------------------------------
# apply_relabel — identity
# ---------------------------------------------------------------------------

class TestApplyRelabelIdentity:
    def test_factions_unchanged(self) -> None:
        src = copy.deepcopy(_BASE_ANALYSIS)
        result = apply_relabel(src, _IDENTITY_MAP)
        assert result["factions"] == ["alpha", "beta"]

    def test_issue_names_unchanged(self) -> None:
        src = copy.deepcopy(_BASE_ANALYSIS)
        result = apply_relabel(src, _IDENTITY_MAP)
        assert [i["name"] for i in result["issues"]] == ["trade", "security"]

    def test_outcome_names_unchanged(self) -> None:
        src = copy.deepcopy(_BASE_ANALYSIS)
        result = apply_relabel(src, _IDENTITY_MAP)
        assert result["issues"][0]["outcomes"] == ["open", "closed"]
        assert result["issues"][1]["outcomes"] == ["allied", "neutral"]

    def test_scores_unchanged(self) -> None:
        src = copy.deepcopy(_BASE_ANALYSIS)
        result = apply_relabel(src, _IDENTITY_MAP)
        assert result["scoring"]["alpha"]["trade"]["open"] == 8
        assert result["scoring"]["beta"]["security"]["neutral"] == 4

    def test_batna_unchanged(self) -> None:
        src = copy.deepcopy(_BASE_ANALYSIS)
        result = apply_relabel(src, _IDENTITY_MAP)
        assert result["batna"] == {"alpha": 5, "beta": 4}

    def test_coalition_values_unchanged(self) -> None:
        src = copy.deepcopy(_BASE_ANALYSIS)
        result = apply_relabel(src, _IDENTITY_MAP)
        cv = result["coalition_values"]
        assert len(cv) == 1
        assert cv[0]["members"] == ["alpha"]
        assert cv[0]["values"] == {"alpha": 10}

    def test_pressure_clocks_unchanged(self) -> None:
        src = copy.deepcopy(_BASE_ANALYSIS)
        result = apply_relabel(src, _IDENTITY_MAP)
        assert result["pressure"]["asymmetric_clocks"] == {"alpha": 3, "beta": 5}


# ---------------------------------------------------------------------------
# apply_relabel — themed relabel
# ---------------------------------------------------------------------------

class TestApplyRelabelThemed:
    def test_faction_ids_relabeled(self) -> None:
        _, res = _themed()
        assert res["factions"] == ["EmpireOfDawn", "FreeStates"]

    def test_issue_names_relabeled(self) -> None:
        _, res = _themed()
        names = [i["name"] for i in res["issues"]]
        assert names == ["CommerceAct", "DefensePact"]

    def test_outcome_names_relabeled(self) -> None:
        _, res = _themed()
        assert res["issues"][0]["outcomes"] == ["FreeMarket", "Protectionist"]
        assert res["issues"][1]["outcomes"] == ["MutualDefense", "NonAlignment"]

    def test_scores_preserved_under_relabel(self) -> None:
        _, res = _themed()
        assert res["scoring"]["EmpireOfDawn"]["CommerceAct"]["FreeMarket"] == 8
        assert res["scoring"]["EmpireOfDawn"]["CommerceAct"]["Protectionist"] == 2
        assert res["scoring"]["FreeStates"]["DefensePact"]["NonAlignment"] == 4

    def test_batna_preserved_under_relabel(self) -> None:
        _, res = _themed()
        assert res["batna"] == {"EmpireOfDawn": 5, "FreeStates": 4}

    def test_coalition_values_members_relabeled(self) -> None:
        _, res = _themed()
        assert res["coalition_values"][0]["members"] == ["EmpireOfDawn"]

    def test_coalition_values_numeric_preserved(self) -> None:
        _, res = _themed()
        assert res["coalition_values"][0]["values"] == {"EmpireOfDawn": 10}

    def test_pressure_clocks_faction_relabeled(self) -> None:
        _, res = _themed()
        assert res["pressure"]["asymmetric_clocks"] == {
            "EmpireOfDawn": 3,
            "FreeStates": 5,
        }

    def test_non_identifier_fields_copied(self) -> None:
        _, res = _themed()
        assert res["game_mode"] == "mixed"
        assert res["pressure"]["round_cost_decay"] == 1.0
        assert res["pressure_profile"]["time_pressure"] == "medium"


# ---------------------------------------------------------------------------
# assert_structure_preserved — passes on valid relabel
# ---------------------------------------------------------------------------

class TestAssertStructurePreservedPasses:
    def test_identity_passes(self) -> None:
        src = copy.deepcopy(_BASE_ANALYSIS)
        res = apply_relabel(src, _IDENTITY_MAP)
        assert_structure_preserved(src, res, _IDENTITY_MAP)  # must not raise

    def test_themed_passes(self) -> None:
        src, res = _themed()
        assert_structure_preserved(src, res, _THEMED_MAP)  # must not raise


# ---------------------------------------------------------------------------
# assert_structure_preserved — rejects numeric drift
# ---------------------------------------------------------------------------

class TestAssertStructurePreservedRejectsNumericDrift:
    def test_score_drift_rejected(self) -> None:
        src, res = _themed()
        res["scoring"]["EmpireOfDawn"]["CommerceAct"]["FreeMarket"] = 999
        with pytest.raises(AssertionError, match="score drift"):
            assert_structure_preserved(src, res, _THEMED_MAP)

    def test_batna_drift_rejected(self) -> None:
        src, res = _themed()
        res["batna"]["EmpireOfDawn"] = 999
        with pytest.raises(AssertionError, match="batna drift"):
            assert_structure_preserved(src, res, _THEMED_MAP)

    def test_coalition_value_drift_rejected(self) -> None:
        src, res = _themed()
        res["coalition_values"][0]["values"]["EmpireOfDawn"] = 999
        with pytest.raises(AssertionError, match="value drift"):
            assert_structure_preserved(src, res, _THEMED_MAP)


# ---------------------------------------------------------------------------
# assert_structure_preserved — rejects non-bijective map
# ---------------------------------------------------------------------------

class TestAssertStructurePreservedRejectsNonBijective:
    def test_faction_collision_rejected(self) -> None:
        bad_map = copy.deepcopy(_THEMED_MAP)
        bad_map["factions"]["beta"] = "EmpireOfDawn"  # both map to same name
        src = copy.deepcopy(_BASE_ANALYSIS)
        with pytest.raises(AssertionError, match="not bijective"):
            assert_structure_preserved(src, apply_relabel(src, bad_map), bad_map)

    def test_issue_collision_rejected(self) -> None:
        bad_map = copy.deepcopy(_THEMED_MAP)
        bad_map["issues"]["security"] = "CommerceAct"  # duplicate
        src = copy.deepcopy(_BASE_ANALYSIS)
        with pytest.raises(AssertionError, match="not bijective"):
            assert_structure_preserved(src, apply_relabel(src, bad_map), bad_map)

    def test_outcome_collision_rejected(self) -> None:
        bad_map = copy.deepcopy(_THEMED_MAP)
        bad_map["outcomes"]["closed"] = "FreeMarket"  # duplicate
        src = copy.deepcopy(_BASE_ANALYSIS)
        with pytest.raises(AssertionError, match="not bijective"):
            assert_structure_preserved(src, apply_relabel(src, bad_map), bad_map)


# ---------------------------------------------------------------------------
# assert_structure_preserved — rejects incomplete map
# ---------------------------------------------------------------------------

class TestAssertStructurePreservedRejectsIncomplete:
    def test_missing_faction_rejected(self) -> None:
        incomplete = copy.deepcopy(_THEMED_MAP)
        del incomplete["factions"]["beta"]
        src = copy.deepcopy(_BASE_ANALYSIS)
        with pytest.raises(AssertionError, match="incomplete.*beta"):
            assert_structure_preserved(src, src, incomplete)

    def test_missing_issue_rejected(self) -> None:
        incomplete = copy.deepcopy(_THEMED_MAP)
        del incomplete["issues"]["security"]
        src = copy.deepcopy(_BASE_ANALYSIS)
        with pytest.raises(AssertionError, match="incomplete.*security"):
            assert_structure_preserved(src, src, incomplete)

    def test_missing_outcome_rejected(self) -> None:
        incomplete = copy.deepcopy(_THEMED_MAP)
        del incomplete["outcomes"]["closed"]
        src = copy.deepcopy(_BASE_ANALYSIS)
        with pytest.raises(AssertionError, match="incomplete.*closed"):
            assert_structure_preserved(src, src, incomplete)
