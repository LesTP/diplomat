# ARCH: Scenario Authoring

## Purpose

Pre-game preparation subsystem for negotiation scenarios. Converts operator
intent — either a narrative description or a constraint spec — into the
`scenario_analysis.json` + per-faction persona `.txt` files that
`run_simulation.py` consumes.

Two construction directions meet at the same canonical artifact format:

- **Forward (compiler):** narrative `.md` → LLM extraction → analysis JSON
- **Reverse (builder):** `ScenarioSpec` JSON → constraint-satisfaction search
  → analysis JSON

Plus shared infrastructure: spec validation, fitness computation, and
post-hoc verification of any analysis JSON's payoff structure.

## Module map

| Submodule | Role | LLM? |
|---|---|---|
| `scenario_compiler` | Forward direction; structured extraction via `toolkit/structured_llm`. Also hosts `fill_narrative()` (LLM-fills `logrolling` + `deception_tactics` into a pre-built analysis). | Yes |
| `scenario_builder` | Reverse direction; random-restart hill-climb with simulated annealing. | No |
| `scenario_spec` | `ScenarioSpec` + `IssueSpec` + `PressureSpec` dataclasses with JSON load/validate. | No |
| `scenario_fitness` | `compute_fitness(analysis, spec) → FitnessResult`; the acceptance gate consumed by the builder's search loop. | No |
| `verify_scenario_optimum` | Pure analysis utilities (`faction_score`, `enumerate_deals`, `find_pareto_frontier`, `beats_batna`, `find_priority_issues`) + a CLI verifier that prints a payoff report for an existing analysis JSON. | No |

## Public API

The package's `__init__.py` re-exports the curated public surface (matches
the `__all__` list). Internal helpers remain importable from their
submodules but are deliberately omitted from the package root.

```python
from scenario_authoring import (
    # Spec types
    ScenarioSpec, IssueSpec, load_spec, dump_spec,
    # Builder
    build_and_save_scenario,
    # Compiler
    analyze_scenario, fill_narrative,
    # Fitness
    compute_fitness, FitnessResult,
    # Analysis utils
    enumerate_deals, find_pareto_frontier, faction_score, beats_batna,
    # Constants
    SCENARIO_ANALYSIS_SCHEMA, DEFAULT_BATNA_FRACTION,
)
```

Submodule entry points NOT re-exported but available for advanced use:
`generate_persona`, `save_persona`, `save_analysis`,
`parse_batna_fractions_json`, `validate_batna_pressure`,
`force_batna_targets`, `max_possible_score`, `build_compiler_system_prompt`,
`find_priority_issues`, plus all `_*` helpers (treat as private).

### Key signatures

```python
async def analyze_scenario(
    llm_client: Any,
    scenario_text: str,
    *,
    batna_fraction: float = DEFAULT_BATNA_FRACTION,
    batna_fractions: dict[str, float] | None = None,
) -> dict[str, Any]
# Returns: scenario_analysis.json-shaped dict; raises on extraction failure.

def build_and_save_scenario(
    spec: ScenarioSpec,
    output_dir: str | Path,
    scenario_title: str = "a reverse-engineered negotiation",
    *,
    max_restarts: int = 1000,
    max_local_moves: int = 200,
    seed: int | None = None,
    debug_search: bool = False,
) -> tuple[dict[str, Any], Path, dict[str, Path]]
# Returns: (analysis dict, analysis.json path, {faction_id: persona.txt path}).
# Raises RuntimeError if all restarts exhaust without a candidate
# satisfying compute_fitness(analysis, spec).satisfies(0.10).

def compute_fitness(analysis: dict[str, Any], spec: ScenarioSpec) -> FitnessResult
# Deterministic. Computes per-target distances + weighted total.
# Cost: O(D^2 * F) where D = product of outcome counts, F = faction count.

async def fill_narrative(
    llm_client: Any,
    analysis: dict[str, Any],
    *,
    domain_context: str | None = None,
) -> dict[str, Any]
# In-place fills logrolling + deception_tactics; returns the modified dict.
```

## Types

