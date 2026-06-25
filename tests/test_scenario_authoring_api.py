"""Lock in the scenario_authoring package's public API surface.

Ensures the __init__.py's __all__ stays in sync with the curated re-exports
and that downstream consumers can import the canonical names directly from
the package root.
"""

from __future__ import annotations

import scenario_authoring


def test_all_re_exports_resolve() -> None:
    """Every name in __all__ is actually attached to the package."""
    for name in scenario_authoring.__all__:
        assert hasattr(scenario_authoring, name), f"missing public symbol: {name}"


def test_public_surface_is_stable() -> None:
    """Pin the public surface so accidental additions or removals are caught."""
    expected = {
        # Spec types
        "ScenarioSpec",
        "IssueSpec",
        "load_spec",
        "dump_spec",
        # Builder
        "build_and_save_scenario",
        # Compiler
        "analyze_scenario",
        "fill_narrative",
        # Fitness
        "compute_fitness",
        "FitnessResult",
        # Analysis utils
        "enumerate_deals",
        "find_pareto_frontier",
        "faction_score",
        "beats_batna",
        # Visualization
        "render_scenario_html",
        "build_scenario_viz",
        # Brief
        "load_brief",
        "check_brief",
        "BriefResult",
        # Narrative
        "reskin_scenario",
        "assert_structure_preserved",
        # Constants
        "SCENARIO_ANALYSIS_SCHEMA",
        "DEFAULT_BATNA_FRACTION",
    }
    assert set(scenario_authoring.__all__) == expected
