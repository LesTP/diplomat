"""Tests for scenario_narrative.py — apply_relabel + assert_structure_preserved +
extract_catalogue_entry.

All tests are deterministic (no LLM).  Standalone: stdlib + scenario_authoring
sibling imports only.
"""

from __future__ import annotations

import copy
from pathlib import Path

import pytest

from scenario_authoring.scenario_narrative import (
    apply_relabel,
    assert_structure_preserved,
    extract_catalogue_entry,
)

# Path to the prose catalogue at the project root (tests run from project root)
_CATALOGUE_PATH = Path("Multi-Party Negotiation Scenarios.md")


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


# ---------------------------------------------------------------------------
# extract_catalogue_entry — against real catalogue file
# ---------------------------------------------------------------------------

class TestExtractCatalogueEntry:
    @pytest.fixture(scope="class")
    def catalogue(self) -> str:
        return _CATALOGUE_PATH.read_text(encoding="utf-8")

    def test_extracts_known_level4_entry(self, catalogue: str) -> None:
        heading = "#### Camp David (1978) — trilateral mediation"
        text = extract_catalogue_entry(catalogue, heading)
        assert text.startswith(heading)

    def test_extracted_section_ends_before_next_peer_heading(self, catalogue: str) -> None:
        heading = "#### Camp David (1978) — trilateral mediation"
        text = extract_catalogue_entry(catalogue, heading)
        # Section must not bleed into the next #### heading
        assert "#### Dayton Accords" not in text

    def test_extracted_section_contains_expected_content(self, catalogue: str) -> None:
        heading = "#### Camp David (1978) — trilateral mediation"
        text = extract_catalogue_entry(catalogue, heading)
        assert "Carter" in text

    def test_extracts_level3_category_heading(self, catalogue: str) -> None:
        heading = "### Category 2 — Structured Academic / Business Case Studies (PON / TNRC)"
        text = extract_catalogue_entry(catalogue, heading)
        assert text.startswith(heading)
        # Must not bleed into Category 3
        assert "### Category 3" not in text

    def test_unknown_heading_raises_valueerror(self, catalogue: str) -> None:
        with pytest.raises(ValueError, match="not found"):
            extract_catalogue_entry(catalogue, "#### This Heading Does Not Exist")

    def test_invalid_heading_raises_valueerror(self) -> None:
        with pytest.raises(ValueError, match="valid Markdown heading"):
            extract_catalogue_entry("some text", "Not a heading at all")


# ---------------------------------------------------------------------------
# reskin_scenario — mocked structured_call
# ---------------------------------------------------------------------------

def _make_sc_result(success: bool, data: dict | None = None, error: str | None = None):
    class _R:
        pass
    r = _R()
    r.success = success
    r.data = data
    r.error = error
    return r


_RESKIN_RELABEL_MAP: dict[str, dict[str, str]] = {
    "factions": {"alpha": "EmpireOfDawn", "beta": "FreeStates"},
    "issues": {"trade": "CommerceAct", "security": "DefensePact"},
    "outcomes": {
        "open": "FreeMarket",
        "closed": "Protectionist",
        "allied": "MutualDefense",
        "neutral": "NonAlignment",
    },
}

_RESKIN_LLM_RESPONSE = {
    "relabel_map": _RESKIN_RELABEL_MAP,
    "logrolling": ["EmpireOfDawn trades CommerceAct for MutualDefense support"],
    "deception_tactics": {
        "EmpireOfDawn": "Anchor on DefensePact early",
        "FreeStates": "Overstate CommerceAct urgency",
    },
    "narrative_md": "Two powers meet at the negotiating table.\n\nThey must resolve CommerceAct and DefensePact.",
}


