"""Tests for the scenario verification CLI."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from scenario_authoring import verify_scenario_optimum as verify
import scenario_authoring.scenario_viz as scenario_viz


def _analysis() -> dict[str, object]:
    return {
        "factions": ["alpha", "beta"],
        "issues": [
            {"name": "allocation", "outcomes": ["A", "B"], "description": "Allocation"},
            {"name": "payment", "outcomes": ["A", "B"], "description": "Payment"},
        ],
        "scoring": {
            "alpha": {
                "allocation": {"A": 10, "B": 1},
                "payment": {"A": 1, "B": 10},
            },
            "beta": {
                "allocation": {"A": 1, "B": 10},
                "payment": {"A": 10, "B": 1},
            },
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
        "pressure_profile": {
            "time_pressure": "low",
            "external_shock": "low",
        },
    }


def test_main_can_render_optional_viz_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    analysis = _analysis()
    analysis_path = tmp_path / "scenario_analysis.json"
    analysis_path.write_text(json.dumps(analysis), encoding="utf-8")

    rendered: dict[str, object] = {}

    def fake_build_scenario_viz(analysis_arg, output_arg, **kwargs):
        rendered["analysis"] = analysis_arg
        rendered["output"] = output_arg
        rendered["kwargs"] = kwargs
        return output_arg

    monkeypatch.setattr(scenario_viz, "build_scenario_viz", fake_build_scenario_viz)
    monkeypatch.setattr(scenario_viz, "find_narrative", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "verify_scenario_optimum",
            "--analysis",
            str(analysis_path),
            "--viz",
            "--viz-title",
            "Viz Demo",
        ],
    )

    rc = verify.main()

    assert rc == 0
    assert rendered["analysis"] == analysis
    assert rendered["output"] == analysis_path.with_suffix(".html")
    assert rendered["kwargs"]["title"] == "Viz Demo"
    assert rendered["kwargs"]["fallback_title"] == "Viz Demo"
