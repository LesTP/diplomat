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
| `scenario_viz` | Scenario-only deal-explorer HTML renderer built on verifier math; exposes `render_scenario_html()` and `build_scenario_viz()`. | No |
| `scenario_brief` | Verify-against-brief: `load_brief()` + `check_brief()` measure an analysis's static structure against a declared `features` block (PASS/FAIL per feature); `build_brief_readme()` renders per-scenario auto-doc. Reuses verifier + fitness math. | No |
| `scenario_narrative` | Themed re-skin: `apply_relabel()` renames faction/issue/outcome identifiers under a bijective map; `assert_structure_preserved()` is the value-isomorphism guard; `extract_catalogue_entry()` slices a heading-scoped section from the prose catalogue; `reskin_scenario()` drives one `structured_call` and runs the guard. | Yes (reskin_scenario only) |
| `round_context` | Stdlib-only leaf: `CoachingContext` frozen dataclass + `render_round_context_section()`. Extracted from `modules/persona` in Phase 46 to sever the lone load-time coupling. Re-exported by `modules.persona` for pipeline back-compat. Not in the package `__init__.py` `__all__` — access directly via `from scenario_authoring.round_context import CoachingContext, render_round_context_section`. | No |

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
    # Visualization
    render_scenario_html, build_scenario_viz,
    # Brief
    load_brief, check_brief, BriefResult,
    # Narrative
    reskin_scenario, assert_structure_preserved,
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

async def reskin_scenario(
    analysis: dict[str, Any],
    source_context: str,
    llm_client: Any,
    llm_config: dict[str, Any],
    tier: str = "commodity",
    *,
    domain_context: str = "",
) -> tuple[dict[str, Any], str]
# One structured_call → relabel_map + logrolling + deception_tactics + narrative_md.
# Applies apply_relabel, overlays prose, runs assert_structure_preserved.
# Returns (reskinned_analysis, narrative_md). Raises AssertionError on numeric drift.

def assert_structure_preserved(
    source: dict[str, Any],
    reskinned: dict[str, Any],
    relabel_map: dict[str, dict[str, str]],
) -> None
# Value-isomorphism guard. Raises AssertionError (with descriptive message) on:
# incomplete map, non-bijective map, count mismatch, score drift, BATNA drift,
# coalition_values member/value drift.

def load_brief(path: str | Path) -> dict[str, Any]
# Loads + validates brief.json into {"features": {...}, "goal": str}.
# Rejects unknown feature keys and malformed feature shapes.

