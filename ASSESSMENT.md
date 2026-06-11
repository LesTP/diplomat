# ASSESSMENT — Negotiation skill, scoring, and workstream organization

> Conceptual rationale + scoring framework + the three workstream blocks
> that organize all current and future work. This is the *why* and *how
> we measure*; tactical items live in `NEXT_STEPS.md` (tagged A/B/C per
> §5 below). Architecture lives in `ARCHITECTURE.md` (and per-module
> `ARCH_*.md`). Operational tuning lives in `TUNING.md`.

---

## 1. Why this exists — the calculation-vs-negotiation tension

If you fully specify a negotiation game — everyone's utility function,
BATNAs, possible outcomes, payoffs — the "answer" is calculable. Nash
bargaining, Shapley values, the Pareto frontier are all just mechanism
design. Skilled negotiation collapses to "find the equilibrium and
propose it." Two rational agents with full information will converge on
the same point.

That collapse depends on three assumptions: (a) full information about
everyone's utilities, (b) rational actors, (c) costless commitment.
Remove any one and *calculation alone is no longer sufficient*. Real
negotiation persists because all three fail in practice:

- **Asymmetric information.** You don't know others' utilities; you can
  only infer them from what they say and do.
- **Bounded rationality.** Even with full information, agents make
  framing-dependent choices, anchor on opening positions, and discount
  the future.
- **Signaling and misrepresentation.** Stated preferences can be true,
  false, or strategically ambiguous. Bluffing has real expected value.
- **Trust and reputation.** What you say in round 1 affects what's
  believed in round 4. Broken promises poison later rounds.
- **Coalition dynamics.** Multi-party adds the meta-game of who allies
  with whom and on what terms.

Diplomat preserves this gap intentionally. Each agent gets a *private*
scoring table and *private* BATNA. The scenario compiler emits a public
narrative + private per-faction analysis. Deception tactics are
configurable. Agents must communicate over multiple rounds to surface
joint value. The gap between "what a perfect calculator would do given
full information" and "what an LLM agent can actually achieve given its
private view + finite messages" is where negotiation skill lives.

This is also why agents in Run 8 failed to find the Pareto-optimal
Shared deal (alpha=14, beta=20, gamma=22, all comfortably above BATNAs
of 11/8/10). The deal *existed*. Calculation could find it. The agents
didn't propose it because they lacked the negotiation skill to surface
existing-but-hidden value through communication.

---

## 2. What "negotiating well" means — dimensions of skill

| Dimension | What "good" looks like | Where in Diplomat |
|---|---|---|
| **Preference elicitation** | Inferring others' utilities from what they say without revealing your own | Analyst module (read state + transcript → infer opponent priorities) |
| **Signaling** | Telegraphing your priorities credibly when it helps, vaguely when it hurts | Persona + Generation prompts |
| **Anchoring** | Opening positions that bend the equilibrium toward you | Persona (currently a "don't accept first framework" rule; arguably over-anchoring) |
| **Concession sequencing** | Trading on low-value items to extract high-value ones (logrolling) | Persona scoring table + analyst's leverage-points output |
| **Threat credibility** | Making BATNA-walking-away claims believable | Persona BATNA + analyst's threat-level output |
| **Coalition arithmetic** | When 2-of-N lets you exclude the others, who do you ally with | State manager coalitions + analyst |
| **Time pressure handling** | When to hold vs. settle as deadlines approach | Persona endgame markers (PENULTIMATE / FINAL ROUND) |
| **Reputation management** | Avoiding broken promises that poison later rounds | State manager promise tracking + reconciler fulfillment paths |
| **Deception detection** | Recognizing when others are bluffing about BATNAs or commitments | Adversarial reader |
| **Persuasion** | Getting others to update positions based on arguments, not just trades | Generation quality + analyst's response to it |

A perfectly calculating but communicatively naive agent will *lose* to
an agent with worse math but better signaling and persuasion. That's the
target.

---

## 3. How we measure "winning" — four scoring lenses

Each lens captures a different aspect. None alone is complete; pick by
the question you're answering.

### 3.1 BATNA-relative score (currently implemented)

```
score_normalized = (score_achieved - BATNA) / (max_possible - BATNA)
```

