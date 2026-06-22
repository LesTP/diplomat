"""Tests for the cross-game mean_rank aggregator (§3.5 cross-game half)."""

from __future__ import annotations

import json
from pathlib import Path

from tests.self_play.rank_aggregator import (
    aggregate,
    aggregate_files,
    extract_samples,
    model_label,
    scenario_key,
)


def _result(faction_ranks, faction_models, issues=None):
    return {
        "scores": {"faction_ranks": faction_ranks},
        "faction_models": faction_models,
        "scenario_analysis": {"issues": issues or [{"name": "i1"}, {"name": "i2"}]},
    }


def test_model_label_handles_missing_entry():
    assert model_label({"provider": "openai", "model": "gpt-5.5"}) == "openai/gpt-5.5"
    assert model_label(None) == "unknown"
    assert model_label({}) == "unknown"


def test_scenario_key_parses_filename():
    result = _result({}, {})
    assert scenario_key(result, "run17_bare_gpt55_succ_2.json") == "succ"
    assert scenario_key(result, "run17_full_deepseekchat_wrbeta_1.json") == "wrbeta"


def test_scenario_key_falls_back_to_issue_signature():
    result = _result({}, {}, issues=[{"name": "beta_i"}, {"name": "alpha_i"}])
    # no parseable filename -> sorted issue names
    assert scenario_key(result, "custom_name.json") == "alpha_i+beta_i"
    assert scenario_key(result, None) == "alpha_i+beta_i"


def test_extract_samples_joins_rank_and_model():
    result = _result(
        {"alpha": 1, "beta": 2, "gamma": 3},
        {
            "alpha": {"provider": "openai", "model": "gpt-5.5"},
            "beta": {"provider": "openai", "model": "gpt-4.1-mini"},
            "gamma": {"provider": "openai", "model": "gpt-4.1-mini"},
        },
    )
    samples = extract_samples(result, "run17_full_mixed_succ_1.json")
    assert ("succ", "openai/gpt-5.5", 1) in samples
    assert ("succ", "openai/gpt-4.1-mini", 2) in samples
    assert ("succ", "openai/gpt-4.1-mini", 3) in samples
    assert len(samples) == 3


def test_extract_samples_empty_when_no_faction_ranks():
    # results predating the rank lens carry no faction_ranks
    result = {"scores": {}, "faction_models": {}}
    assert extract_samples(result, "run17_full_x_succ_1.json") == []


def test_aggregate_computes_mean_rank_and_win_rate():
    samples = [
        ("succ", "openai/gpt-5.5", 1),
        ("succ", "openai/gpt-5.5", 2),
        ("succ", "openai/gpt-4.1-mini", 3),
        ("succ", "openai/gpt-4.1-mini", 3),
    ]
    agg = aggregate(samples)
    strong = agg[("succ", "openai/gpt-5.5")]
    weak = agg[("succ", "openai/gpt-4.1-mini")]
    assert strong["n"] == 2
    assert strong["mean_rank"] == 1.5
    assert strong["win_rate"] == 0.5
    assert weak["mean_rank"] == 3.0
    assert weak["win_rate"] == 0.0


def test_aggregate_files_pools_across_files(tmp_path: Path):
    # two games, mixed population; strong model out-ranks weak across files
    for n in (1, 2):
        result = _result(
            {"alpha": 1, "beta": 2, "gamma": 3},
            {
                "alpha": {"provider": "anthropic", "model": "claude-sonnet-4-6"},
                "beta": {"provider": "openai", "model": "gpt-4.1-mini"},
                "gamma": {"provider": "openai", "model": "gpt-4.1-mini"},
            },
        )
        (tmp_path / f"run17_full_mixed_succ_{n}.json").write_text(
            json.dumps(result), encoding="utf-8"
        )

    agg, used, skipped, no_deal = aggregate_files(
        [str(p) for p in tmp_path.glob("*.json")]
    )
    assert used == 2
    assert skipped == 0
    assert no_deal == 0
    assert agg[("succ", "anthropic/claude-sonnet-4-6")]["mean_rank"] == 1.0
    assert agg[("succ", "anthropic/claude-sonnet-4-6")]["win_rate"] == 1.0
    assert agg[("succ", "openai/gpt-4.1-mini")]["n"] == 4  # 2 slots × 2 games
    assert agg[("succ", "openai/gpt-4.1-mini")]["mean_rank"] == 2.5


def test_aggregate_files_skips_unparseable_and_rankless(tmp_path: Path):
    (tmp_path / "bad.json").write_text("{not json", encoding="utf-8")
    (tmp_path / "run17_full_x_succ_1.json").write_text(
        json.dumps({"scores": {}}), encoding="utf-8"
    )
    agg, used, skipped, no_deal = aggregate_files(
        [str(p) for p in tmp_path.glob("*.json")]
    )
    assert used == 0
    assert skipped == 2
    assert no_deal == 0
    assert agg == {}


def test_aggregate_files_excludes_no_deal_by_default(tmp_path: Path):
    # A no-deal game (deal_reached False) has BATNA-determined ranks; exclude it.
    result = _result(
        {"alpha": 1, "beta": 2, "gamma": 2},
        {
            "alpha": {"provider": "anthropic", "model": "claude-sonnet-4-6"},
            "beta": {"provider": "openai", "model": "gpt-4.1-mini"},
            "gamma": {"provider": "openrouter", "model": "deepseek/deepseek-chat"},
        },
    )
    result["scores"]["deal_reached"] = False
    (tmp_path / "run17_bare_mix_succ_1.json").write_text(
        json.dumps(result), encoding="utf-8"
    )

    agg, used, skipped, no_deal = aggregate_files(
        [str(p) for p in tmp_path.glob("*.json")]
    )
    assert used == 0
    assert no_deal == 1
    assert agg == {}

    # ...but kept when explicitly included
    agg2, used2, _, no_deal2 = aggregate_files(
        [str(p) for p in tmp_path.glob("*.json")], include_no_deal=True
    )
    assert used2 == 1
    assert no_deal2 == 0
    assert agg2[("succ", "anthropic/claude-sonnet-4-6")]["mean_rank"] == 1.0
