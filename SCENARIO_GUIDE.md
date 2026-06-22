# Scenario Authoring Guide

Operator-facing walkthrough for the `scenario_authoring` subsystem. For
the architectural contract (types, schema, coupling), see
[`ARCH_scenario_authoring.md`](ARCH_scenario_authoring.md). For module-by-
module details, see the same.

---

## What this subsystem does (capabilities snapshot, 2026-06-21)

A pre-game subsystem for constructing negotiation scenarios that the
self-play harness (`tests/self_play/`) consumes. Two directions, one
canonical artifact format, plus shared verification + fitness libraries
and an empirical scaling probe.

### Currently supported scenario classes

| Class | Status | Authoring path |
|---|---|---|
| **Full-cooperation** (everyone agrees on a deal) | ✅ Reliable | Compiler (narrative) or Builder (constraint) |
| **Coalition-coercive** (partial-agreement payoffs matter; Susskind-style) | ✅ Schema + scoring first-class as of Phase 2a | Compiler extracts `coalition_values` from narratives; builder stubs `[]` for operator hand-fill |
| **Distributive (no dominant attractor)** — equal-sum Pareto deals, each favoring a different faction | **DONE** — `succ` scenario (2026-06-22) | Hand-authored constant-sum payoffs; see “Authoring a distributive scenario” below |
| **Hidden-value / adversarial** | Queued | Add scenario class definitions; share compiler/builder |

### What you can do today

**Authoring:**
- Compile a narrative `.md` into structured analysis + per-faction personas via LLM
- Reverse-build a scenario from a `ScenarioSpec` (constraint-driven search; no LLM)
- Layer LLM-authored prose onto a builder-emitted stub via `--fill-narrative-only`
- Compose with the **scale-aware spec language** introduced in Phase 42 C2:
  `pareto_count_target` accepts either absolute counts (`(3, 5)`) or
  fractions of deal space (`(0.05, 0.15)` = 5–15% of D)
- Hand-edit a compiled analysis (BATNAs, pressure, coalition_values) and
  regenerate personas without re-running the compiler

**Verification + characterization:**
- `verify_scenario_optimum` — payoff-structure report for any
  `scenario_analysis.json` (Pareto frontier, batna-clearing count,
  priority issues, logrolling availability)
- `verify_scenario_pressure` — round-pressure invariants check
- `tools/scenario_builder_scale_probe.py` — characterize builder
  convergence + wall-clock across (F, I, O) cells; outputs JSONL +
  auto-summary markdown; serves as a regression gate for future
  algorithm changes

**Scoring** (in `GameEnvironment.score_game`):
- Full-agreement deals: standard faction-score on agreed outcomes
- Partial coalitions with `coalition_values` match: members get their
  values; excluded factions fall back to BATNA
- Partial coalitions without matching values: treated as no-deal (all
  BATNA, conservative)
- No deal: all BATNA
- Competitive ranking: `faction_ranks` (section 3.5) ranks factions by achieved score within the game (1=highest); the per-game lens that `rank_aggregator` pools into a cross-model leaderboard

### Programmatic surface

```python
from scenario_authoring import (
    # Spec types
    ScenarioSpec, IssueSpec, load_spec, dump_spec,
    # Construction entry points
    build_and_save_scenario,           # constraint-driven (builder)
    analyze_scenario, fill_narrative,  # narrative-driven (compiler)
    # Fitness
    compute_fitness, FitnessResult,
    # Analysis utilities
    enumerate_deals, find_pareto_frontier, faction_score, beats_batna,
    # Constants
    SCENARIO_ANALYSIS_SCHEMA, DEFAULT_BATNA_FRACTION,
)
```

15 curated symbols pinned by a contract test. Internal helpers
(`generate_persona`, `save_persona`, `force_batna_targets`,
`parse_batna_fractions_json`, etc.) remain importable from submodules
but are deliberately not re-exported.

### Empirical scaling characteristics