- Range: `(-∞, 1.0]`. Positive = beat BATNA. 1.0 = max possible.
- Captures: "Did you do better than walking away?"
- Status: ✓ Implemented in `tests/self_play/game_environment.py::score_game`.
  Outputs WIN if score > BATNA, LOSE otherwise.
- Limitation: doesn't distinguish "barely beat BATNA" from "found the
  optimum." Two agents both above BATNA both "win."

### 3.2 Pareto efficiency + no-deal-aware surplus share (implemented)

```
pareto_efficiency = sum(achieved_scores) / max_pareto_sum
negotiated_surplus_share =
  sum(score_achieved - BATNA) / (max_pareto_sum - sum(BATNAs))
```

where `max_pareto_sum` is the highest aggregate score over all deals
that beat every faction's BATNA.

- Range: `pareto_efficiency` is usually `[0, 1.0]`; scorer/table
  mismatches can exceed 1.0 and should be investigated rather than
  silently clamped. `negotiated_surplus_share` reads `0.0` at the
  no-deal/BATNA floor and `1.0` at the deterministic Pareto optimum.
- Captures: "Did the group leave value on the table?"
- Status: ✓ Implemented in
  `tests/self_play/game_environment.py:548` and
  `tests/self_play/game_environment.py:684`. The scorer output now
  includes `achieved_score_sum`, `max_pareto_sum`, and
  `pareto_efficiency`, plus baseline-normalized companion fields:
  `sum_batnas`, `faction_deltas`, `delta_above_batna_sum`,
  `min_faction_delta`, `surplus_distribution_stdev`, and
  `negotiated_surplus_share`.
- Why diagnostic: directly measures the negotiation skill we care
  about most — surfacing existing-but-hidden joint value through
  communication.
- Why the companion fields matter: no-deal outcomes can have different
  `pareto_efficiency` values solely because BATNAs differ. The
  normalized surplus fields make those cases comparable across runs.

### 3.3 vs Naive Baseline (implemented in self-play scoring)

```
skill_premium = (your_score - baseline_score) / (max_possible - baseline_score)
```

where `baseline_score` is what an agent would get from a defined naive
strategy. Candidates:

- **Equal-split baseline:** each faction takes 1/N of the Pareto-optimal
  surplus
- **BATNA-clearing baseline:** each faction scores at BATNA until a
  Pareto-improving deal is offered, then normalize against faction max
- **Nash bargaining baseline:** the analytic solution given full
  information, computed over BATNA-clearing deals only

- Range: `(-∞, 1.0]`. Positive = outperformed calculation alone.
- Captures: "Did the negotiation surface value calculation wouldn't have?"
- Status: ✓ Implemented in `tests/self_play/game_environment.py` and
  rendered in `tests/self_play/analysis.py`. The scorer now emits
  `equal_split_baseline`, `vs_equal_split`, `max_possible_per_faction`,
  `skill_premium_vs_batna`, `nash_deal_scores`, `nash_deal_sum`,
  `nash_product`, and `vs_nash_efficiency`.
- Why diagnostic: isolates skill from scenario difficulty. A skilled
  agent on a hard scenario may score lower than a naive agent on an
  easy scenario; this metric controls for that.

### 3.4 Process signatures (5 deterministic signatures implemented)

A *bundle* of behavioral metrics. Not a single formula; a vector of
diagnostics that characterize *how* the deal was reached, not just
*what* was reached.

| Signature | Formula | Currently captured? |
|---|---|---|
| **Broken-promise rate** | `broken / total_promises` | ✓ implemented |
| **Position-shift count** | Number of times an agent's stated position on an issue changed in response to another agent's argument | Partial — needs LLM-judge over transcript |
| **Coalition stability** | % of coalitions formed that survived to the final deal | ✓ implemented |
| **Time-to-deal** | Round number when deal reached (or `∞` if no deal) | ✓ implemented |
| **Opening gap** | `(opening_position_value - reached_deal_value) / max_possible` | ✓ implemented for exact outcome-name matches |
| **Near-miss diagnostic** | Final-round 2-of-N convergence plus issue-level defection log | ✓ implemented in `tests/self_play/analysis.py` |
| **Concession curve** | Sequence of per-round position values; categorize as linear, geometric, anchor-then-capitulate | Partial — needs round-by-round extraction |
| **Persuasion shifts caused** | Times *other* agents changed position in response to *your* arguments | Needs LLM-judge over transcript |

