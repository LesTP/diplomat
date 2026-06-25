"""Tests for the scenario brief: schema validation, feature checks, the
golden succ/succ2 regression (the Run 19 / Run 20 catches), and the CLI.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from scenario_authoring import scenario_brief
from scenario_authoring.scenario_brief import (
    BriefResult,
    FeatureCheck,
    build_brief_readme,
    check_brief,
    load_brief,
)

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCENARIOS = _REPO_ROOT / "scenarios"


def _analysis() -> dict[str, object]:
    """Small 2-faction analysis with a clearing focal point + exact ties.

    Deal sums: (A,A)=20, (A,B)=11, (B,A)=11, (B,B)=2  -> not constant-sum.
    Focal deal (alpha:x=A, beta:y=A) -> 10/10, clears BATNA -> focal exists.
    BATNA-clearing deals: (A,A)=10/10 and (B,B)=1/1 -> both tied at top.
    """
    return {
        "factions": ["alpha", "beta"],
        "issues": [
            {"name": "x", "outcomes": ["A", "B"], "description": "x"},
            {"name": "y", "outcomes": ["A", "B"], "description": "y"},
        ],
        "scoring": {
            "alpha": {"x": {"A": 10, "B": 0}, "y": {"A": 0, "B": 1}},
            "beta": {"x": {"A": 0, "B": 1}, "y": {"A": 10, "B": 0}},
        },
        "batna": {"alpha": 0, "beta": 0},
        "deception_tactics": {"alpha": "", "beta": ""},
        "logrolling": [],
        "game_mode": "mixed",
        "pressure": {
            "round_cost_decay": 0.0,
            "asymmetric_clocks": {},
            "penalty_floor_offset": 0.0,
        },
        "pressure_profile": {"time_pressure": "low", "external_shock": "low"},
    }


def _checks_by_name(result: BriefResult) -> dict[str, FeatureCheck]:
    return {c.name: c for c in result.checks}


# ---------------------------------------------------------------------------
# load_brief validation
# ---------------------------------------------------------------------------


def test_load_brief_accepts_wellformed(tmp_path: Path) -> None:
    brief_path = tmp_path / "brief.json"
    brief_path.write_text(
        json.dumps(
            {
                "goal": "a distributive contest",
                "features": {
                    "constant_sum": True,
                    "priority_collision": "soft",
                    "winner_spread": {"min_per_faction": 1},
                    "batna_clearing_count": {"min": 2, "max": 8},
                },
            }
        ),
        encoding="utf-8",
    )
    brief = load_brief(brief_path)
    assert brief["goal"] == "a distributive contest"
    assert brief["features"]["constant_sum"] is True
    assert brief["features"]["batna_clearing_count"] == {"min": 2, "max": 8}


def test_load_brief_rejects_unknown_feature(tmp_path: Path) -> None:
    brief_path = tmp_path / "brief.json"
    brief_path.write_text(
        json.dumps({"features": {"made_up_feature": True}}), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="unknown brief feature"):
        load_brief(brief_path)


def test_load_brief_rejects_empty_features(tmp_path: Path) -> None:
    brief_path = tmp_path / "brief.json"
    brief_path.write_text(json.dumps({"features": {}}), encoding="utf-8")
    with pytest.raises(ValueError, match="non-empty 'features'"):
        load_brief(brief_path)


def test_load_brief_rejects_bad_collision(tmp_path: Path) -> None:
    brief_path = tmp_path / "brief.json"
    brief_path.write_text(
        json.dumps({"features": {"priority_collision": "extreme"}}), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="priority_collision"):
        load_brief(brief_path)


def test_load_brief_rejects_min_gt_max(tmp_path: Path) -> None:
    brief_path = tmp_path / "brief.json"
    brief_path.write_text(
        json.dumps({"features": {"batna_clearing_count": {"min": 9, "max": 2}}}),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="min <= max"):
        load_brief(brief_path)


# ---------------------------------------------------------------------------
# check_brief per-feature: PASS and FAIL on the same fixture
# ---------------------------------------------------------------------------


def test_constant_sum_check() -> None:
    a = _analysis()
    assert _checks_by_name(check_brief(a, {"features": {"constant_sum": False}}))[
        "constant_sum"
    ].passed
    assert not _checks_by_name(check_brief(a, {"features": {"constant_sum": True}}))[
        "constant_sum"
    ].passed


def test_no_focal_point_check() -> None:
    a = _analysis()
    # focal deal exists and clears BATNAs -> observed no_focal_point == False
    assert not _checks_by_name(
        check_brief(a, {"features": {"no_focal_point": True}})
    )["no_focal_point"].passed
    assert _checks_by_name(check_brief(a, {"features": {"no_focal_point": False}}))[
        "no_focal_point"
    ].passed


def test_priority_collision_check() -> None:
    a = _analysis()
    assert _checks_by_name(
        check_brief(a, {"features": {"priority_collision": "none"}})
    )["priority_collision"].passed
    assert not _checks_by_name(
        check_brief(a, {"features": {"priority_collision": "hard"}})
    )["priority_collision"].passed


def test_batna_clearing_count_check() -> None:
    a = _analysis()
    chk = _checks_by_name(
        check_brief(a, {"features": {"batna_clearing_count": {"min": 2, "max": 2}}})
    )["batna_clearing_count"]
    assert chk.observed == 2
    assert chk.passed
    assert not _checks_by_name(
        check_brief(a, {"features": {"batna_clearing_count": {"min": 3}}})
    )["batna_clearing_count"].passed


def test_winner_spread_check() -> None:
    a = _analysis()
    # both clearing deals are tied at the top -> no faction wins outright
    assert _checks_by_name(
        check_brief(a, {"features": {"winner_spread": {"min_per_faction": 0}}})
    )["winner_spread"].passed
    assert not _checks_by_name(
        check_brief(a, {"features": {"winner_spread": {"min_per_faction": 1}}})
    )["winner_spread"].passed


def test_no_exact_ties_check() -> None:
    a = _analysis()
    assert not _checks_by_name(
        check_brief(a, {"features": {"no_exact_ties": True}})
    )["no_exact_ties"].passed
    assert _checks_by_name(check_brief(a, {"features": {"no_exact_ties": False}}))[
        "no_exact_ties"
    ].passed


def test_only_declared_features_are_checked() -> None:
    result = check_brief(_analysis(), {"features": {"constant_sum": False}})
    assert [c.name for c in result.checks] == ["constant_sum"]
    assert result.all_passed


# ---------------------------------------------------------------------------
# Golden regression: the real succ / succ2 scenarios
# ---------------------------------------------------------------------------


def _load_scenario(name: str) -> dict[str, object]:
    return json.loads(
        (_SCENARIOS / name / "scenario_analysis.json").read_text(encoding="utf-8")
    )


def test_succ_brief_catches_run19_focal_point() -> None:
    analysis = _load_scenario("succession_division_v1")
    brief = load_brief(_SCENARIOS / "succession_division_v1" / "brief.json")
    result = check_brief(analysis, brief)
    assert not result.all_passed
    # Run 19 catch: the everyone-takes-own-priority deal clears all BATNAs.
    assert "no_focal_point" in result.failed_features


def test_succ2_brief_catches_run20_deadlock() -> None:
    analysis = _load_scenario("succession_division_v2")
    brief = load_brief(_SCENARIOS / "succession_division_v2" / "brief.json")
    result = check_brief(analysis, brief)
    assert not result.all_passed
    # Run 20 catch: too few BATNA-clearing deals -> deadlock risk.
    assert "batna_clearing_count" in result.failed_features


# ---------------------------------------------------------------------------
# auto-doc
# ---------------------------------------------------------------------------


def test_build_brief_readme_contains_table_and_verdict() -> None:
    a = _analysis()
    brief = {"goal": "test goal", "features": {"constant_sum": True}}
    result = check_brief(a, brief)
    doc = build_brief_readme(a, brief, result, title="Demo", viz_rel_path="x.html")
    assert "# Demo" in doc
    assert "test goal" in doc
    assert "| Feature | Expected | Observed | Result |" in doc
    assert "FAIL" in doc  # constant_sum:True fails on the non-constant fixture
    assert "[Deal explorer](x.html)" in doc


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _write_analysis(tmp_path: Path) -> Path:
    path = tmp_path / "scenario_analysis.json"
    path.write_text(json.dumps(_analysis()), encoding="utf-8")
    return path


def test_cli_returns_zero_on_pass_and_writes_doc(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    analysis_path = _write_analysis(tmp_path)
    brief_path = tmp_path / "brief.json"
    brief_path.write_text(
        json.dumps({"features": {"constant_sum": False}}), encoding="utf-8"
    )
    doc_path = tmp_path / "README.md"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "scenario_brief",
            "--analysis",
            str(analysis_path),
            "--brief",
            str(brief_path),
            "--doc",
            str(doc_path),
        ],
    )
    assert scenario_brief.main() == 0
    assert doc_path.is_file()
    assert "Brief check" in doc_path.read_text(encoding="utf-8")


def test_cli_returns_two_on_fail(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    analysis_path = _write_analysis(tmp_path)
    brief_path = tmp_path / "brief.json"
    brief_path.write_text(
        json.dumps({"features": {"no_focal_point": True}}), encoding="utf-8"
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "scenario_brief",
            "--analysis",
            str(analysis_path),
            "--brief",
            str(brief_path),
        ],
    )
    assert scenario_brief.main() == 2
