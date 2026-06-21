"""Scale regression for the Phase 42 4x4x4 builder success criterion.

Locks in PROJECT.md's "scales to 4+ factions / 4+ issues" criterion. With the
C5a relative ``batna_clearing_count_target`` and the deterministic builder
(C5b), a synthetic 4x4x4 / D=256 spec converges within the probe restart
budget. seed=0 is a known-accepting seed in the post-C5b probe matrix; because
the builder is now PYTHONHASHSEED-independent, this is reproducible.

Mirrors ``tools/scenario_builder_scale_probe.py::synthesize_spec`` with
``relative_batna=True`` so the regression tracks the same target shape the
probe validated.
"""

from __future__ import annotations

from pathlib import Path

from scenario_authoring.scenario_builder import build_and_save_scenario
from scenario_authoring.scenario_spec import IssueSpec, ScenarioSpec


def _synthetic_4x4x4_spec(seed: int) -> ScenarioSpec:
    faction_ids = [f"f{i}" for i in range(4)]
    return ScenarioSpec(
        factions=faction_ids,
        issues=[
            IssueSpec(name=f"i{i}", outcomes=[f"o{j}" for j in range(4)])
            for i in range(4)
        ],
        score_range=(1, 10),
        pareto_count_target=(3, 5),
        pareto_distribution_spread=0.35,
        pareto_outcome_diversity=0.66,
        batna_clearing_count_target=0.20,  # C5a relative form (20% of D)
        batna_to_pareto_gap_pct=0.20,
        requires_logrolling=True,
        priority_collision="soft",
        asymmetric_batna_fractions={fid: 0.5 for fid in faction_ids},
        target_weights={"pareto_distribution_spread": 0.0},
        game_mode="mixed",
        seed=seed,
    )


def test_builds_4x4x4_in_budget(tmp_path: Path) -> None:
    spec = _synthetic_4x4x4_spec(seed=0)
    analysis, analysis_path, persona_paths = build_and_save_scenario(
        spec, tmp_path, max_restarts=50, seed=0,
    )
    assert analysis_path.is_file()
    assert len(analysis["factions"]) == 4
    assert set(persona_paths) == set(spec.factions)
