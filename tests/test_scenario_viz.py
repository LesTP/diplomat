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


def test_narrative_layout_is_balanced() -> None:
    """Layout contract (DECISIONS.md D-63): the scenario narrative renders as a
    SINGLE balanced multi-column flow that breaks at paragraph boundaries, never
    the old lopsided fixed left/right grid that left a gaping empty column.
    """
    analysis = _analysis()
    narrative = (
        "# Demo Scenario\n\n"
        "First intro paragraph describing the setup at some length.\n\n"
        "Second intro paragraph with additional detail and framing.\n\n"
        "## The Three Parties\n\n"
        "- Alpha - the north\n"
        "- Beta - the center\n"
        "- Gamma - the frontier\n\n"
        "## The Stakes\n\n"
        "A longer section paragraph describing the stakes at considerable length "
        "so the balancer has real content to distribute across both columns.\n"
    )

    html = render_scenario_html(
        analysis, runs=None, title="Demo", narrative_text=narrative
    )

    # Single balanced multi-column flow.
    assert 'class="scenflow"' in html
    assert "columns:2" in html
    assert "column-fill:balance" in html
    # Reflow breaks at paragraph boundaries, not mid-paragraph.
    assert "break-inside:avoid" in html
    # The old lopsided fixed-grid split must never come back.
    assert "scen2" not in html
    assert "scencol" not in html


def test_multiline_bullets_are_not_truncated() -> None:
    """Wrapped bullet continuation lines must be kept (D-63 family bug:
    md_to_html previously dropped every line not starting with '- ').
    """
    from scenario_authoring.scenario_viz import md_to_html

    md = (
        "## The Three Parties\n\n"
        "- **Gamma** - the military frontier. Has no claim on the heartland;\n"
        "  cares about command of the armed forces and the treasury, and brokers\n"
        "  the Alpha-Beta fight as kingmaker.\n"
    )
    html = md_to_html(md)

    assert "cares about command of the armed forces" in html
    assert "as kingmaker" in html


def test_per_issue_grid_sizes_to_widest_issue() -> None:
    """renderGrid must size columns to the MAX outcome count across issues, so a
    scenario mixing a 2-outcome issue with 3-outcome issues still renders all
    columns (the succ3b two-column regression).
    """
    analysis = {
        "factions": ["alpha", "beta", "gamma"],
        "issues": [
            {"name": "heartland", "outcomes": ["A", "B"], "description": "two"},
            {"name": "treasury", "outcomes": ["A", "B", "C"], "description": "three"},
        ],
        "scoring": {
            "alpha": {"heartland": {"A": 9, "B": 2}, "treasury": {"A": 7, "B": 3, "C": 2}},
            "beta": {"heartland": {"A": 2, "B": 9}, "treasury": {"A": 3, "B": 7, "C": 2}},
            "gamma": {"heartland": {"A": 1, "B": 1}, "treasury": {"A": 2, "B": 2, "C": 8}},
        },
        "batna": {"alpha": 5, "beta": 5, "gamma": 5},
    }
    html = render_scenario_html(analysis, runs=None, title="Mixed")
    assert "Math.max(...ISS.map(i=>i.outcomes.length))" in html
    assert "ISS[0].outcomes.length" not in html
    # Compact column headers: faction-named where outcomes are holder-named,
    # else A/B/C fallback. No per-cell name labels (that made the chart too tall).
    assert "colFac" in html
    assert "String.fromCharCode(65+o)" in html
    assert "Asset goes to:" in html
    assert "[\"A\",\"B\",\"C\",\"D\",\"E\"].slice(0,nOut)" not in html


def test_per_issue_caption_is_dynamic_and_payoff_framed() -> None:
    """For holder-named outcomes the caption names the factions, gives a real
    example, and states it's a payoff, not an asset share (succ3b ask)."""
    analysis = {
        "factions": ["alpha", "beta", "gamma"],
        "issues": [
            {"name": "heartland", "outcomes": ["Alpha-Administered", "Beta-Administered"], "description": "x"},
            {"name": "treasury", "outcomes": ["Alpha-Custody", "Beta-Custody", "Gamma-Custody"], "description": "y"},
        ],
        "scoring": {
            "alpha": {"heartland": {"Alpha-Administered": 9, "Beta-Administered": 2}, "treasury": {"Alpha-Custody": 7, "Beta-Custody": 3, "Gamma-Custody": 2}},
            "beta": {"heartland": {"Alpha-Administered": 2, "Beta-Administered": 9}, "treasury": {"Alpha-Custody": 3, "Beta-Custody": 7, "Gamma-Custody": 2}},
            "gamma": {"heartland": {"Alpha-Administered": 1, "Beta-Administered": 1}, "treasury": {"Alpha-Custody": 2, "Beta-Custody": 2, "Gamma-Custody": 8}},
        },
        "batna": {"alpha": 6, "beta": 6, "gamma": 6},
    }
    html = render_scenario_html(analysis, runs=None, title="Holder-named")

    assert "asset going to" in html
    assert "<b>payoff</b>" in html
    assert "NOT a share of the asset" in html
    # the example is computed from the real data (heartland Alpha-Administered = 9/2/1)
    assert "alpha 9, beta 2, gamma 1" in html