- Captures: skill *signature*, not skill *outcome*. Useful when
  outcomes are similar across runs and you want to compare *how*
  agents got there.
- Status: ✓ Five deterministic signatures implemented in
  `tests/self_play/analysis.py`; report rendering lives in the same
  module. Position-shift count, concession curve, and persuasion shifts
  remain deferred because they need transcript interpretation beyond exact
  outcome-name matching.

### 3.5 How they compose

Different questions call for different combinations:

| Question | Best lens(es) |
|---|---|
| "Which agent did best in this run?" | 3.1 BATNA-relative |
| "Did the group find the available value?" | 3.2 Pareto efficiency |
| "Is this agent's prompt actually better, or is it just an easier scenario?" | 3.2 + 3.3 (controls for scenario, then compares to equal-split/BATNA/Nash baselines) |
| "How did they negotiate, not just what they got?" | 3.4 Process signatures |
| "Is a new persona/strategy/model better?" | 3.1 + 3.2 across multiple scenarios |
| "Does this strategy work in mixed-motive games but not zero-sum?" | 3.1 + 3.3 per game-mode |

---

## 4. What makes a good scenario — properties of skill-testing setups

For "negotiation skill" to be visible in outcomes, a scenario must
have:

1. **A meaningful gap between BATNA-equilibrium and Pareto-optimum.**
   If everyone's BATNA equals the Pareto-optimum, there's no
   skill-rewarding deal to find. Run 8's hand-patched Water Rights
   (Pareto sum=56 vs BATNA sum=29) had this; the compiler's defaults
   often don't.
2. **At least one logrolling opportunity.** Multi-issue scenarios
   where asymmetric priorities allow gains-from-trade. Without this,
   the game is single-issue distributive bargaining.
3. **Asymmetric private information.** Each agent's scoring table is
   private. Public narrative gives shared context but not utilities.
4. **A clear loss condition.** "No deal" must score worse than the
   worst acceptable deal, or agents have no incentive to negotiate
   under information asymmetry.
5. **Time pressure** (optional but recommended). Some mechanism that
   makes "wait for a better offer" not strictly dominant — round
   decay, asymmetric deadlines, exogenous events.

The reverse scenario builder (§4.5) is the systematic answer to "give me
a scenario with these properties." Hand-patching (raising BATNAs in
`--analysis-json` to create pressure) remains the workaround for properties
the builder doesn't yet cover.

---

## 4.5. The reverse scenario builder — operationalizing §4

`tools.scenario_builder` (shipped Phase 35; search improvements Phase 36)
generates a scenario file from a target outcome-shape specification.
Operator writes a `ScenarioSpec` JSON describing what properties the
scenario should have; the tool searches scoring-table space and emits the
same `scenario_analysis.json` + per-faction `.txt` personas the rest of the
pipeline consumes. Read from `CLI_REFERENCE.md` for the full CLI surface.

### Why it exists

The §4 properties are easy to *recognize* in a finished scenario and easy
to *fail to produce* when authoring one. Two existing paths each have a
gap:

- **`tools.scenario_compiler` (forward, LLM-driven)** — takes a narrative
  and asks an LLM to invent a coherent scoring table. Coherence is enforced
  by the prompt; no §4 property is structurally guaranteed. Runs 1-10 used
  this path; Run 8 needed hand-patching to create BATNA pressure.
- **Hand-authored scoring tables** — full control, but each scenario takes
  ~30 minutes of careful design and the §4 properties have to be re-verified
  by `tests.self_play.verify_scenario_optimum` after each tweak.

The reverse builder inverts the relationship: operator specifies the
properties, tool searches scoring-table space until it finds a candidate
that has them. The §4 properties become typed spec fields.

### What it produces

A scenario directory matching the existing pipeline contract:

- `scenario_analysis.json` — factions, issues, outcomes, scoring, BATNAs,
  `game_mode`. Same schema, same downstream consumers (self-play,
  `FileBasedPersona`, verifier).
