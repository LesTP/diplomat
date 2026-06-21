# Scenario Authoring Guide

Operator-facing walkthrough for the `scenario_authoring` subsystem. For
the architectural contract (types, schema, coupling), see
[`ARCH_scenario_authoring.md`](ARCH_scenario_authoring.md). For module-by-
module details, see the same.

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

## Scaling expectations

Empirical scaling data from Phase 3's matrix sweep
(`scenarios/scale_probe_summary.md`). With fixed
`pareto_count_target=(3, 5)`:

| Axis | What works | What breaks |
|---|---|---|
| **Factions (F)** | 3, 4, 5 healthy | 6 fragile (1/3 acceptance) |
| **Issues (I)** | 3 only | I ≥ 4 fails 0/3 — the natural Pareto frontier grows with deal space, fixed target becomes infeasible |
| **Outcomes-per-issue (O)** | Up to ~4 healthy | 5, 6 gradual degradation |
| **Balanced (e.g., 4×4×4)** | — | Fails 0/3 |

**Practical authoring rules of thumb (pre-Phase-42):**

- Stay at I ≤ 3 (issues per scenario)
- F ≤ 5 (factions)
- O ≤ 4 (outcomes per issue) for reliable convergence
- If you need more dimension on one axis, drop others
- If the builder fails to converge on a spec you believe is feasible:
  loosen `pareto_count_target` (try a wider range, e.g., `[3, 12]`) — the
  frontier may simply be bigger than expected

Phase 42 (queued; gated on `PHASE_42_PLAN.md`) will add scale-aware spec
language (`pareto_count_target` as a fraction of deal space) which is
expected to make 4×4×4 and beyond reliably convergent without changing
the algorithm.

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
