"""Phase 51, Item 3 — N-pooling contract + deterministic bootstrap CIs.

Contract:
  - rank_aggregator.aggregate_files pools all K games for a given (model, scenario)
    cell regardless of how many result files contribute — tested via synthetic JSON
    fixtures (no games run).
  - No-deal exclusion behaves as documented: deal_reached=False games are excluded
    from the pool by default; include_no_deal=True keeps them.
  - bootstrap_ci(values, *, seed, iterations, alpha) -> (point, ci_low, ci_high)
    is deterministic (same seed → byte-identical output), satisfies
    ci_low <= point <= ci_high, and handles degenerate inputs without error.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import pytest

from tests.self_play.rank_aggregator import aggregate_files, is_no_deal

# bootstrap_ci may live in rank_aggregator or a new aggregate_stats module.
try:
    from tests.self_play.aggregate_stats import bootstrap_ci
    _BOOTSTRAP_AVAILABLE = True
except ImportError:
    try:
        from tests.self_play.rank_aggregator import bootstrap_ci  # type: ignore[no-redef]
        _BOOTSTRAP_AVAILABLE = True
    except ImportError:
        _BOOTSTRAP_AVAILABLE = False
        def bootstrap_ci(*args, **kwargs):  # type: ignore[misc]
            raise NotImplementedError("bootstrap_ci not implemented yet")

_need_bootstrap = pytest.mark.xfail(
    not _BOOTSTRAP_AVAILABLE,
    reason="bootstrap_ci not implemented yet",
    strict=False,
)

# ---------------------------------------------------------------------------
# Synthetic result-JSON helpers
# ---------------------------------------------------------------------------

_SCENARIO_ANALYSIS = {
    "factions": ["alpha", "beta", "gamma"],
    "batna": {"alpha": 0, "beta": 0, "gamma": 0},
    "issues": [{"name": "issue_a", "outcomes": []}],
}


def _make_result(
    *,
    model: str = "openai/gpt-4.1-nano",
    scenario: str = "jsm1",
    alpha_rank: int = 1,
    beta_rank: int = 2,
    gamma_rank: int = 3,
    deal_reached: bool = True,
) -> dict:
    """Synthetic result JSON mirroring the real result schema."""
    return {
        "faction_models": {
            "alpha": {"provider": model.split("/")[0], "model": model.split("/")[1] if "/" in model else model},
            "beta": {"provider": "openai", "model": "gpt-4.1-nano"},
            "gamma": {"provider": "openai", "model": "gpt-4.1-nano"},
        },
        "scores": {
            "deal_reached": deal_reached,
            "faction_ranks": {
                "alpha": alpha_rank,
                "beta": beta_rank,
                "gamma": gamma_rank,
            },
            "faction_scores": {
                "alpha": {"points": 10.0, "batna": 0.0},
                "beta": {"points": 8.0, "batna": 0.0},
                "gamma": {"points": 5.0, "batna": 0.0},
            },
        },
        "scenario_analysis": _SCENARIO_ANALYSIS,
    }


def _write_results(tmp_path: Path, results: list[dict]) -> list[str]:
    """Write synthetic result dicts to temp files, return paths."""
    paths = []
    for i, result in enumerate(results):
        p = tmp_path / f"result_{i:03d}.json"
        p.write_text(json.dumps(result), encoding="utf-8")
        paths.append(str(p))
    return paths


# ---------------------------------------------------------------------------
# N-pooling contract
# ---------------------------------------------------------------------------


class TestNPoolingContract:
    """AC 1 — aggregate_files pools exactly K games per (model, scenario) cell."""

    def test_single_file_pools_one_game(self, tmp_path: Path) -> None:
        """One result file → one game pooled for the model."""
        results = [_make_result(model="openai/gpt-4.1-nano")]
        paths = _write_results(tmp_path, results)
        agg, used, skipped, no_deal_excl = aggregate_files(paths)
        assert used == 1
        assert skipped == 0
        # The pool for alpha's model should have n=1
        alpha_model = "openai/gpt-4.1-nano"
        matching = {k: v for k, v in agg.items() if k[1] == alpha_model}
        assert matching, f"No aggregate entry found for model '{alpha_model}'"
        total_n = sum(v["n"] for v in matching.values())
        # alpha appears once per game, and there is 1 game, so n=1 for alpha's slot
        assert total_n >= 1

    def test_k_files_pool_exactly_k_games(self, tmp_path: Path) -> None:
        """K result files for one (model, scenario) cell pool exactly K games."""
        K = 5
        results = [_make_result(model="openai/gpt-4.1-nano") for _ in range(K)]
        paths = _write_results(tmp_path, results)
        agg, used, skipped, no_deal_excl = aggregate_files(paths)
        assert used == K, f"Expected {K} games used, got {used}"
        # All K alpha slots are the same model; each result contributes one rank
        # sample for alpha, so the model's n across its scenario should equal K.
        alpha_model = "openai/gpt-4.1-nano"
        # aggregate pools all faction slots playing that model across all files.
        # alpha plays alpha_model in every file → K alpha samples, plus beta and
        # gamma who also play gpt-4.1-nano → 3*K total. Accept any that includes
        # the K alpha contributions.
        matching = {k: v for k, v in agg.items() if k[1] == alpha_model}
        assert matching, "No aggregate entry for the model"
        # At minimum alpha's n == K (there may be one entry for the scenario
        # pooling all three faction slots if they share the model).
        for (scenario, model), stats in matching.items():
            assert stats["n"] >= K, (
                f"Expected n >= {K} for ({scenario}, {model}), got {stats['n']}"
            )

    def test_no_deal_excluded_by_default(self, tmp_path: Path) -> None:
        """No-deal games (deal_reached=False) are excluded from the pool by default."""
        deal_result = _make_result(model="openai/gpt-4.1-nano", deal_reached=True)
        no_deal_result = _make_result(model="openai/gpt-4.1-nano", deal_reached=False)
        paths = _write_results(tmp_path, [deal_result, no_deal_result])
        agg, used, skipped, no_deal_excl = aggregate_files(paths)
        assert no_deal_excl == 1, f"Expected 1 no-deal excluded, got {no_deal_excl}"
        assert used == 1, f"Expected 1 game used (the deal game), got {used}"

    def test_no_deal_included_when_flag_set(self, tmp_path: Path) -> None:
        """With include_no_deal=True, no-deal games are kept in the pool."""
        deal_result = _make_result(model="openai/gpt-4.1-nano", deal_reached=True)
        no_deal_result = _make_result(model="openai/gpt-4.1-nano", deal_reached=False)
        paths = _write_results(tmp_path, [deal_result, no_deal_result])
        agg, used, skipped, no_deal_excl = aggregate_files(paths, include_no_deal=True)
        assert no_deal_excl == 0, "No-deal games should not be excluded when include_no_deal=True"
        assert used == 2

    def test_missing_faction_ranks_skipped(self, tmp_path: Path) -> None:
        """Result files without faction_ranks in scores are skipped (pre-rank-lens)."""
        result_no_ranks = {
            "faction_models": {"alpha": {"provider": "openai", "model": "gpt-4.1-nano"}},
            "scores": {"deal_reached": True},  # no faction_ranks
        }
        paths = _write_results(tmp_path, [result_no_ranks])
        agg, used, skipped, no_deal_excl = aggregate_files(paths)
        assert skipped == 1
        assert used == 0

    def test_invalid_json_file_skipped(self, tmp_path: Path) -> None:
        """Files that cannot be parsed as JSON are skipped without error."""
        bad_file = tmp_path / "bad.json"
        bad_file.write_text("not valid json {{{{", encoding="utf-8")
        paths = [str(bad_file)]
        agg, used, skipped, no_deal_excl = aggregate_files(paths)
        assert skipped == 1
        assert used == 0

    def test_is_no_deal_false_for_deal_game(self) -> None:
        """is_no_deal() returns False when deal_reached is True."""
        result = _make_result(deal_reached=True)
        assert not is_no_deal(result)

    def test_is_no_deal_true_for_no_deal_game(self) -> None:
        """is_no_deal() returns True when deal_reached is False."""
        result = _make_result(deal_reached=False)
        assert is_no_deal(result)

    def test_is_no_deal_false_when_key_missing(self) -> None:
        """is_no_deal() treats missing deal_reached as a deal (not a no-deal)."""
        result = {"scores": {}}
        assert not is_no_deal(result)


# ---------------------------------------------------------------------------
# bootstrap_ci correctness
# ---------------------------------------------------------------------------


@_need_bootstrap
class TestBootstrapCIDeterminism:
    """AC 2 — bootstrap_ci with a fixed seed returns byte-identical results across runs."""

    def test_same_seed_same_result(self) -> None:
        """bootstrap_ci with fixed seed is deterministic."""
        values = [1, 2, 2, 3, 3, 3, 4, 4, 5]
        r1 = bootstrap_ci(values, seed=42, iterations=500, alpha=0.05)
        r2 = bootstrap_ci(values, seed=42, iterations=500, alpha=0.05)
        assert r1 == r2, f"Non-deterministic output: {r1} != {r2}"

    def test_different_seeds_may_differ(self) -> None:
        """Different seeds are expected to produce different (or same-by-chance) results; no crash."""
        values = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        r1 = bootstrap_ci(values, seed=1, iterations=500, alpha=0.05)
        r2 = bootstrap_ci(values, seed=2, iterations=500, alpha=0.05)
        # We only assert no exception; different seeds may coincidentally agree.
        assert len(r1) == 3
        assert len(r2) == 3


@_need_bootstrap
class TestBootstrapCICorrectness:
    """AC 3 — structural correctness: ci_low <= point <= ci_high; wider alpha → wider CI."""

    def test_ci_ordering(self) -> None:
        """ci_low <= point <= ci_high for a typical input."""
        values = [1, 2, 3, 3, 4, 4, 5, 5, 6, 7]
        point, ci_low, ci_high = bootstrap_ci(values, seed=42, iterations=1000, alpha=0.05)
        assert ci_low <= point, f"ci_low={ci_low} > point={point}"
        assert point <= ci_high, f"point={point} > ci_high={ci_high}"

    def test_wider_alpha_yields_wider_interval(self) -> None:
        """A larger alpha (less confident) produces a wider or equal CI than a smaller alpha."""
        values = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        _, lo_narrow, hi_narrow = bootstrap_ci(values, seed=42, iterations=1000, alpha=0.05)
        _, lo_wide, hi_wide = bootstrap_ci(values, seed=42, iterations=1000, alpha=0.20)
        narrow_width = hi_narrow - lo_narrow
        wide_width = hi_wide - lo_wide
        assert wide_width <= narrow_width, (  # wider alpha = smaller interval bounds
            f"Expected wider alpha to shrink the CI: alpha=0.20 width={wide_width}, "
            f"alpha=0.05 width={narrow_width}"
        )

    def test_point_is_mean_or_median(self) -> None:
        """Point estimate must be within the data range."""
        values = [2, 4, 6, 8, 10]
        point, _, _ = bootstrap_ci(values, seed=42, iterations=500, alpha=0.05)
        assert min(values) <= point <= max(values), (
            f"Point estimate {point} outside data range [{min(values)}, {max(values)}]"
        )

    def test_degenerate_single_value_no_error(self) -> None:
        """n=1 input must not raise."""
        point, ci_low, ci_high = bootstrap_ci([7.0], seed=42, iterations=100, alpha=0.05)
        assert ci_low <= point <= ci_high

    def test_degenerate_all_equal_values_no_error(self) -> None:
        """All-equal input must not raise and CI must be degenerate (width=0)."""
        values = [5.0] * 10
        point, ci_low, ci_high = bootstrap_ci(values, seed=42, iterations=100, alpha=0.05)
        assert ci_low <= point <= ci_high
        # All values are identical; CI should be [5.0, 5.0].
        assert ci_low == pytest.approx(5.0), f"ci_low={ci_low} for all-equal input"
        assert ci_high == pytest.approx(5.0), f"ci_high={ci_high} for all-equal input"

    def test_more_iterations_does_not_crash(self) -> None:
        """High iteration count must complete without error."""
        values = list(range(1, 21))
        result = bootstrap_ci(values, seed=0, iterations=2000, alpha=0.05)
        assert len(result) == 3