```python
@dataclass(frozen=True)
class IssueSpec:
    name: str                       # non-empty
    outcomes: list[str]             # unique, non-empty
    description: str = ""

@dataclass
class PressureSpec:
    round_cost_decay: float = 0.0   # >= 0
    asymmetric_clocks: dict[str, int] = field(default_factory=dict)
    penalty_floor_offset: float = 0.0

@dataclass
class ScenarioSpec:
    factions: list[str]                              # unique, >= 2 in practice
    issues: list[IssueSpec]                          # non-empty
    score_range: tuple[int, int] = (1, 10)
    pareto_count_target: int | tuple[int, int] = 1   # exact or (lo, hi)
    pareto_distribution_spread: float = 0.0          # pstdev of per-faction frontier ranges
    pareto_outcome_diversity: float = 0.0            # distinct-winner fraction (0..1)
    batna_clearing_count_target: int = 0
    batna_to_pareto_gap_pct: float = 0.0             # 0..1
    requires_logrolling: bool = False
    priority_collision: str = "none"                 # none | soft | hard
    pressure: PressureSpec = field(default_factory=PressureSpec)
    pressure_profile: dict[str, str] = field(default_factory=dict)
    asymmetric_batna_fractions: dict[str, float] = field(default_factory=dict)
    target_weights: dict[str, float] = field(default_factory=dict)
    game_mode: str = "mixed"                         # cooperative | competitive | mixed
    seed: int = 0

@dataclass(frozen=True)
class FitnessResult:
    per_target_distance: dict[str, float]
    total_distance: float
    def satisfies(self, tolerance: float) -> bool: ...
```

## Schema: scenario_analysis.json

Defined as `SCENARIO_ANALYSIS_SCHEMA` in `scenario_compiler.py`. Strict mode
(`additionalProperties: False`); all new top-level fields must be added to
`properties` or LLM extraction rejects them.

| Field | Type | Required | Purpose |
|---|---|---|---|
| `factions` | `list[str]` | yes | Faction identifiers |
| `issues` | `list[{name, outcomes, description}]` | yes | Negotiation issues |
| `scoring` | `{faction: {issue: {outcome: number}}}` | yes | Per-faction private point tables |
| `batna` | `{faction: number}` | yes | Per-faction no-deal value |
| `deception_tactics` | `{faction: string}` | yes | Suggested tactic per faction |
| `logrolling` | `list[string]` | yes | Mutually beneficial trades (LLM prose) |
| `game_mode` | `"cooperative" \| "competitive" \| "mixed"` | yes | Scenario mode classification |
| `pressure` | `{round_cost_decay, asymmetric_clocks, penalty_floor_offset}` | yes | Round-pressure mechanics |
| `pressure_profile` | `{time_pressure, external_shock}` (each `low\|medium\|high`) | yes | Coarse pressure ratings |
| `coalition_values` | `list[{members: [string], values: {faction: number}}]` | **no** (Phase 2a) | Optional partial-coalition payoffs for coalition-coercive scenarios |

Validation is upstream-only — at LLM-extraction time via
`toolkit.structured_llm.structured_call(schema=...)`. There is no
`jsonschema.validate()` at load time, so existing files without optional
fields load fine via `json.loads`.

## Implementation notes

### `scenario_compiler`

- `COMPILER_SYSTEM_PROMPT_TEMPLATE` rendered via `.format()` with the BATNA
  fraction substituted in. Phase 2a added a `coalition_values` instruction
  block (LLM populates only when the narrative describes payoffs for
  proper subsets of factions; otherwise empty list).
- `analyze_scenario()` calls `structured_call(schema=SCENARIO_ANALYSIS_SCHEMA)`
  at the `commodity` tier. Default model: `gpt-4.1-mini` (per
  `pipeline.yaml`-equivalent inline config in `__main__`).
- `--fill-narrative-only <analysis.json>` mode (Phase 39) skips compilation
  and calls `fill_narrative()` to layer LLM prose onto a builder-emitted
  stub.
- `force_batna_targets()` post-clamps BATNAs to a target fraction of max
  possible score; used both as a default calibration and as a `--force-batna-
  fraction` override.

### `scenario_builder`

- `build_and_save_scenario()` → `_search_loop()` (random-restart) →
  `_anneal_local()` (Metropolis SA inner loop).
- Each restart calls `_seed_scoring_table()` (biased random init using
  `spec.priority_collision` + `spec.requires_logrolling` to plant likely-
  feasible structure) then runs up to `max_local_moves` SA steps. The
  Metropolis schedule cools geometrically from T=1.0 to T=0.01.
- A candidate is accepted iff `compute_fitness(analysis, spec).satisfies(0.10)`
  AND `pareto_count` matches the spec's range (the latter is a strict gate
  layered on top of the fitness budget).