- `<faction>.txt` per faction — rendered from `PERSONA_TEMPLATE`.
- `logrolling` and `deception_tactics` fields emitted as stubs until the
  reverse-builder output is passed through
  `tools.scenario_compiler --fill-narrative-only` (or hand-authored).

Workflow:

`ScenarioSpec` -> `tools.scenario_builder` -> `scenario_analysis.json` +
persona stubs -> `tools.scenario_compiler --fill-narrative-only
[--domain-context-file ...]` -> enriched `scenario_analysis.json` +
persona files

### Spec fields ↔ §4 properties

| §4 property | `ScenarioSpec` field | What it controls |
|---|---|---|
| BATNA-Pareto gap | `batna_to_pareto_gap_pct` | Minimum (Pareto - BATNA) / max_score across factions |
| Logrolling opportunity | `requires_logrolling` | True → at least one Pareto deal where every faction clears 75% of max |
| Pareto landscape shape | `pareto_count_target` | Number of distinct Pareto-optimal deals (1 = single answer; range = coordination problem) |
| Acceptable-deal space | `batna_clearing_count_target` | Number of voluntary (BATNA-clearing) deals overall |
| Skill discrimination | `pareto_outcome_diversity` *(Phase 37, queued)* | Pareto deals favor different factions |
| Frontier uniformity | `pareto_distribution_spread` | Per-faction range stdev across the frontier — fairness-audit metric, distinct from skill discrimination |
| Asymmetric BATNAs | `asymmetric_batna_fractions` | Per-faction BATNA = fraction × max-possible-score |
| Priority structure | `priority_collision` | `none` (clean logrolling) / `soft` (forces compromise) / `hard` (single contested issue) |
| Game mode | `game_mode` | `cooperative` / `competitive` / `mixed` — flows into persona template |
| Pressure mechanisms | `pressure` object (`round_cost_decay`, `asymmetric_clocks`, `penalty_floor_offset`) | Small-bundle pressure now lives on the scenario schema and feeds persona / round-context rendering; exogenous events remain deferred to Phase 39 |

Targets that aren't strictly required can be downweighted or disabled via
`target_weights: {<field>: <weight>}`. The default is 1.0 for continuous
targets, 0.3 for categorical (logrolling presence, priority collision,
game mode); set 0.0 to drop a target from the fitness sum.

### Sample workflow

```
python -m tools.scenario_builder \
  --spec tests/self_play/scenarios/joint_space_mission_v1/spec.json \
  --output-dir tests/self_play/scenarios/joint_space_mission_v1/ \
  --title "Joint Space Mission" \
  --seed 42 \
  --verify
```

`--verify` re-runs `tests.self_play.verify_scenario_optimum` on the emitted
JSON and exits non-zero on FAIL. `--debug-search` emits per-restart fitness
records when a spec doesn't converge in expected time.

### What it doesn't (yet) do

- **Pressure mechanisms.** Round-cost decay, asymmetric deadlines, and
  penalty floor now sit in `scenario_analysis.json` as `pressure` and flow
  through `PERSONA_TEMPLATE`; exogenous events still sit outside the schema
  and remain deferred to Phase 39. `NEXT_STEPS.md` §2.
- **LLM narrative wrap.** Closed via `tools.scenario_compiler
  --fill-narrative-only`; logrolling text and deception tactics are filled
  from the fixed scoring tables, with an optional domain-context file for
  operator framing.
- **Larger search spaces.** Validated at 3 factions × 3 issues × 3
  outcomes (27-deal space) in ~4 seconds. 4+ factions or 4+ issues per
  faction may need search-algorithm work (LLM-guided proposal seeding,
  larger neighborhoods).
- **Skill-discrimination targeting.** `pareto_outcome_diversity` is queued
  as Phase 37 — the existing `pareto_distribution_spread` measures
  per-faction frontier-range uniformity, not "different deals favor
  different factions." Both metrics are useful; they answer different
  questions.

### Status

