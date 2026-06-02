from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.self_play.analysis import compute_near_miss


RESULTS_DIR = Path(__file__).resolve().parent / "self_play" / "results"


def _load_results(filename: str) -> dict:
    return json.loads((RESULTS_DIR / filename).read_text(encoding="utf-8"))


def _synthetic_near_miss_results() -> dict:
    return {
        "rounds_completed": 4,
        "scenario_analysis": {
            "factions": ["alpha", "beta", "gamma"],
            "issues": [
                {
                    "name": "core_terms",
                    "outcomes": ["Alpha option", "Beta option"],
                }
            ],
            "scoring": {
                "alpha": {"core_terms": {"Alpha option": 6, "Beta option": 4}},
                "beta": {"core_terms": {"Alpha option": 5, "Beta option": 7}},
                "gamma": {"core_terms": {"Alpha option": 4, "Beta option": 8}},
            },
            "batna": {"alpha": 2, "beta": 2, "gamma": 2},
        },
        "round_responses": {
            "1": {
                "alpha": "Round 1: Beta option remains best.",
                "beta": "Round 1: Beta option remains best.",
                "gamma": "Round 1: Beta option remains best.",
            },
            "2": {
                "alpha": "If beta and gamma commit, Beta option is workable.",
                "beta": "Round 2: Beta option remains best.",
                "gamma": "Round 2: Beta option remains best.",
            },
            "3": {
                "alpha": "If beta and gamma commit, Beta option is workable.",
                "beta": "Round 3: Beta option remains best.",
                "gamma": "Round 3: Beta option remains best.",
            },
            "4": {
                "alpha": "Final stance: Alpha option.",
                "beta": "Final stance: Beta option.",
                "gamma": "Final stance: Beta option.",
            },
        },
    }


def test_compute_near_miss_detects_two_of_three_final_alignment():
    result = compute_near_miss(_synthetic_near_miss_results())

    assert result["near_miss"] is True
    assert set(result["converging_factions"]) == {"beta", "gamma"}
    assert result["dissenting_faction"] == "alpha"
    assert result["defection_event_log"] == [
        {
            "round_from": 3,
            "round_to": 4,
            "faction": "alpha",
            "issue": "core_terms",
            "from_position": "Beta option",
            "to_position": "Alpha option",
            "was_contingent": True,
        }
    ]


@pytest.mark.parametrize(
    ("filename", "expected_dissent"),
    [
        ("run9_alpha_squeezed_live.json", "beta"),
        ("run10_cprime_live.json", "gamma"),
    ],
)
def test_compute_near_miss_flags_fixture_runs_as_near_miss(
    filename: str,
    expected_dissent: str,
):
    result = compute_near_miss(_load_results(filename))

    assert result["near_miss"] is True
    assert result["dissenting_faction"] == expected_dissent
    assert len(result["converging_factions"]) == 2
    assert expected_dissent not in result["converging_factions"]


@pytest.mark.parametrize(
    "filename",
    [
        "run9_beta_squeezed_live.json",
        "run10_bprime_live.json",
    ],
)
def test_compute_near_miss_leaves_non_near_miss_fixtures_false(filename: str):
    result = compute_near_miss(_load_results(filename))

    assert result["near_miss"] is False
    assert result["dissenting_faction"] is None
    assert result["converging_factions"] == []