From `scenarios/scale_probe_summary_post_phase42_absolute.md` (post-Phase-42
data, absolute `pareto_count_target=(3, 5)`):

| Axis | What works reliably | Where it breaks |
|---|---|---|
| **Factions (F)** | F=3, 4, 5, **6** (Phase 42 C1 fixed the F=6 cliff) | F=7+ unmeasured |
| **Issues (I)** | I=3 reliable; **I=4 reachable** with relative `batna_clearing_count_target` (Phase 42 C5a) | I=5+ unmeasured under default targets |
| **Outcomes (O)** | O=3, 4 healthy | O=5: 2/3 acceptance; O=6: 1/3 acceptance (graceful degradation) |
| **Wall-clock** | ~25s for 4×4×4 (D=256); ~65s for 3×6×3 (D=729) | Phase 42 C3 Skyline algorithm dropped these ~10× from the pre-Phase-42 baseline |

PROJECT.md's "scales to 4+ factions / 4+ issues" success criterion:
**MET (Phase 42)** — 4 factions ✅ (C1) and 4 issues ✅ (C5a relative
`batna_clearing_count_target`); 4×4×4 reaches ≥2/3 acceptance with the
deterministic builder (C5b). See `DECISIONS.md` D-59.

### What's NOT yet supported

- **4+ issue scenarios with default fitness targets** — use relative
  `batna_clearing_count_target` (fraction of D) instead of absolute counts;
  this is the Phase 42 C5a fix that made I≥4 reliable
- **Runtime partial-coalition detection during gameplay** — today
  `score_game` (post-game scorer) is the only consumer of `coalition_values`.
  Phase 2b would surface coalition formation in `RoundSteppedFlow` so
  agents/operator can see it forming, not just at the end
- **Builder emission of non-empty `coalition_values`** — currently always
  stubbed `[]`; operator hand-edits the JSON for coalition-coercive specs.
  Phase 42 / Phase 2b deferred item: `ScenarioSpec.requires_coalition_values`
  flag
- **`fill_narrative()` extension for `coalition_values`** — today only
  fills `logrolling` and `deception_tactics`. Deferred to Phase 2b

### Newly answerable benchmark questions (after Phase 2a)

These were not cleanly answerable before this session's work; coalition
support was hand-patched into scoring tables of synthetic issues, and the
scoring engine treated agreement as binary deal/no-deal:

- **"Does model X get excluded by others forming a coalition without it?"**
  `score_game` now returns distinct outcomes for partial-coalition formation
  (AB-against-C scored differently from no-deal)
- **"Which models recognize partial-coalition Pareto outcomes?"** Scorable
  distinctly from full-agreement Pareto deals
- **"What's a model's strategic-refusal pattern on coalition-coercive
  scenarios?"** Observable in scoring + process signatures
- **"Does the agreeableness-bias problem hold when partial-coalition
  payoffs are first-class data?"** Mixed-model runs can now produce
  "X wins via coalition AB without Y" instead of always deadlocking at
  BATNA — the structural blocker on RESEARCH_NOTES Note 2 Path B is
  cleared at the schema level

---

## When to use what

There are two ways to author a scenario for the harness. Pick by what you
have on hand:

| If you have… | …use | because |
|---|---|---|
| A narrative description of the scenario (parties, interests, payoffs implied or stated) | **Compiler** | LLM extracts the structured form for you |
| A precise idea of the scenario's *properties* (Pareto count, BATNA gap, logrolling required, priority collision pattern) without specific narrative content | **Builder** | Constraint-satisfaction search finds a scoring table matching your targets |
| A builder-emitted analysis missing narrative prose (`logrolling`, `deception_tactics` empty) | **Compiler in `--fill-narrative-only` mode** | LLM authors the prose without re-running the compile |

Both directions produce the same `scenario_analysis.json` + per-faction
persona `.txt` bundle; downstream consumers don't care which path produced
them.

## The narrative path (compiler)

Authoring loop:

