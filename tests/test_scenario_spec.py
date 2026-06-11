"""Tests for reverse scenario builder specs."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.scenario_spec import IssueSpec, ScenarioSpec, dump_spec, load_spec


def test_round_trip_preserves_nested_defaults_and_ranges(tmp_path: Path) -> None:
    spec = ScenarioSpec(
        factions=["alpha", "beta"],
        issues=[
            IssueSpec(name="Tariffs", outcomes=["Strict", "Relaxed"], description="Trade barriers"),
            IssueSpec(name="Labor", outcomes=["Strict", "Relaxed"], description="Worker protections"),
        ],
        score_range=(2, 9),
        pareto_count_target=(2, 4),
        pareto_distribution_spread=1.25,
        batna_clearing_count_target=3,
        batna_to_pareto_gap_pct=0.15,
        requires_logrolling=True,
        priority_collision="soft",
        pressure={
            "round_cost_decay": 1.5,
            "asymmetric_clocks": {"alpha": 3},
            "penalty_floor_offset": 2.0,
        },
        asymmetric_batna_fractions={"alpha": 0.65},
        target_weights={"pareto_count": 2.0, "game_mode": 0.3},
        game_mode="mixed",
        seed=99,
    )

    path = dump_spec(spec, tmp_path / "spec.json")
    loaded = load_spec(path)

    assert loaded == spec
    assert loaded.issues[0] == IssueSpec(
        name="Tariffs",
        outcomes=["Strict", "Relaxed"],
        description="Trade barriers",
    )
    assert loaded.pressure.round_cost_decay == 1.5
    assert loaded.pressure.asymmetric_clocks == {"alpha": 3}
    assert loaded.pressure.penalty_floor_offset == 2.0


def test_load_applies_defaults(tmp_path: Path) -> None:
    path = tmp_path / "spec.json"
    path.write_text(
        json.dumps(
            {
                "factions": ["alpha"],
                "issues": [
                    {"name": "Tariffs", "outcomes": ["Strict", "Relaxed"]},
                ],
            }
        ),
        encoding="utf-8",
    )

    spec = load_spec(path)

    assert spec.score_range == (1, 10)
    assert spec.pareto_count_target == 1
    assert spec.pareto_distribution_spread == 0.0
    assert spec.pareto_outcome_diversity == 0.0
    assert spec.batna_clearing_count_target == 1
    assert spec.batna_to_pareto_gap_pct == 0.10
    assert spec.requires_logrolling is False
    assert spec.priority_collision == "none"
    assert spec.pressure.round_cost_decay == 0.0
    assert spec.pressure.asymmetric_clocks == {}
    assert spec.pressure.penalty_floor_offset == 0.0
    assert spec.asymmetric_batna_fractions == {}
    assert spec.target_weights == {}
    assert spec.game_mode == "mixed"
    assert spec.seed == 0


def test_validation_rejects_invalid_target_weight() -> None:
    with pytest.raises(ValueError, match="must be non-negative"):
        ScenarioSpec(
            factions=["alpha"],
            issues=[IssueSpec(name="Tariffs", outcomes=["Strict", "Relaxed"])],
            target_weights={"pareto_count": -0.1},
        )


def test_validation_rejects_invalid_pareto_outcome_diversity() -> None:
    with pytest.raises(ValueError, match="pareto_outcome_diversity"):
        ScenarioSpec(
            factions=["alpha"],
            issues=[IssueSpec(name="Tariffs", outcomes=["Strict", "Relaxed"])],
            pareto_outcome_diversity=1.1,
        )


def test_validation_rejects_invalid_faction_fraction() -> None:
    with pytest.raises(ValueError, match="must name a faction"):
        ScenarioSpec(
            factions=["alpha"],
            issues=[IssueSpec(name="Tariffs", outcomes=["Strict", "Relaxed"])],
            asymmetric_batna_fractions={"beta": 0.6},
        )


def test_validation_rejects_invalid_score_range() -> None:
    with pytest.raises(ValueError, match="score_range"):
        ScenarioSpec(
            factions=["alpha"],
            issues=[IssueSpec(name="Tariffs", outcomes=["Strict", "Relaxed"])],
            score_range=(10, 1),
        )


def test_validation_rejects_invalid_pressure_clock_faction() -> None:
    with pytest.raises(ValueError, match="asymmetric_clocks keys must name a faction"):
        ScenarioSpec(
            factions=["alpha"],
            issues=[IssueSpec(name="Tariffs", outcomes=["Strict", "Relaxed"])],
            pressure={"asymmetric_clocks": {"beta": 3}},
        )