- Per-restart `_log_search_restart()` emits structured JSON via the
  `scenario_authoring.scenario_builder` logger when `--debug-search` is on.
  Schema: `{event, restart_index, exit_reason, start_total_distance,
  end_total_distance, per_target_distance}`.
- Stubs `logrolling: []` and `coalition_values: []` (Phase 2a); operator
  layers narrative via `scenario_compiler --fill-narrative-only`.

### `scenario_fitness`

- Eleven per-target distance components: `pareto_count`,
  `pareto_outcome_diversity`, `pareto_distribution_spread`,
  `batna_clearing_count`, `batna_to_pareto_gap_pct`, `requires_logrolling`,
  `priority_collision`, `game_mode`, plus per-faction
  `asymmetric_batna_fractions.<faction>` entries.
- Weighted sum into `total_distance`. Default weights: categorical targets
  (logrolling/priority_collision/game_mode) at 0.3; everything else at 1.0.
  `spec.target_weights` overrides per target.
- `satisfies(tolerance)` is `total_distance <= tolerance`. Builder uses
  `tolerance=0.10` (hard-coded).
- Dominant cost: `find_pareto_frontier` is `O(D^2 * F)` per call.

### `scenario_spec`

- Strict JSON `load_spec()`: enforces score_range low < high, positive int
  / range targets, fraction validation (0..1 where applicable), enum sets,
  per-faction key consistency.
- `dump_spec()` writes JSON; preserves field order.

### `verify_scenario_optimum`

- Pure library + CLI. Run as `python -m
  scenario_authoring.verify_scenario_optimum --analysis path/to/analysis.json`
  for a payoff report (max-deal-value, BATNA, Pareto frontier, batna-
  clearing count, priority issues, logrolling availability).
- Library callers (`scenario_builder`, `scenario_fitness`,
  `game_environment.score_game`) consume `enumerate_deals`,
  `find_pareto_frontier`, `faction_score`, `beats_batna`. Originally lived
  in `tests/self_play/` for historical reasons; moved into the package in
  2026-06-21 (D-58) to eliminate the production → tests coupling.

## Inputs

- **Compiler:** narrative `.md` scenario text + optional batna fractions;
  LLM client (via `toolkit/structured_llm`).
- **Builder:** `ScenarioSpec` JSON file (`--spec`) loaded via `load_spec`.
- **Verifier:** existing `scenario_analysis.json`.

## Outputs

All three paths produce the same two-artifact bundle in the operator-chosen
output directory:

- `scenario_analysis.json` — canonical structured form (consumed at runtime
  by `GameEnvironment` and `score_game`)
- `<faction>.txt` (one per faction) — persona file consumed by
  `FileBasedPersona`; embeds the faction's private scoring table + BATNA +
  deception suggestion + logrolling notes + pressure-aware round-context

## State

None. Each entry point is a pure function (or coroutine) of its inputs;
no module-level state, no caches that persist across calls.

## Coupling notes

- **All LLM calls** go through `toolkit/structured_llm.structured_call()` at
  the `commodity` tier. No direct provider SDK imports.
- **No runtime dependency** on Diplomat's pipeline (`Orchestrator`,
  `Pipeline`, `Flow`, transport, persistence). The subsystem produces files;
  `GameEnvironment` reads them.
- **Downstream consumer:** `tests/self_play/game_environment.py::score_game`
  reads `scenario_analysis["coalition_values"]` (when present) for partial-
  agreement scoring; `tests/self_play/run_simulation.py` and
  `coached_game.py` import `scenario_compiler` to compile narratives before
  a live game.
- **Upstream `tests/` coupling:** none after D-58. The subsystem is
  importable from any Python entry point with only `src/` on `sys.path`.

## Logging

- `scenario_authoring.scenario_compiler`: warnings only by default; LLM call
  details flow through `toolkit/structured_llm`'s logger.
- `scenario_authoring.scenario_builder`: per-restart JSON when
  `--debug-search` is on; otherwise quiet at INFO level.
- `scenario_authoring.verify_scenario_optimum`: prints its report to stdout
  (not via logger).

## Scaling expectations (Phases 3 / 41 / 42)

`tools/scenario_builder_scale_probe.py` characterized convergence across
dimensions; see `scenarios/scale_probe_summary.md` for the original data and
`scenarios/c5b_final_singlecell_summary.md` for the post-Phase-42 matrix.