def check_brief(analysis: dict[str, Any], brief: dict[str, Any]) -> BriefResult
# Measures analysis structure, returns one FeatureCheck per declared feature.
# Reuses verify_scenario_optimum + scenario_fitness math (no re-derivation).
```

### Brief features (`brief.json`)

A brief declares an optional `goal` (prose) and a non-empty `features` object.
Only declared features are checked; each yields one `FeatureCheck`
(`name, expected, observed, passed`). `BriefResult.all_passed` /
`.failed_features` summarize.

| Feature | Shape | Measured |
|---|---|---|
| `constant_sum` | bool | all deals have equal sum-of-faction-scores |
| `priority_collision` | `none`\|`soft`\|`hard` | `scenario_fitness._priority_collision_level` |
| `no_focal_point` | bool | no "everyone-gets-priority" deal clears all BATNAs |
| `winner_spread` | `{min_per_faction: int}` | min over factions of outright wins across BATNA-clearing deals ≥ min |
| `batna_clearing_count` | `{min?, max?}` | count of deals beating all BATNAs within bounds |
| `no_exact_ties` | bool | no BATNA-clearing deal has its top score shared by ≥2 factions |

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
  clearing count, priority issues, logrolling availability). Pass `--viz`
  or `--viz <path>` to also render the deal-explorer HTML with the scenario
  narrative automatically attached when a matching `.md` file is found.
- Library callers (`scenario_builder`, `scenario_fitness`,
  `game_environment.score_game`) consume `enumerate_deals`,
  `find_pareto_frontier`, `faction_score`, `beats_batna`. Originally lived
  in `tests/self_play/` for historical reasons; moved into the package in
  2026-06-21 (D-58) to eliminate the production → tests coupling.

### `scenario_viz`

- Scenario-only HTML renderer for the deal explorer. It depends only on the
  verifier math and stdlib, so it can be reused from both
  `verify_scenario_optimum` and `scenario_builder` without coupling back into
  the runtime pipeline.
- `build_scenario_viz()` writes HTML to disk; `render_scenario_html()` returns
  the HTML string for embedding or tests.
- **Narrative layout contract (D-63):** the scenario narrative renders as a
  single balanced multi-column flow (`.scenflow` / `columns:2` /
  `column-fill:balance`) that breaks at paragraph boundaries
  (`break-inside:avoid` on paragraphs/bullets/issue-lists, `break-after:avoid`
  on headings). Do NOT revert to a fixed left/right grid that assigns whole
  sections to columns — it leaves an empty column when one side is short. Locked
  by `tests/test_scenario_viz.py::test_narrative_layout_is_balanced`.

### `scenario_narrative`

- `apply_relabel()` does one deep-copy pass over the analysis, renaming
  faction/issue/outcome keys in `factions`, `issues`, `scoring`, `batna`,
  `deception_tactics`, `pressure.asymmetric_clocks`, and
  `coalition_values.members`/`values`. All numeric payoffs pass through
  unchanged. Does NOT validate bijectivity/completeness — that's the guard's job.
- `assert_structure_preserved()` runs after `apply_relabel`: completeness check
  (all source identifiers have a mapping), bijectivity check (no two source ids
  share a new name), structural counts (faction/issue/outcome), scoring
  value-isomorphism, BATNA value-isomorphism, coalition_values member-set +
  value-isomorphism. Raises `AssertionError` with a precise message on the first
  failure.
- `extract_catalogue_entry()` finds the exact heading line, collects all lines
  until the next heading of equal or higher Markdown level (or EOF). Raises
  `ValueError` for a non-heading input or a heading not found in the text.
- `reskin_scenario()` assembles a user prompt from the analysis structure
  (factions, issues, scoring, BATNA, coalition_values) plus `source_context`
  and `domain_context`; calls `structured_call(schema=RESKIN_SCHEMA)` at the
  commodity tier; applies `apply_relabel` + prose overlay; runs the guard;
  returns `(reskinned_analysis, narrative_md)`. PROMPT QUALITY (themed-name
  aptness, prose faithfulness) is tuning-deferred per D-62 — a later supervised
  Refine phase adds prompt-regression coverage.
- Standalone: `apply_relabel`, `assert_structure_preserved`, and
  `extract_catalogue_entry` depend only on stdlib. `reskin_scenario` imports
  `toolkit.structured_llm` lazily (inside the coroutine), so the module is
  importable without toolkit for unit tests.

### `scenario_brief`

- `load_brief()` validates `brief.json` via a per-feature validator table
  (`_FEATURE_VALIDATORS`); adding a feature = one validator entry + one branch
  in `check_brief`.
- `check_brief()` enumerates deals once and reuses `verify_scenario_optimum`
  (`enumerate_deals`, `faction_score`, `beats_batna`, `compute_focal_deal`) +
  `scenario_fitness._priority_collision_level`. No Pareto/BATNA/collision logic
  is re-derived here.
- `compute_focal_deal()` / `focal_deal_clears_batnas()` were extracted from
  `verify_scenario_optimum.main()` (Phase 44) so the focal-point check and the
  CLI report share one implementation.
- Standalone constraint: depends only on `verify_scenario_optimum`,
  `scenario_fitness`, and stdlib — no `toolkit`, no pipeline `modules`.

## Inputs

- **Compiler:** narrative `.md` scenario text + optional batna fractions;
  LLM client (via `toolkit/structured_llm`).
- **Builder:** `ScenarioSpec` JSON file (`--spec`) loaded via `load_spec`.
- **Verifier:** existing `scenario_analysis.json`.
- **Narrative re-skin:** existing `scenario_analysis.json` + optional catalogue
  text (or extracted heading section) + optional domain context; LLM client.

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
- **Pipeline → package direction (Phase 46):** `modules/persona/__init__.py`
  re-imports `CoachingContext` + `render_round_context_section` from
  `scenario_authoring.round_context`. The dependency arrow runs pipeline →
  package, not the reverse. The package itself has zero pipeline imports.
- **Downstream consumer:** `tests/self_play/game_environment.py::score_game`
  reads `scenario_analysis["coalition_values"]` (when present) for partial-
  agreement scoring; `tests/self_play/run_simulation.py` and
  `coached_game.py` import `scenario_compiler` to compile narratives before
  a live game.
- **Upstream `tests/` coupling:** none after D-58. The subsystem is
  importable from any Python entry point with only `src/` on `sys.path`.

## Coalition Path B scoring contract (locked — Phase 47 / D-61)

`tests/self_play/game_environment.py` implements three coalition scoring
paths keyed off `coalition_members` and `coalition_values` in
`scenario_analysis.json`. This contract is locked by
`tests/self_play/test_game_environment_coalition.py` (23 tests). **Do not
change semantics without updating D-61 and the test suite.**

| Condition | Outcome |
|---|---|
| `coalition_members` empty **or** equal to all factions | Full-agreement path — `faction_score()` on `agreed_outcomes`; `coalition_values` ignored |
| Partial `coalition_members` + matching `coalition_values` entry | Members get stated values; excluded factions fall back to BATNA; member absent from entry's `values` dict also falls back to BATNA |
| Partial `coalition_members` + **no** matching `coalition_values` entry | No-deal (`deal_reached=False`, `no_deal_reason="partial_coalition_without_coalition_values"`, all-BATNA) |
| Any deal where a faction score < its BATNA | No-deal (`deal_reached=False`, `no_deal_reason="deal_below_batna_for_some_faction"`) |
| `deal_reached=True` with empty/missing `agreed_outcomes` | Normalized to no-deal (`no_deal_reason="deal_reached_without_agreed_outcomes"`) |

`_find_coalition_value(analysis, members)` matches by **sorted-set equality**
(order-insensitive). Returns `None` on miss, empty list, or missing key.

**Deferred (separate supervised phases, not loop-loopable):**
- Representation rationalization — `coalition_members` schema field alignment
  with builder output conventions
- Builder `coalition_values` emission — auto-generate `coalition_values` entries
  during `scenario_builder.py` search
- Runtime detection — live game coalition detection and routing
- Live mixed-model validation — end-to-end smoke with real LLM providers

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
