"""Tests for reverse scenario builder specs."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scenario_authoring.scenario_spec import IssueSpec, ScenarioSpec, dump_spec, load_spec


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
        pressure_profile={"time_pressure": "medium", "external_shock": "low"},
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
    assert loaded.pressure_profile == {"time_pressure": "medium", "external_shock": "low"}


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
    assert spec.pressure_profile == {"time_pressure": "low", "external_shock": "low"}
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


def test_validation_rejects_invalid_pressure_profile_value() -> None:
    with pytest.raises(ValueError, match="pressure_profile.time_pressure"):
        ScenarioSpec(
            factions=["alpha"],
            issues=[IssueSpec(name="Tariffs", outcomes=["Strict", "Relaxed"])],
            pressure_profile={"time_pressure": "urgent", "external_shock": "low"},
        )


# ── Relative pareto_count_target (Phase 42 Commit 2) ──────────────────


def _basic_kwargs() -> dict:
    return {
        "factions": ["alpha"],
        "issues": [IssueSpec(name="Tariffs", outcomes=["Strict", "Relaxed"])],
    }


def test_accepts_absolute_int_target() -> None:
    spec = ScenarioSpec(**_basic_kwargs(), pareto_count_target=3)
    assert spec.pareto_count_target == 3


def test_accepts_absolute_int_range_target() -> None:
    spec = ScenarioSpec(**_basic_kwargs(), pareto_count_target=(3, 5))
    assert spec.pareto_count_target == (3, 5)


def test_accepts_relative_float_target() -> None:
    spec = ScenarioSpec(**_basic_kwargs(), pareto_count_target=0.1)
    assert spec.pareto_count_target == 0.1


def test_accepts_relative_float_range_target() -> None:
    spec = ScenarioSpec(**_basic_kwargs(), pareto_count_target=(0.05, 0.15))
    assert spec.pareto_count_target == (0.05, 0.15)


def test_rejects_mixed_int_float_range_target() -> None:
    with pytest.raises(ValueError, match="mixed types"):
        ScenarioSpec(**_basic_kwargs(), pareto_count_target=(3, 0.15))


def test_rejects_boolean_target() -> None:
    with pytest.raises(ValueError, match="boolean"):
        ScenarioSpec(**_basic_kwargs(), pareto_count_target=True)


def test_rejects_float_target_above_1() -> None:
    with pytest.raises(ValueError, match=r"\(0.0, 1.0\]"):
        ScenarioSpec(**_basic_kwargs(), pareto_count_target=1.5)


def test_rejects_float_target_at_zero() -> None:
    with pytest.raises(ValueError, match=r"\(0.0, 1.0\]"):
        ScenarioSpec(**_basic_kwargs(), pareto_count_target=0.0)


def test_resolve_passes_through_absolute_int() -> None:
    from scenario_authoring.scenario_spec import resolve_pareto_count_target
    assert resolve_pareto_count_target(3, deal_count=27) == 3


def test_resolve_passes_through_absolute_range() -> None:
    from scenario_authoring.scenario_spec import resolve_pareto_count_target
    assert resolve_pareto_count_target((3, 5), deal_count=27) == (3, 5)


def test_resolve_converts_float_to_absolute() -> None:
    from scenario_authoring.scenario_spec import resolve_pareto_count_target
    # 0.10 of 256 deals -> 26 (rounded)
    assert resolve_pareto_count_target(0.10, deal_count=256) == 26


def test_resolve_converts_float_range_to_absolute() -> None:
    from scenario_authoring.scenario_spec import resolve_pareto_count_target
    assert resolve_pareto_count_target((0.05, 0.15), deal_count=256) == (13, 38)


def test_resolve_floors_at_1_for_small_deal_count() -> None:
    # 0.05 of 10 = 0.5, would round to 0; floor to 1 to keep target satisfiable.
    from scenario_authoring.scenario_spec import resolve_pareto_count_target
    assert resolve_pareto_count_target(0.05, deal_count=10) == 1


def test_relative_target_round_trips_through_json(tmp_path: Path) -> None:
    spec = ScenarioSpec(**_basic_kwargs(), pareto_count_target=(0.05, 0.15))
    spec_path = tmp_path / "spec.json"
    dump_spec(spec, spec_path)
    loaded = load_spec(spec_path)
    assert loaded.pareto_count_target == (0.05, 0.15)