Built and validated 2026-06-11. First operator spec
(`tests/self_play/scenarios/joint_space_mission_v1/spec.json`) converges
in ~4 seconds and produces 3 distinct Pareto-optimal deals plus 2
logrolling-quality deals — the multi-Pareto spectrum that motivated the
tool. Phase B (LLM-author personas, optional self-play smoke) is the
immediate operator follow-up; the scenario is regenerable from the
committed spec at any time.

---

## 5. The three workstream blocks

All work fits one of three blocks. Each has its own iteration loop, its
own evaluation signal, and its own kind of technical debt. Cross-cutting
items get a fourth bucket.

### Block A — Agent architecture & memory

**What it covers.** The pipeline that turns inbound events into outbound
messages: extraction, state management, analyst, reconciliation, context
assembly, generation, adversarial, review gate. Plus the memory model
(events + audit log + entities) and the conversation model (Stage
1/2a/2b/3 per `ARCH_conversation_model.md`).

**Iteration loop.** Add or modify a module → unit tests + Layer 3
integration tests → fake-LLM regression → live self-play sanity check.

**Evaluation signal.** Test pass/fail; behavioral diffs in self-play
transcripts; reconciliation accuracy (dedup hit rate, fulfillment
detection rate).

**Tech debt to watch.** Per-event structured logging (currently only
`DIPLOMAT ONLINE` lines), tools/function-calling support (none yet),
tiered memory (none — flat state + audit log). The Pipeline/Flow
split is complete (Phase 22); adding a StreamFlow / TurnBasedFlow /
Clankmates HybridFlow is now additive against the stable `Pipeline`
contract.

**Closed debt.** Reconciliation path coverage is covered by Layer 3
tests in `tests/integration/test_phase18_paths.py`: burst extraction
without dropped messages, duplicate promise merge, promise fulfillment,
new inconsistency detection, and missed proposal insertion.