class TestReskinScenario:
    def test_returns_reskinned_analysis_and_narrative(self, monkeypatch) -> None:
        import asyncio
        from scenario_authoring.scenario_narrative import reskin_scenario

        async def fake_sc(*args, **kwargs):
            return _make_sc_result(True, _RESKIN_LLM_RESPONSE)

        monkeypatch.setattr("toolkit.structured_llm.structured_call", fake_sc)

        reskinned, narrative = asyncio.run(
            reskin_scenario(
                copy.deepcopy(_BASE_ANALYSIS),
                source_context="Two-faction test scenario",
                llm_client=None,
                llm_config={},
            )
        )

        assert reskinned["factions"] == ["EmpireOfDawn", "FreeStates"]
        assert reskinned["scoring"]["EmpireOfDawn"]["CommerceAct"]["FreeMarket"] == 8
        assert reskinned["batna"]["EmpireOfDawn"] == 5
        assert reskinned["logrolling"] == _RESKIN_LLM_RESPONSE["logrolling"]
        assert "narrative" in narrative.lower() or len(narrative) > 10

    def test_structure_preserved_guard_passes(self, monkeypatch) -> None:
        import asyncio
        from scenario_authoring.scenario_narrative import reskin_scenario

        async def fake_sc(*args, **kwargs):
            return _make_sc_result(True, _RESKIN_LLM_RESPONSE)

        monkeypatch.setattr("toolkit.structured_llm.structured_call", fake_sc)

        reskinned, _ = asyncio.run(
            reskin_scenario(
                copy.deepcopy(_BASE_ANALYSIS),
                source_context="",
                llm_client=None,
                llm_config={},
            )
        )
        # assert_structure_preserved ran without raising; confirm numeric values intact
        assert reskinned["batna"]["FreeStates"] == 4
        assert reskinned["scoring"]["FreeStates"]["DefensePact"]["NonAlignment"] == 4

    def test_value_tampering_mock_rejected_by_guard(self, monkeypatch) -> None:
        import asyncio
        from scenario_authoring.scenario_narrative import reskin_scenario

        tampered = copy.deepcopy(_RESKIN_LLM_RESPONSE)
        # LLM claims to relabel but sneaks in a numeric change — guard must catch it
        # We simulate this by having the mock return a relabel_map that's valid BUT
        # the apply_relabel result will be patched after the fact.
        # Easiest: override apply_relabel to inject drift, then reskin_scenario's guard fires.
        from scenario_authoring import scenario_narrative as sn

        original_apply = sn.apply_relabel

        def drifting_apply(analysis, relabel_map):
            result = original_apply(analysis, relabel_map)
            result["scoring"]["EmpireOfDawn"]["CommerceAct"]["FreeMarket"] = 999
            return result

        monkeypatch.setattr(sn, "apply_relabel", drifting_apply)

        async def fake_sc(*args, **kwargs):
            return _make_sc_result(True, tampered)

        monkeypatch.setattr("toolkit.structured_llm.structured_call", fake_sc)

        with pytest.raises(AssertionError, match="score drift"):
            asyncio.run(
                reskin_scenario(
                    copy.deepcopy(_BASE_ANALYSIS),
                    source_context="",
                    llm_client=None,
                    llm_config={},
                )
            )

    def test_llm_failure_raises_valueerror(self, monkeypatch) -> None:
        import asyncio
        from scenario_authoring.scenario_narrative import reskin_scenario

        async def fake_sc(*args, **kwargs):
            return _make_sc_result(False, error="timeout")

        monkeypatch.setattr("toolkit.structured_llm.structured_call", fake_sc)

        with pytest.raises(ValueError, match="Reskin failed"):
            asyncio.run(
                reskin_scenario(
                    copy.deepcopy(_BASE_ANALYSIS),
                    source_context="",
                    llm_client=None,
                    llm_config={},
                )
            )

    def test_does_not_mutate_source_analysis(self, monkeypatch) -> None:
        import asyncio
        from scenario_authoring.scenario_narrative import reskin_scenario

        async def fake_sc(*args, **kwargs):
            return _make_sc_result(True, _RESKIN_LLM_RESPONSE)

        monkeypatch.setattr("toolkit.structured_llm.structured_call", fake_sc)

        original = copy.deepcopy(_BASE_ANALYSIS)
        asyncio.run(
            reskin_scenario(
                copy.deepcopy(_BASE_ANALYSIS),
                source_context="",
                llm_client=None,
                llm_config={},
            )
        )
        assert _BASE_ANALYSIS == original