Post-Phase-42 (deterministic builder, relative `batna_clearing_count_target`,
`max_restarts=50`):

| Axis | Behavior |
|---|---|
| Factions (F) | Healthy through F=5; F=6 reliable after Phase 42 C1 F-aware biasing |
| Issues (I) | I≥4 reachable after Phase 42 C5a (relative `batna_clearing_count_target`); 3×4×3 reliable (3/3), 4×4×4 ≈2/3 |
| Outcomes-per-issue (O) | Graceful degradation; 3/3 at 3×3×4, 1/3 at 3×3×6 |

**4+ factions / 4+ issues criterion is MET:** 4×4×4 / D=256 reaches ≥2/3
acceptance (2/3 seeds=3, 4/6 seeds=6). Two structural lessons from Phase 42:

- The original I-axis "cliff" was **spec-semantic, not algorithmic**: a fixed
  absolute `batna_clearing_count_target` becomes infeasible as the deal space
  grows. Relative (fraction-of-D) targets fix it (Phase 42 C5a).
- The builder is **deterministic across processes** (Phase 42 C5b): it consumes
  RNG in fixed `spec.factions` order, not `PYTHONHASHSEED`-dependent set/dict
  iteration order. Probe results are therefore reproducible. A broadened SA
  move neighborhood (multi-cell / issue-scoped / outcome-rank swaps) was tried
  and **made high-D convergence worse**; the single-cell neighborhood is kept.

## Usage Examples

### Compile a narrative scenario

```bash
python -m scenario_authoring.scenario_compiler \
    --scenario scenarios/water_rights.md \
    --output-dir scenarios/water_rights_compiled \
    --title "Clearwater River Basin"
```

Produces `scenario_analysis.json` + `alpha.txt`, `beta.txt`, `gamma.txt`.

### Build a scenario from constraints

```bash
python -m scenario_authoring.scenario_builder \
    --spec scenarios/joint_space_mission_v1/spec.json \
    --output-dir scenarios/jsm1_rebuild \
    --title "Joint Space Mission" \
    --seed 42 \
    --verify
```

The `--verify` flag re-runs `verify_scenario_optimum` on the output and
exits non-zero if the analysis fails sanity checks.

### Fill narrative onto a builder-emitted stub

```bash
python -m scenario_authoring.scenario_compiler \
    --fill-narrative-only scenarios/jsm1_rebuild/scenario_analysis.json \
    --domain-context-file scenarios/joint_space_mission.md
```

Replaces the empty `logrolling: []` and `deception_tactics` stubs in-place
with LLM-authored prose grounded by the domain narrative.

### Verify an analysis

```bash
python -m scenario_authoring.verify_scenario_optimum \
    --analysis scenarios/water_rights_compiled/scenario_analysis.json
```

Prints per-faction max-deal-value, BATNA, Pareto frontier members, batna-
clearing count, priority-issue summary, and logrolling availability.

### Programmatic use

```python
from scenario_authoring import (
    ScenarioSpec, IssueSpec, build_and_save_scenario, compute_fitness,
)

spec = ScenarioSpec(
    factions=["alpha", "beta", "gamma"],
    issues=[
        IssueSpec(name="resource", outcomes=["A", "B", "C"]),
        IssueSpec(name="payment",  outcomes=["A", "B", "C"]),
    ],
    pareto_count_target=(3, 5),
    requires_logrolling=True,
    priority_collision="soft",
    seed=42,
)

analysis, analysis_path, persona_paths = build_and_save_scenario(
    spec, output_dir="scenarios/my_scenario", scenario_title="My Scenario",
)

# Re-score the result
fitness = compute_fitness(analysis, spec)
print(fitness.total_distance, fitness.satisfies(0.10))
```

## Provisional contracts

- **Schema additions are LLM-extraction breaking.** Because the schema is
  used in strict mode (`additionalProperties: False`), any new field must
  be added to `properties` before the compiler will accept it. Existing
  files without the field load fine (no `jsonschema.validate` at load time)
  but extraction of new files will reject the field unless declared.
- **`tolerance=0.10`** in `_candidate_is_acceptable` is hard-coded. If a
  use case needs a tighter or looser budget, this becomes parameterizable.
- **Builder spec language is absolute** (`pareto_count_target=3` means
  "exactly 3 deals on the frontier"). Phase 42's relative-target proposal
  would change this to "3 deals OR 5% of D, whichever is smaller" or
  similar. Spec migration would be required.
