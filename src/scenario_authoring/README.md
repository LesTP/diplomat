# scenario_authoring

Self-contained package for constructing, verifying, and profiling negotiation
scenarios for the Diplomat self-play harness.

## Two construction directions

Both directions produce the same canonical artifact bundle:
`scenario_analysis.json` + one `<faction>.txt` persona file per faction.

**Forward (compiler):** narrative `.md` → LLM extraction → analysis JSON.
Operator writes a prose scenario; the compiler calls `toolkit/structured_llm`
to extract factions, issues, scoring tables, BATNAs, and deception tactics.

```bash
python -m scenario_authoring compile \
    --scenario scenarios/water_rights.md \
    --output-dir scenarios/water_rights_v1 \
    --title "Clearwater River Basin"
```

**Reverse (builder):** `ScenarioSpec` JSON → constraint-satisfaction search
→ analysis JSON. Operator declares desired outcome-shape properties (Pareto
count, distribution spread, BATNA gap, logrolling requirement); the builder
searches the combinatorial scoring-table space to find a matching scenario.
No LLM required.

```bash
python -m scenario_authoring build \
    --spec scenarios/specs/multi_pareto.json \
    --output-dir scenarios/multi_pareto_v1 \
    --title "Multi-Pareto Scenario" \
    --verify
```

## Unified CLI

All four subcommands are available via the package dispatcher:

```
python -m scenario_authoring <subcommand> [flags]
```

| Subcommand | Delegates to | Purpose |
|---|---|---|
| `build`   | `scenario_builder.main()` | Reverse-build a scenario from a `ScenarioSpec` |
| `compile` | `scenario_compiler.main()` | Forward-compile a narrative into personas |
| `verify`  | `verify_scenario_optimum.main()` | Enumerate deals + Pareto report for an analysis |
| `brief`   | `scenario_brief.main()` | Verify an analysis against a `brief.json` |

Subcommand flags are passed through unchanged. Run with no subcommand to see
the help message.

## Public API

```python
from scenario_authoring import (
    # Spec types
    ScenarioSpec, IssueSpec, load_spec, dump_spec,
    # Builder
    build_and_save_scenario,
    # Compiler (LLM-dependent)
    analyze_scenario, fill_narrative,
    # Fitness
    compute_fitness, FitnessResult,
    # Analysis utils
    enumerate_deals, find_pareto_frontier, faction_score, beats_batna,
    # Visualization
    render_scenario_html, build_scenario_viz,
    # Brief
    load_brief, check_brief, BriefResult,
    # Constants
    SCENARIO_ANALYSIS_SCHEMA, DEFAULT_BATNA_FRACTION,
)
```

**Standalone constraint:** all non-LLM paths (`build_and_save_scenario`,
`compute_fitness`, `enumerate_deals`, `find_pareto_frontier`, `faction_score`,
`beats_batna`, `render_scenario_html`, `build_scenario_viz`, `load_brief`,
`check_brief`, `CoachingContext`, `render_round_context_section`) import with
only stdlib + sibling modules — no `toolkit`, no pipeline `modules.*`.
`analyze_scenario` and `fill_narrative` import `toolkit` lazily and raise a
clear `ImportError` when it is absent.

## Submodules

| Module | Role | LLM? |
|---|---|---|
| `scenario_compiler` | Forward: narrative → LLM extraction → analysis JSON | Yes |
| `scenario_builder` | Reverse: `ScenarioSpec` → hill-climb search → analysis JSON | No |
| `scenario_spec` | `ScenarioSpec` / `IssueSpec` / `PressureSpec` dataclasses + JSON I/O | No |
| `scenario_fitness` | `compute_fitness(analysis, spec) → FitnessResult` | No |
| `verify_scenario_optimum` | Analysis utilities + CLI payoff report | No |
| `scenario_viz` | Deal-explorer HTML renderer | No |
| `scenario_brief` | Verify-against-brief: `load_brief()` + `check_brief()` | No |
| `round_context` | `CoachingContext` dataclass + `render_round_context_section()` (stdlib-only leaf; re-exported by `modules.persona` for pipeline use) | No |

## Further reading

- **[SCENARIO_GUIDE.md](../../SCENARIO_GUIDE.md)** — operator walkthrough:
  authoring workflows, tuning BATNAs, running the self-play harness with a
  compiled scenario.
- **[ARCH_scenario_authoring.md](../../ARCH_scenario_authoring.md)** —
  architectural contract: full type definitions, schema, coupling notes,
  scaling expectations, and implementation notes per submodule.
