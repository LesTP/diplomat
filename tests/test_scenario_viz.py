from __future__ import annotations

import json
from pathlib import Path

from scenario_authoring.scenario_viz import (
    build_deals,
    build_data,
    build_scenario_viz,
    render_scenario_html,
)
from scenario_authoring.verify_scenario_optimum import enumerate_deals, find_pareto_frontier


def _analysis() -> dict[str, object]:
    return {
        "factions": ["alpha", "beta", "gamma"],
        "issues": [
            {"name": "allocation", "outcomes": ["A", "B"], "description": "Allocation"},
            {"name": "payment", "outcomes": ["A", "B"], "description": "Payment"},
        ],
        "scoring": {
            "alpha": {"allocation": {"A": 9, "B": 1}, "payment": {"A": 1, "B": 10}},
            "beta": {"allocation": {"A": 2, "B": 8}, "payment": {"A": 10, "B": 1}},
            "gamma": {"allocation": {"A": 7, "B": 3}, "payment": {"A": 2, "B": 6}},
        },
        "batna": {"alpha": 5, "beta": 5, "gamma": 4},
    }


def test_render_scenario_html_works_with_empty_runs() -> None:
    analysis = _analysis()

    html_none = render_scenario_html(analysis, runs=None, title="Demo")
    html_empty = render_scenario_html(analysis, runs=[], title="Demo")

    assert "A · Deal explorer" in html_none
    assert "Surplus-share ternary" in html_none
    assert "Demo" in html_none
    assert "0 run(s)" in html_none
    assert "0 run(s)" in html_empty


def test_build_deals_matches_pareto_frontier() -> None:
    analysis = _analysis()
    deals = build_deals(analysis)
    frontier = find_pareto_frontier(analysis, enumerate_deals(analysis))

    from_build = {
        json.dumps(deal["outcomes"], sort_keys=True)
        for deal in deals
        if deal["pareto"]
    }
    from_verify = {json.dumps(deal, sort_keys=True) for deal, _ in frontier}

    assert from_build == from_verify


def test_build_data_accepts_missing_runs_and_sets_bottleneck() -> None:
    analysis = _analysis()

    data = build_data(analysis, runs=None, bottleneck="allocation")

    assert data["runs"] == []
    assert data["bottleneck"] == "allocation"
    assert len(data["deals"]) == 4


def test_build_scenario_viz_writes_file(tmp_path: Path) -> None:
    analysis = _analysis()
    output = tmp_path / "viz.html"

    written = build_scenario_viz(analysis, output, title="Demo Viz", bottleneck="payment")
    text = output.read_text(encoding="utf-8")

    assert written == output
    assert output.exists()
    assert "Demo Viz" in text
    assert "Deal space" in text