1. Write the scenario as Markdown in `scenarios/<name>.md`. Describe:
   - The factions and their identifiers (lowercase recommended)
   - The negotiation issues + possible outcomes per issue
   - Each faction's stated or implied interests / priorities
   - BATNAs (no-deal value) when narrative implies them; the compiler can
     also infer
   - Time pressure / external shock cues if relevant
   - For coalition-coercive scenarios (Susskind-style): payoffs for
     proper subsets of factions (e.g., "A+B coalition produces 118")
2. Compile:
   ```bash
   python -m scenario_authoring.scenario_compiler \
       --scenario scenarios/<name>.md \
       --output-dir scenarios/<name>_v1 \
       --title "<Human-readable scenario title>"
   ```
3. Inspect `scenarios/<name>_v1/scenario_analysis.json` — verify factions,
   issues, scoring tables, BATNAs, and (for coalition scenarios)
   `coalition_values` populated correctly.
4. Verify the payoff structure:
   ```bash
   python -m scenario_authoring.verify_scenario_optimum \
       --analysis scenarios/<name>_v1/scenario_analysis.json
   ```
   Prints per-faction max-deal-value, BATNA, Pareto frontier, batna-
   clearing count, priority issues, and logrolling availability. Use this
   as a sanity check that the LLM didn't produce a degenerate scenario
   (e.g., everyone's optimum is the same outcome).

### Tuning BATNAs after compile

The compiler's default BATNA fraction is 50% of each faction's maximum
possible score. To override:

```bash
# Symmetric fraction across all factions:
python -m scenario_authoring.scenario_compiler \
    --scenario scenarios/<name>.md \
    --output-dir scenarios/<name>_v1 \
    --batna-fraction 0.65

# Per-faction fractions:
python -m scenario_authoring.scenario_compiler \
    --scenario scenarios/<name>.md \
    --output-dir scenarios/<name>_v1 \
    --batna-fractions '{"alpha": 0.70, "beta": 0.40, "gamma": 0.50}'

# Force a literal BATNA (overrides narrative AND fraction):
python -m scenario_authoring.scenario_compiler \
    --scenario scenarios/<name>.md \
    --output-dir scenarios/<name>_v1 \
    --force-batna-fraction 0.0
```

`--force-batna-fraction 0.0` is the right call when the narrative says
"alone: 0" or similar (e.g., coalition-coercive scenarios where solo
factions produce nothing).

### When the compiler misses structure

The LLM sometimes drops operator-relevant detail (BATNAs not matching
narrative, pressure mechanics not extracted). For small fixes, hand-edit
the JSON directly:

```python
import json
from pathlib import Path
from scenario_authoring import generate_persona, save_persona  # internal helpers

p = Path("scenarios/<name>_v1/scenario_analysis.json")
a = json.loads(p.read_text())

# Manual edits, e.g.:
a["batna"] = {"a": 0, "b": 0, "c": 0}
a["pressure"]["round_cost_decay"] = 0

p.write_text(json.dumps(a, indent=2, sort_keys=True))

# Regenerate personas to reflect the JSON edits:
for fid in a["factions"]:
    save_persona(fid, generate_persona(fid, a, "<title>"),
                 p.parent)
```

Document the hand-edits in a sibling `NOTES.md` so the rationale survives
re-compilation. See `scenarios/three_party_coalition_v1/NOTES.md` for an
example.

## The constraint path (builder)

When you know what *kind* of scenario you want (e.g., "3-Pareto, soft
priority-collision, logrolling required") but not the specific narrative:

1. Write a `ScenarioSpec` as JSON. Minimum viable spec:
   ```json
   {
     "factions": ["alpha", "beta", "gamma"],
     "issues": [
       { "name": "issue_1", "outcomes": ["A", "B", "C"] },
       { "name": "issue_2", "outcomes": ["A", "B", "C"] },
       { "name": "issue_3", "outcomes": ["A", "B", "C"] }
     ],
     "pareto_count_target": [3, 5],
     "requires_logrolling": true,
     "priority_collision": "soft",
     "seed": 42
   }
   ```
   See [`ARCH_scenario_authoring.md`](ARCH_scenario_authoring.md) §Types
   for every available field. The `joint_space_mission_v1/spec.json` file
   is a complete worked example.
2. Build:
   ```bash
   python -m scenario_authoring.scenario_builder \
       --spec scenarios/<name>_spec.json \
       --output-dir scenarios/<name>_v1 \
       --title "<Human-readable title>" \
       --verify
   ```
   The builder runs a random-restart hill-climb with simulated annealing;
   each restart freshly seeds a biased random scoring table and tries to
   converge on a table whose Pareto / BATNA / logrolling structure matches
   the spec.
3. The builder emits `logrolling: []` and `coalition_values: []` as stubs.
   Layer narrative prose onto them via:
   ```bash
   python -m scenario_authoring.scenario_compiler \
       --fill-narrative-only scenarios/<name>_v1/scenario_analysis.json \
       --domain-context-file scenarios/<name>_domain_context.md
   ```
   The `--domain-context-file` is optional but improves the LLM's prose
   quality by giving it real-world framing.
4. Verify as in the narrative path.

### When the builder fails to converge

`RuntimeError: scenario search failed to produce an acceptable candidate`
after `--max-restarts` (default 1000). Common causes + remedies:

| Cause | Symptom | Remedy |
|---|---|---|
| Spec is infeasible | All restarts exhaust quickly | Relax a target. Most common: `pareto_count_target=(3, 5)` with large deal space → frontier exceeds 5 naturally. See "Scaling" below |
| `requires_logrolling=true` with high faction count | Few/no restarts accept | The logrolling target wants every faction to do well in one deal; gets harder as F grows. Try `target_weights={"requires_logrolling": 0.5}` |
| `priority_collision="hard"` with non-divisible faction count | Restart count exhausts | Hard collision requires all factions to share one priority issue; can be infeasible with certain score-range / issue-count combos |
| Conflicting targets (e.g., low `pareto_distribution_spread` + tight `pareto_count_target`) | Slow convergence, then fail | Loosen one target; or set `target_weights` to deprioritize the less-essential one |

`--debug-search` emits one JSON record per restart with
`per_target_distance` showing which target(s) the search is failing on:
```bash
python -m scenario_authoring.scenario_builder \
    --spec scenarios/<name>_spec.json \
    --output-dir /tmp/scenario_debug \
    --debug-search --max-iterations 20
```

## Coalition-coercive scenarios

Susskind-style three-party coalition games, where partial coalitions
(e.g., A+B leaves C out) produce different payoffs from full agreement,
are first-class as of Phase 2a (2026-06-20).

**In the narrative (.md):** describe payoffs for proper subsets of
factions explicitly. Format that compiles well:

```markdown
## Coalition Values (confirmed payoffs)
- A alone: 0
- B alone: 0
- C alone: 0
- A + B coalition: 118
- A + C coalition: 84
- B + C coalition: 50
- A + B + C (grand coalition): 121
```

The compiler extracts these into `scenario_analysis.json::coalition_values`:

```json
"coalition_values": [
  { "members": ["a", "b"],      "values": { "a": 6, "b": 7 } },
  { "members": ["a", "c"],      "values": { "a": 5, "c": 6 } },
  { "members": ["b", "c"],      "values": { "b": 4, "c": 3 } },
  { "members": ["a", "b", "c"], "values": { "a": 7, "b": 6, "c": 5 } }
]
```

Note: the 1-10 score range compresses the narrative's actual values. The
*ordering* is what matters for negotiation dynamics; absolute magnitudes
get rescaled.

**At scoring time:** when the LLM scorer detects a strict subset of
factions converged (`coalition_members` in its response), the scoring
engine looks up that subset in `coalition_values`:
- Match found → members get their stated values; excluded factions fall
  back to BATNA.
- No match → treated as no-deal; everyone at BATNA.

For full-cooperation scenarios (Water Rights, Joint Space Mission), leave
`coalition_values` empty or omit it. Schema is backward-compatible.

**In a spec (builder):** `coalition_values` is always stubbed `[]`.
Future Phase 42 work will add `ScenarioSpec.requires_coalition_values`
for builder-emitted coalition scenarios; today, operator hand-edits the
JSON to populate it.

## Authoring a distributive scenario (no dominant attractor)

The `succ` scenario (`scenarios/succession_division_v1/`, narrative
`scenarios/succession_division.md`) is the reference distributive scenario,
built for the section 3.5 rank-among-factions lens. Unlike `jsm1`/`wrbeta` -
where one deal is both highest-sum and most balanced, so every model converges
there (zero outcome diversity) - a distributive scenario has multiple
(near-)equal-sum Pareto deals, each favoring a different faction, so *which*
deal is agreed becomes a genuine contest and a stronger negotiator claims more.

**Design principle - use (near-)constant-sum payoffs.** If every outcome of
every issue sums to the same constant across factions, then every deal sums to
the same total, which makes Pareto domination impossible - so there is no
dominant attractor by construction (the cleanest guarantee against the `jsm1`
failure mode). `succ` does exactly this: each outcome on each of 3 issues sums
to 12 across the 3 factions, so every deal sums to 36 and all 27 deals are on
the frontier, none dominating another.

**Remove the equal-split Schelling point.** A symmetric constant-sum game has a
perfect equal-split deal (12/12/12) that models gravitate to. Break it with a
*compensated internal shift* - redistribute points within one outcome (keeping
that outcome's sum constant) so no deal lands on an exact tie, without
reintroducing domination. In `succ` this yields 6 BATNA-clearing contest deals
with a balanced 2/2/2 winner spread (alpha/beta/gamma each win two).

**Author + verify loop** (hand-authoring is recommended - the equal-sum property
is not a `ScenarioSpec` fitness target):
1. Hand-write `scenario_analysis.json` with constant-sum `scoring` and BATNAs
   that carve out a balanced contest set (corners where one faction dominates
   should *not* clear all BATNAs).
2. Verify with `verify_scenario_optimum --top-n 27` plus a frontier/winner
   enumeration: confirm near-equal sums, distinct per-deal winners, no exact ties.
3. Register the scenario tag in `tools/ablation_multi.sh` `scenario_paths()`.

**Run a model comparison on it** (what the distributive scenario unlocks):
```bash
bash tools/ablation_multi.sh runrotate 'M1,M2,M3' succ bare 3   # seat-rotated mixed-model games
python -m tests.self_play.rank_aggregator                       # mean_rank leaderboard
```
See `CLI_REFERENCE.md` for the full dispatcher + aggregator reference and
`ASSESSMENT.md` section 3.5 for the scoring lens.

## Scaling expectations

Original Phase 3 matrix sweep (`scenarios/scale_probe_summary.md`) with a
**fixed absolute** `pareto_count_target=(3, 5)` showed hard cliffs. Phase 42
resolved them; post-Phase-42 data is in
`scenarios/c5b_final_singlecell_summary.md`.

| Axis | Post-Phase-42 (relative targets, deterministic builder) |
|---|---|
| **Factions (F)** | 3–5 healthy; 6 reliable (C1 F-aware biasing) |
| **Issues (I)** | I ≥ 4 reachable with relative `batna_clearing_count_target` (3×4×3 reliable) |
| **Outcomes-per-issue (O)** | Up to ~4 healthy; 5, 6 gradual degradation |
| **Balanced 4×4×4 (D=256)** | ≈2/3 acceptance — PROJECT.md criterion MET |

**Practical authoring rules of thumb (post-Phase-42):**

- Use **relative** targets at higher dimensions: set `batna_clearing_count_target`
  (and optionally `pareto_count_target`) as a *fraction of the deal space*
  (a float in (0, 1], e.g. `0.20`) instead of an absolute count. Absolute
  counts become structurally infeasible as the deal space grows — this was the
  real cause of the old I-axis "cliff", not the search algorithm.
- 4×4×4 is reliable; 4 factions / 4 issues is the validated ceiling. Beyond
  that (5×5×5+) is unmeasured/out of scope — drop other axes if you push one.
- If a spec you believe is feasible won't converge, prefer relativizing its
  count targets before loosening ranges.
- The builder is deterministic: same seed → same scenario, reproducibly across
  machines and processes.

## Probing scaling for new dimensions

If you want empirical data on a specific dimension combo before committing
to it for real scenarios:

```bash
python tools/scenario_builder_scale_probe.py \
    --cells 4x4x4,5x3x3,5x4x4 \
    --seeds 5 \
    --max-restarts 50 \
    --output /tmp/my_probe.jsonl \
    --summary /tmp/my_probe_summary.md
```

The probe runs the builder against synthetic specs at the listed
dimensions, captures convergence + wall-clock + final fitness, and emits
a JSONL + summary markdown. See
[`scenarios/scale_probe_summary.md`](scenarios/scale_probe_summary.md) for
the canonical sweep + findings.

## File layout reference

```
scenarios/                                  # Production scenario data
    <name>.md                               # Narrative source
    <name>_v1/                              # Compiled output
        scenario_analysis.json              # Canonical structured form
        <faction>.txt  (one per faction)    # Persona files
        spec.json                           # Builder spec (if builder-authored)
        NOTES.md                            # Operator notes (optional)
    scale_probe_results.jsonl               # Phase 3 sweep data
    scale_probe_summary.md                  # Phase 3 sweep findings

src/scenario_authoring/                     # Subsystem code
    __init__.py                             # Curated public API
    scenario_compiler.py                    # Forward direction (LLM)
    scenario_builder.py                     # Reverse direction (search)
    scenario_spec.py                        # Spec types
    scenario_fitness.py                     # Fitness function
    verify_scenario_optimum.py              # Analysis utilities + CLI

tools/
    scenario_builder_scale_probe.py         # Phase 3 scaling probe
    recompile_batnas.py                     # Re-derive BATNAs without re-compile
    backfill_pareto.py / rescore_run.py /   # Post-hoc analysis helpers
    viz.py / etc.
```

## Quick reference card

| Goal | Command |
|---|---|
| Compile a narrative | `python -m scenario_authoring.scenario_compiler --scenario <md> --output-dir <dir>` |
| Build from constraints | `python -m scenario_authoring.scenario_builder --spec <json> --output-dir <dir> --verify` |
| Layer prose on a stub | `python -m scenario_authoring.scenario_compiler --fill-narrative-only <analysis> [--domain-context-file <md>]` |
| Verify payoff structure | `python -m scenario_authoring.verify_scenario_optimum --analysis <analysis>` |
| Probe scaling | `python tools/scenario_builder_scale_probe.py --cells <FxIxO> --seeds N --output <jsonl>` |
| Re-derive BATNAs | `python tools/recompile_batnas.py --source <dir> --output-dir <dir> --fractions <json>` |

## Further reading

- [`ARCH_scenario_authoring.md`](ARCH_scenario_authoring.md) — types, schema, public API
- [`scenarios/scale_probe_summary.md`](scenarios/scale_probe_summary.md) — empirical scaling data (pre-Phase-42 baseline)
- [`scenarios/scale_probe_summary_post_phase42_absolute.md`](scenarios/scale_probe_summary_post_phase42_absolute.md) — post-Phase-42 results + Phase 42 C5 hand-off
- [`CLI_REFERENCE.md`](CLI_REFERENCE.md) — all subcommand flags + defaults
- [`Multi-Party Negotiation Scenarios.md`](Multi-Party%20Negotiation%20Scenarios.md) — source catalogue (Harvard PON, historical congresses, Susskind coalition templates)