**Active items.** Stage 2a conversation model (#3), structured per-event logging (smoke tooling debt).

**Closed debt (Phase 21).** Module boundary cleanup orchestration (§1.7 — `OrchestrationOptions` dataclass, `advance_to_round` public API, reconciler logged exceptions) ✓. Module boundary cleanup LLM adapter + config (§1.8 — `_TaggedLLMClient` deleted, `LoggingLLMClient` reduced, `purpose` kwarg threaded through all modules, `DryRunLLMClient` purpose-based classification, `build_reconciler` / `subsystem_llm_config` factories) ✓.

**Closed debt (Phase 22).** Pipeline/Flow split (§1.9 — `Pipeline` interface in `src/pipeline.py`; `EventDrivenFlow` for production Telegram/CLI; `RoundSteppedFlow` for self-play; `Orchestrator` reduced to compat factory returning `EventDrivenFlow`; `GameEnvironment` composes `RoundSteppedFlow`) ✓.

### Block B — Prompt tuning

**What it covers.** Everything that goes into an LLM call as
prompt — faction personas, module prompts (state_updater, analyst,
generation, adversarial, reconciliation), strategy libraries, voice
overlays, few-shot examples, per-role model assignment.

**Iteration loop.** Edit prompt or persona → Layer 2 prompt regression
suite (`tests/prompt_regression/`) → self-play run → review transcripts
and edit logs → revise prompt.

**Evaluation signal.** Prompt regression pass rates; review-gate edit
classifications (`tone_softer`, `commitment_removed`,
`constraint_enforcement`, etc.); persona coherence over rounds; deal
quality from self-play.

**Tech debt to watch.** Persona payment rigidity (recurring across
Runs 7, 8); persona endgame over-anchoring; persona drift in long
games; provider-native structured output (token-level schema
compliance via OpenAI `response_format`).

**Active items.** Strategy library §2.5, voice templates §9,
persona payment rigidity A/B test, persona endgame over-anchoring
decision, more extraction few-shot examples, per-role model strategy
§7.

### Block C — Game creation, scoring, assessment

**What it covers.** Scenario design and compilation, BATNA tuning,
pressure mechanisms, verification tools, post-game scoring (all four
lenses from §3), process signature aggregation. Anything that asks
"is this scenario well-designed?" or "did this agent negotiate well?"

**Iteration loop.** Hypothesis about skill or scenario property →
design or compile a scenario → verify with `verify_scenario_optimum.py`
→ run self-play → score with all applicable lenses → conclusion.
`RUN_PROTOCOL.md` formalizes the live-run side.

**Evaluation signal.** Pareto efficiency across runs; skill premium
over naive baseline; process signature distributions; scenario
verification pass/fail.

**Tech debt to watch.** Skill premium (3.3) is still unimplemented;
three process signatures (position-shift count, concession curve,
persuasion shifts caused) still require transcript interpretation;
reverse scenario builder doesn't exist; scenario compiler still
under-pressures BATNAs by default (mitigated by `--batna-fraction`).

**Active items.** Game pressure beyond BATNA §2 (round decay,
exogenous events, asymmetric deadlines, penalty floors, cascade
scoring); divorce scenario design §2; reverse scenario builder §8;
pricing audit §6 (cost accounting affects per-game cost metrics).

### Cross-cutting items

Some items touch multiple blocks or sit outside them:

- **Toolkit fixes** — `complete_with_retry`, `normalize_model_name`,
  `max_completion_tokens` dispatch (uncommitted from 2026-05-31 smoke).
  Cross-cutting infrastructure.
- **OpenRouter integration §1.5** — expands provider matrix; enables
  Block B experiments but is infrastructure.
- **Clankmates transport §5** — production deployment surface for
  game traffic; orthogonal to A/B/C until the platform ships.
- **Coaching test loop on Pi §4** — meta-test that exercises all
  three blocks end-to-end with a human in the loop. The original
  product hypothesis.
- **Run 9 (rotated providers)** — uses A and C infrastructure to test
  whether provider choice affects outcomes; the result feeds back
  into Block B (per-role model strategy §7).

---

## 6. Cross-references

| Concept | Lives in |
|---|---|
| Component architecture | `ARCHITECTURE.md` + per-module `ARCH_*.md` |
| Scope, constraints, MVP | `PROJECT.md` |
| Phase plan + cold start | `DEVPLAN.md` |
| Operational tuning (BATNA, providers, prompts) | `TUNING.md` |
| Self-play live-run pre-flight | `RUN_PROTOCOL.md` |
| Bot lifecycle on Pi | `diplomat-testing-doc.md` §5b, `CLI_REFERENCE.md` |
| Active backlog, A/B/C-tagged | `NEXT_STEPS.md` |
| Run-by-run findings | `TUNING_LOG.md` |
| Audit trail | `DEVLOG.md` + `DEVLOG_archive.md` |
| Conceptual scoring framework, workstream map | **this doc** |

---

## Change history

| Date | Change |
|---|---|
| 2026-05-31 | Initial draft. Distills a conversation between operator and Devmate (in this session's chat) about why pure calculation isn't negotiation, what skill means in Diplomat's setting, four scoring lenses with formulas, properties of skill-testing scenarios, and three workstream blocks (A: architecture/memory, B: prompt tuning, C: game creation/scoring). NEXT_STEPS items get tagged A/B/C in a follow-up edit; PROJECT.md and DEVPLAN.md get pointer references. |
| 2026-05-31 | Block A "tech debt to watch" updated with Pipeline/Flow separation as the architectural seam for adding new application sequences (StreamFlow, TurnBasedFlow, Clankmates HybridFlow). Active items list updated with §1.7, §1.8, §1.9 from NEXT_STEPS. |
| 2026-05-31 | Block A reconciliation path coverage moved from active debt to closed debt after Layer 3 `test_phase18_paths.py` covered burst extraction, dedup, fulfillment, inconsistencies, and missed proposals. |
| 2026-05-31 | Block A Pipeline/Flow split (§1.9) moved from active debt to closed debt (Phase 22): `Pipeline` interface extracted, `EventDrivenFlow` and `RoundSteppedFlow` implemented, `Orchestrator` compat shim, `GameEnvironment` refactored. Tech-debt-to-watch blurb updated to reflect completion. |
| 2026-05-31 | Phase 23 implemented scoring lenses §3.2 Pareto efficiency and four deterministic §3.4 process signatures. Block C tech debt now tracks only skill premium, transcript-interpretive process signatures, reverse scenario builder, and BATNA pressure defaults. |
