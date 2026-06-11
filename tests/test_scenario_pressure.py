from __future__ import annotations

import json
from pathlib import Path

from tests.self_play.verify_scenario_pressure import (
    deadline_context,
    effective_batna,
    verify_pressure_profile,
)


def _load_pressure_fixture() -> dict[str, object]:
    fixture_path = Path("tests/self_play/fixtures/pressure/pressure_good.json")
    return json.loads(fixture_path.read_text(encoding="utf-8"))


def test_pressure_verifier_passes_on_fixture() -> None:
    analysis = _load_pressure_fixture()

    report, failures = verify_pressure_profile(analysis, min_drop_pct=0.20)

    assert failures == []
    assert any("priority_collision=soft" in line for line in report)
    assert any("alpha→round 4" in line for line in report)


def test_pressure_verifier_rejects_too_small_drop() -> None:
    analysis = _load_pressure_fixture()
    analysis["pressure"] = {
        "round_cost_decay": 0.1,
        "asymmetric_clocks": {"alpha": 3},
        "penalty_floor_offset": 0.0,
    }

    _report, failures = verify_pressure_profile(analysis, min_drop_pct=0.20)

    assert len(failures) == 1
    assert "falls by only" in failures[0]


def test_pressure_verifier_rejects_deadlines_without_priority_collision() -> None:
    analysis = _load_pressure_fixture()
    analysis["priority_collision"] = "none"

    _report, failures = verify_pressure_profile(analysis, min_drop_pct=0.20)

    assert any("priority_collision is 'none'" in failure for failure in failures)


def test_deadline_context_renders_accept_or_bust_final_round() -> None:
    analysis = _load_pressure_fixture()
    context = deadline_context(analysis, "beta")

    assert "Round: 2 of 2" in context
    assert "### FINAL ROUND" in context
    assert "Effective BATNA this round: 2.5 points" in context


def test_effective_batna_matches_expected_formula() -> None:
    assert effective_batna(
        6.0,
        round_cost_decay=1.5,
        penalty_floor_offset=2.0,
        round_number=4,
    ) == -0.5
