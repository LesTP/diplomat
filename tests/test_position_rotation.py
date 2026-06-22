"""Tests for the position-rotation harness (§3.5 slot-fairness control)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.self_play.position_rotation import (
    all_permutations,
    cyclic_rotations,
    factions_from_analysis,
    rotations,
    spec_string,
)

FACTIONS = ["alpha", "beta", "gamma"]
MODELS = ["M1", "M2", "M3"]


def test_cyclic_has_one_assignment_per_faction():
    rots = cyclic_rotations(FACTIONS, MODELS)
    assert len(rots) == 3


def test_cyclic_every_model_plays_every_slot_once():
    rots = cyclic_rotations(FACTIONS, MODELS)
    # invert: model -> set of slots it played across all rotations
    slots_played: dict[str, list[str]] = {m: [] for m in MODELS}
    for assignment in rots:
        for faction, model in assignment.items():
            slots_played[model].append(faction)
    for model, slots in slots_played.items():
        assert sorted(slots) == sorted(FACTIONS), (model, slots)


def test_cyclic_each_assignment_is_a_permutation():
    for assignment in cyclic_rotations(FACTIONS, MODELS):
        assert sorted(assignment.keys()) == sorted(FACTIONS)
        assert sorted(assignment.values()) == sorted(MODELS)


def test_all_permutations_has_factorial_count():
    assert len(all_permutations(FACTIONS, MODELS)) == 6


def test_mismatched_lengths_raise():
    with pytest.raises(ValueError, match="one model per faction"):
        cyclic_rotations(FACTIONS, ["M1", "M2"])
    with pytest.raises(ValueError, match="one model per faction"):
        all_permutations(FACTIONS, ["M1", "M2"])


def test_rotations_dispatch_and_unknown_scheme():
    assert rotations(FACTIONS, MODELS, "cyclic") == cyclic_rotations(FACTIONS, MODELS)
    assert rotations(FACTIONS, MODELS, "all") == all_permutations(FACTIONS, MODELS)
    with pytest.raises(ValueError, match="unknown scheme"):
        rotations(FACTIONS, MODELS, "bogus")


def test_spec_string_preserves_faction_order():
    assignment = {"alpha": "M2", "beta": "M3", "gamma": "M1"}
    assert spec_string(assignment) == "alpha=M2,beta=M3,gamma=M1"


def test_spec_string_keeps_openrouter_slash_models():
    assignment = {"alpha": "deepseek/deepseek-chat", "beta": "gpt-5.4-mini"}
    assert spec_string(assignment) == "alpha=deepseek/deepseek-chat,beta=gpt-5.4-mini"


def test_factions_from_analysis(tmp_path: Path):
    path = tmp_path / "scenario_analysis.json"
    path.write_text(json.dumps({"factions": ["a", "b", "c"]}), encoding="utf-8")
    assert factions_from_analysis(str(path)) == ["a", "b", "c"]
