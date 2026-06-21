"""Scenario authoring subsystem for Diplomat.

Forward (LLM-driven, narrative -> tables) and reverse (constraint-driven,
spec -> tables) construction of negotiation scenarios, plus the fitness and
verification helpers they share. See SCENARIO_GUIDE.md (Phase 4) for the
operator-facing workflow.

This module re-exports the deliberate public API. Internal helpers remain
importable directly from their submodules; reach into a submodule only if
you need an internal helper not re-exported here.

Public surface:
    Spec types       : ScenarioSpec, IssueSpec, load_spec, dump_spec
    Builder          : build_and_save_scenario
    Compiler         : analyze_scenario, fill_narrative
    Fitness          : compute_fitness, FitnessResult
    Analysis utils   : enumerate_deals, find_pareto_frontier, faction_score,
                       beats_batna
    Constants        : SCENARIO_ANALYSIS_SCHEMA, DEFAULT_BATNA_FRACTION
"""

from scenario_authoring.scenario_builder import build_and_save_scenario
from scenario_authoring.scenario_compiler import (
    DEFAULT_BATNA_FRACTION,
    SCENARIO_ANALYSIS_SCHEMA,
    analyze_scenario,
    fill_narrative,
)
from scenario_authoring.scenario_fitness import FitnessResult, compute_fitness
from scenario_authoring.scenario_spec import (
    IssueSpec,
    ScenarioSpec,
    dump_spec,
    load_spec,
)
from scenario_authoring.verify_scenario_optimum import (
    beats_batna,
    enumerate_deals,
    faction_score,
    find_pareto_frontier,
)

__all__ = [
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
    # Constants
    "SCENARIO_ANALYSIS_SCHEMA",
    "DEFAULT_BATNA_FRACTION",
]
