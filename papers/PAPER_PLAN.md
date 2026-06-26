# Diplomat — Paper Plan (Angle B first → Angle A)

> Living plan for turning the Diplomat benchmark work into publications.
> **Strategy:** lead with the **benchmark itself** as the primary contribution.
> **Paper 1 = "Diplomat: a contamination-resistant negotiation benchmark"** —
> establishes the benchmark is *valid* (well-calibrated to current capability,
> non-contaminable, construct-valid / correlated-but-distinct from existing
> benchmarks), then presents **harness/scaffolding lift as a headline finding +
> measurement caveat**. Paper 1 is built on the *cooperative capability* measure
> (close-rate / Pareto efficiency / surplus share), which the existing data
> already supports — so it is **not** gated on solving the distributive-scenario
> discrimination problem. **Paper 2 = the competitive head-to-head leaderboard**
> (mixed-model rank lens + coalition-value scoring on distributive / coalition
scenarios) — gated on succ-v3 + §3.6; every Paper 1 deliverable is reused
> (see §7). **Paper 3 (separate, later) = behavioral steering of negotiators**
> (disposition × scenario-shape interaction) — the prompt-tuning "can of worms";
> see §7b.
>
> ⚠️ **Framing order matters: benchmark validity first, scaffolding second.** You
> cannot claim "scaffolding changes the ranking" before establishing the ranking
> measures something real. Scaffolding lift is a *finding within* a validated
> benchmark, not the lead.
>
> Status legend used throughout: ✅ complete · 🔧 minor work (more N /
> re-analysis / hygiene) · 🆕 from scratch.
>
> Source-doc shorthand: ASSESS = `ASSESSMENT.md`, RN = `RESEARCH_NOTES.md`,
> TL = `TUNING_LOG.md`, SG = `SCENARIO_GUIDE.md`, GG = `GAME_GUIDE.md`.

---

## 0. Positioning — why this is a benchmark, and why it's valuable

**One-sentence pitch.** Diplomat is a contamination-proof,
game-theoretically-grounded benchmark for LLM *negotiation* skill — a frontier
agentic capability that static benchmarks can't measure — with built-in
controls (position rotation, scaffolding ablation) that make model rankings
*valid* rather than artifacts of the test harness.

### Why negotiation, why now
- **Agentic deployment makes it economically real.** LLMs are increasingly
  deployed to act and transact on users' behalf (scheduling, procurement,
  multi-agent systems). Multi-party negotiation under asymmetric information is
  a capability those deployments depend on — and it is essentially unmeasured
  at scale.
- **It's a distinct capability.** Negotiation requires theory-of-mind,
  strategic reasoning, and communication under hidden information — none of
  which coding, QA, or tool-use benchmarks isolate. A model can be excellent at
  those and still be a poor negotiator (see: sonnet's strategic refusal,
  mid-tier's "stuck-but-engaged" failure).

### The gap in existing evaluation
- **Static QA / multiple-choice benchmarks** are saturating and increasingly
  *contaminated* by training data.
- **Most prior LLM-negotiation / multi-agent work** is one of: a single fixed
  scenario, human- or LLM-judged (no objective ground truth), or specific to
  the Diplomacy *board game* (Cicero / Welfare Diplomacy) rather than general
  negotiation structure.
- **Diplomat's niche:** synthetic (contamination-proof) scenarios × objective
  game-theoretic ground truth × scaffolding-aware, position-controlled
  measurement × a multi-dimensional diagnostic profile. No existing benchmark
  combines these.

### Five value pillars
1. **Contamination-proof by construction.** The reverse builder generates
   never-published scenarios deterministically — a property static benchmarks
   are losing and can't recover.
2. **Objective ground truth.** Outcomes score against a *computable* optimum
   (Pareto sum, Nash product, surplus share, BATNA) — no human or LLM judge
   needed to grade the result, unlike most generative evals.
3. **Skill-vs-luck controls.** Position rotation + multi-game aggregation
   separate model skill from seat asymmetry — the infrastructure that makes a
   *leaderboard* credible rather than anecdotal.
4. **Diagnostic profile, not a scalar.** Six scoring lenses + process
   signatures yield a profile — value-creation vs value-claiming vs walk-away
   discipline vs scaffolding-dependence — which is more actionable to model
   developers than a single number.
5. **Measurement validity is built in.** The scaffolding-ablation axis (Paper
   B) is itself part of the benchmark's methodology, not a side study (next).

### Primary thesis (Paper 1): the validity triad
The headline contribution is a *validated* benchmark. Three claims, each with
its own evidence requirement (experiments in §5.7):

1. **Well-calibrated to current capability.** Models spread across the
   difficulty range — frontier models do not saturate the hardest scenarios,
   weak models floor, mid-tier gets stuck. (Evidence: per-scenario score
   distribution across the roster; at least one cell the best model fails.)
2. **Contamination-resistant by construction.** Scenarios are synthetic and
   deterministically generated by the reverse builder — never published, not
   memorizable. (Evidence: the builder argument; optionally an empirical test
   that paraphrase/regeneration doesn't move scores.)
3. **Construct-valid.** The benchmark *correlates* with established capability
   indices (so it measures real capability) but is *not redundant* — it
   captures negotiation-specific variance MMLU/Elo miss. (Evidence: §5.7
   correlation; the multi-dimensional profile answers "why not just use MMLU?")

### Secondary contribution (a finding within the validated benchmark): harness lift
Only *after* the benchmark is established as valid do we present
*scaffolding/harness lift* — the §1 sharpened claim (scaffolding contribution =
f(scenario × capability), with the three-mechanism taxonomy of "zero lift").

This finding does double duty:
- **A substantive result** about when scaffolding helps LLM negotiation agents.
- **A measurement caveat for the benchmark itself**: *how you harness a model
  changes its measured rank*, so any negotiation leaderboard must fix the
  harness when ranking models. This is what makes the harness work intrinsic to
  the benchmark rather than a side study — but it is the **second** act, not the
  lead.

Framing consequences (for §6 Introduction + Related Work):
- Position against the **benchmark** literature; claim the validity triad first.
- Present harness lift as finding + caveat, not thesis.

---

## 1. The sharpened claim (secondary contribution — harness lift)

> This is the **second** act, presented only after the §0 validity triad is
> established. It is a finding *within* the benchmark + a measurement caveat —
> not the paper's lead.

The pre-existing re-framing — *"harness contribution = f(scenario shape, what
the model already does well)"* (RN Note 1 amendment) — is true but
unfalsifiable: neither input is operationalized and the function has no shape.
The publishable, falsifiable version:

> **Scaffolding lift is large only when the scaffold supplies the specific
> reasoning a model lacks for a given scenario. "Zero lift" is not one
> phenomenon — it has three distinct mechanisms that aggregate close-rate
> metrics conflate:**
> 1. **Ceiling** — model already solves it unaided (sonnet/jsm1: bare 3/3 =
>    full 3/3).
> 2. **Redirect-failure** — model *uses* the scaffold's intel but pursues a
>    different objective, so the scaffold can't move the outcome (sonnet/WR-β:
>    strategic refusal; intel fired, 27 promises tracked in 14e-1, deal still
>    refused).
> 3. **Mismatch/floor** — model fails for a reason the scaffold doesn't
>    address (mid/jsm1: stuck on the last issue regardless of intel; gemini:
>    identity confusion).

Why this is conference-grade rather than a tired "scaffolds matter less for
better models" note:
- **Falsifiable + predictive.** It predicts *where* lift is large (capability
  just below the scenario's demand AND the missing piece is something a
  scaffold module supplies) and where it is zero.
- **Novel decomposition.** Most scaffolding papers report one lift number; the
  three-mechanism taxonomy is the contribution.
- **Forces the right instruments.** Distinguishing the three mechanisms
  requires process-signature / transcript analysis (the mechanism classifier,
  §4.1), not just close-rate.

**One-line framing:** *"How much does scaffolding help?" is the wrong
question; "what is the model missing, and does the scaffold supply it?" is the
right one — and the same aggregate lift number hides three different answers.*

---

## 2. Operationalizing the two axes

### 2.1 Model strength

Building **both** an external proxy and a dedicated probe battery (§4.2).

- **External capability index** (LMArena Elo / MMLU-style). Free, no new runs;
  serves as the *independent* x-axis.
- **Capability probe battery** (§4.2). A held-out micro-task suite scoring
  negotiation *sub-skills* independently of full games. Lets us **predict**
  lift (model's probe profile × scenario's demand profile) rather than merely
  correlate it. Reused as a benchmark dimension in Paper A.

> **⚠️ Methodological trap to avoid.** Do **not** define strength = bare-rate
> and then plot lift = (full − bare) against it — that is mechanically
> anti-correlated (bare appears on both axes with opposite sign) and a
> reviewer will reject it. Use the **independent** axis (external index or
> probe battery) for lift-vs-capability plots; use bare-mode performance only
> as *within-domain validation* of that axis. Where possible plot **full-rate
> vs bare-rate directly** rather than the difference.

### 2.2 Scenario richness — three groups of axes

"Richness" is not one axis. It decomposes into three groups with very
different cost-to-vary. **Groups A + B are the experimental spine** (cheap,
clean, controllable); Group C is scoped as harder / partly future work.

**Group A — builder-controllable structural axes** (reverse builder takes
these as typed spec fields; clean one-at-a-time sweeps possible):

| Axis | Measurable proxy | Builder field | Coverage |
|---|---|---|---|
| Pareto-landscape topology | pareto_count, `pareto_outcome_diversity` | `pareto_count_target` | WR-β single ✓, jsm1 multi ✓, distributive ✗ (succ/succ2 broken) |
| BATNA→Pareto gap | (Pareto − BATNA)/max | `batna_to_pareto_gap_pct` | swept Runs 9–11 (archive) |
| BATNA asymmetry | per-faction BATNA fraction | `asymmetric_batna_fractions` | α/β/γ-squeezed ✓ |
| Deal-space size D | O^I | F/I/O | only 3×3×3 in live runs |
| Factions (O(N²) relationships) | F | spec | 3 only (Phase 42 unblocked 4–6) |
| Priority collision | none/soft/hard | `priority_collision` | succ soft, succ2 hard |
| Pressure mechanisms | round-cost / clocks / floor | `pressure` | schema exists, untested in runs |
| Game mode / zero-sum content | cooperative/competitive | `game_mode` | cooperative only |

**Group B — runtime axes** (trivially cheap to vary; no new scenario):

| Axis | Proxy | How to vary |
|---|---|---|
| Horizon / persona drift | round count | `rounds` param |
| Context utilization | prompt tokens | scales with F, I, rounds |

**Group C — semantic axes** (need narrative authoring; hard to isolate):

| Axis | Why hard |
|---|---|
| Deception / adversarial structure | needs `deception_tactics` + persona design; Run 5 Trade Summit not in repo |
| Trust / reputation dynamics | emergent, not a single dial |

---

## 3. Extensions ranked by interest-per-work

1. **🥇 Horizon sweep (Group B).** WR-β at 4 / 8 / 12 rounds × ladder ×
   full+bare. A *parameter change*, not a new scenario. Tests context +
   persona-drift axes — and it is the **exact intuition that started Note 1**
   ("the harness would matter when you can't keep everything in memory") and
   has **never been tested**. Highest interest-per-dollar.
2. **🥈 BATNA-pressure re-analysis.** Runs 9–11 already swept variants;
   consolidate + boost N. Mostly re-analysis.
3. **🥉 Mechanism classifier (build).** Turns the three-mechanism claim from
   hand-inspected anecdote into systematic data. Linchpin of the sharpened
   claim.
4. **Targeted per-module ablation** on the high-lift cell (weak/mid WR-β) —
   not the full per-module matrix. Cleanest demonstration of "scaffold
   supplies the specific missing piece."
5. **(Stretch) one deception scenario** — best clean test of the Adversarial
   module; Group C authoring cost.

---

## 4. The two builds

### 4.1 Mechanism classifier (LLM-judge) — 🆕

**Purpose.** Label every game outcome so the three-mechanism taxonomy (§1)
is data, not anecdote.

**Spec.**
- Input: full transcript + final positions + scored outcome.
- Output label, no-deal cases: `strategic_refusal` | `near_miss`
  (converged on a strict subset of issues) | `breakdown` (substantive but
  scattered) | `incoherence` (identity/quality failure). Deal cases:
  `closed`. Plus a free-text rationale + the issue(s) of failure.
- Validation: hand-label a seed set (14e = refusal; gemini jsm1 =
  incoherence; mid jsm1 = near-miss; nano-bare = breakdown/floor) → measure
  judge↔human agreement (report Cohen's κ). Ship only if κ is acceptable.
- Guardrail: the judge model must **not** be one of the contestant models
  scoring itself; use a fixed independent judge.

**Status of inputs:** seed labels ✅ (exist from manual 14e/Run-15
inspection); classifier itself 🆕; validation set 🔧 (extend seed labels).

### 4.2 Capability probe battery — 🆕

**Purpose.** An independent, auto-gradable measure of negotiation sub-skills,
mapped to ASSESS §2 skill dimensions and to the scaffold modules that are
supposed to supply them. Enables *predicting* lift.

**Probe tasks** (ground truth computable via `verify_scenario_optimum` /
`enumerate_deals` — so **no LLM-judge needed** for the battery, avoiding a
judge-validation burden):

| Probe | Sub-skill (ASSESS §2) | Scaffold module it maps to | Ground truth |
|---|---|---|---|
| Pareto identification | calculation baseline | (none — raw capability) | enumerated frontier |
| Logroll identification | concession sequencing | analyst leverage-points | deterministic |
| Preference elicitation | preference elicitation | Analyst | hidden priority in tables |
| BATNA / accept-or-walk | threat credibility | persona BATNA | computable EV |
| Bluff / deception detection | deception detection | Adversarial reader | planted misrepresentation |
| Commitment tracking | reputation mgmt | State Manager + Reconciler | promise state from transcript |
| Position-consistency over horizon | persona drift | Reconciler | injected contradiction |

**Key design lever:** the *commitment-tracking* and *consistency* probes are
**scaled by transcript length** → they measure the context/horizon axis at the
capability level, directly predicting where State Manager / Reconciler scaffold
becomes load-bearing. This ties the battery to the §2.2 richness axes.

**Output:** per-model capability *vector* (one score per sub-skill) +
optional scalar. The vector also seeds Paper A's multi-dimensional model
profile.

---

## 5. Experiment ledger

N targets: **n≥20** for cheap bare cells, **n≥10** for expensive full /
frontier cells; report bootstrap CIs. Rough per-game costs (from TL): nano
full ~$0.05, mid full ~$1–1.5, sonnet full ~$0.65, bare ~$0.05–0.30; ×3
rounds for the 12-round horizon cells.

### 5.0 Hygiene / infra (gates everything)

| Item | Status |
|---|---|
| Uniform temperature across cells | 🔧 (gpt-5.5 ran temp=1; rest 0.7) |
| Per-run cost capture (`metadata.cost_usd` is None; ledger stale) | 🆕 small |
| Explain zero within-cell variance at temp 0.7 | 🔧 (must explain or it reads as a bug) |
| N-scaling to n≥10–20 + bootstrap CIs | 🔧 (`ablation_multi.sh` exists; run more) |
| External capability index lookup table | 🆕 trivial |
| Mechanism classifier | 🆕 (§4.1) |
| Capability probe battery | 🆕 (§4.2) |

### 5.1 Claim 1 — lift declines with capability (fixed shape)

| Cell | Status |
|---|---|
| WR-β OpenAI ladder nano/mini full+bare | ✅ (Run 14) · 🔧 N |
| WR-β gpt-5.5 (strong OpenAI) **full** | 🆕 (only bare exists, Run 18) |
| WR-β Anthropic ladder haiku + opus full+bare | 🆕 (only sonnet exists) |

### 5.2 Claim 2 — lift depends on scenario shape (the interaction)

| Cell | Status |
|---|---|
| jsm1 OpenAI ladder nano/mini full+bare | ✅ (Runs 15/16) · 🔧 N |
| jsm1 sonnet full+bare | ✅ · 🔧 N |
| jsm1 gpt-5.5 full / Anthropic haiku+opus | 🆕 |
| WR-β × jsm1 contrast matrix | ✅ assembled · 🔧 N |
| ≥1 third shape point with headroom (pressured WR-β or working distributive) | 🆕 |

### 5.3 Claim 3 — three mechanisms of zero lift

| Item | Status |
|---|---|
| Ceiling (sonnet jsm1) | ✅ identified · 🔧 N |
| Redirect-failure / strategic refusal (sonnet WR-β) | ✅ manual transcript (14e) · 🔧 classifier + provider-disentangle |
| Mismatch/floor (mid jsm1, gemini) | ✅ identified · 🔧 classifier |
| Provider confound (sonnet vs gpt-5.5 WR-β) | 🔧 partial (Run 18, one cell, temp confound) → same-provider ladders + uniform temp |
| Classifier applied across all no-deals | 🆕 (depends on §4.1) |

### 5.4 Claim 4 (extension) — lift rises with horizon

| Cell | Status |
|---|---|
| WR-β @ 4 / 8 / 12 rounds × ladder × full+bare | 🆕 (cheap param sweep; pricier at 12 rounds) |

### 5.5 Claim 5 (optional) — module attribution

| Cell | Status |
|---|---|
| Targeted per-module ablation on high-lift cell (weak/mid WR-β) | 🆕 |

### 5.6 Secondary / cheap wins

| Item | Status |
|---|---|
| Cross-provider Pareto convergence (4 families → identical deal) | ✅ exists — free section |
| Cost-economics ($/closed-deal) | 🔧 (needs cost-capture fix) |
| Cross-provider validation (V3, R1) on ladders | ✅ partial · 🔧 N |

**Critical-path "from scratch" set (small):** Anthropic ladder (haiku +
opus), gpt-5.5 full cells, mechanism classifier, capability probe battery,
horizon sweep, per-run cost capture. Everything else is N-boosting +
re-analysis of existing data.

### 5.7 Construct validity & calibration (NEW — Paper 1 *primary* evidence)

This is the evidence the benchmark-led framing requires; it's the lead result,
not a secondary one.

| Item | Status |
|---|---|
| **Per-model benchmark score** (aggregate close-rate / Pareto-efficiency / surplus-share across the scenario suite) | 🔧 (components exist per run; need aggregation + roster coverage) |
| **Calibration / difficulty distribution** — show models spread across difficulty; ≥1 scenario the best model does *not* saturate | 🔧 (WR-β sonnet 0/3 + jsm1 ceiling exist; need a clean difficulty-graded suite + framing) |
| **Correlation with external indices** (Diplomat score vs LMArena Elo / MMLU across roster) — high-but-<1 | 🆕 (needs roster scored + external numbers; trivial once roster runs land) |
| **Discriminant validity** — show negotiation-specific residual variance (e.g., value-claiming / strategic-refusal axis doesn't track general capability) | 🔧 (data exists: sonnet refusal vs gpt-5.5 close; formalize) |
| **Diplomat-score vs probe-battery correlation** (two capability measures agree) | 🆕 (depends on §4.2 probe battery) |
| **(Optional) empirical contamination test** — paraphrase / regenerate a scenario, show scores don't move | 🆕 cheap |

### 5.8 Model roster (Paper 1)

Two clean same-provider ladders + cross-provider validation:
- **OpenAI:** gpt-4.1-nano → gpt-5.4-mini → gpt-5.5
- **Anthropic:** claude-haiku-4-5 → claude-sonnet-4-6 → claude-opus
- **Cross-provider validation:** deepseek-v3, deepseek-r1 (toolkit
  `606e309` unblocked R1)

### 5.9 Disposition probe (minimal — Paper 1; third intervention axis)

Disposition (persona prompt: "be agreeable" / "be aggressive" / "prioritize
reaching a deal") is a **third intervention axis** distinct from scaffolding —
model × scaffold × **disposition**. Scaffolding changes *what the model knows*;
disposition changes *what it is trying to do*. **Do not merge this into the
bare/full ablation** — it is a separate axis. The minimal probe does double
duty in Paper 1; the full study is Paper 3 (§7b).

| Item | Status |
|---|---|
| **Leaderboard robustness check** — do rankings survive persona perturbation? (neutral / agreeable / aggressive × the 2 existing scenarios, small N) | 🆕 |
| **Redirect-failure confirmation** — instruct sonnet to "prioritize reaching a deal" on WR-β; predict the strategic-refusal flips to a *close*, whereas *more scaffolding* does not | 🆕 (cheap; cleanly separates redirect-failure (disposition) from mismatch/floor (capability) — something the scaffolding ablation alone cannot do) |

**Validity tie-in:** this is the *second instance* of the measurement-validity
point — "how you prompt a model changes its rank," so a valid leaderboard must
fix persona as well as scaffold. Keep scope minimal here.

---

## 6. Paper outline (status-marked)

Conference/workshop structure. Status reflects how much *writing* exists, with
the source doc that seeds it.

| # | Section | Status | Source / notes |
|---|---|---|---|
| — | Abstract | 🆕 | write last; lead with the validated-benchmark contribution, harness lift second |
| 1 | Introduction | 🔧 | ASSESS §1 (calculation-vs-negotiation gap) ~80% there; open with §0 value pillars + the **validity triad**, *not* scaffolding |
| 2 | Related work | 🆕 | **biggest gap & risk** — position against the *benchmark* literature (Cicero, Welfare Diplomacy, NegotiationArena, cooperative-AI evals) per §0; claim the contamination-resistant + ground-truth + correlated-but-distinct niche |
| 3 | The Diplomat benchmark (game + harness) | 🔧 | `ARCHITECTURE.md` + `ARCH_*.md`; condense to what the benchmark needs |
| 4 | Scoring & metrics | ✅/🔧 | ASSESS §3 + GG Appendix A nearly publication-ready |
| 5 | Scenario design & richness axes (synthetic → contamination-resistant) | 🔧 | SG + ASSESS §4 + §2.2; foregrounds the reverse builder as the non-contamination mechanism |
| **6** | **Benchmark validity (PRIMARY results)** — calibration, contamination, construct validity / correlation | 🔧/🆕 | **the lead result**; §5.7 experiments; the validity triad from §0 |
| 7 | Per-model results / negotiation profiles | 🔧 | the model ordering + multi-dimensional profile (answers "why not just MMLU") |
| 8 | Harness lift (SECONDARY) — strength operationalization (probe), three-mechanism taxonomy, lift results, **disposition probe** (redirect-failure confirmation) | 🆕/🔧 | §1 + §4.2 + §5.1–5.5 + §5.9; the finding + measurement caveat, presented *after* validity |
| 9 | Experimental setup | 🔧 | `RUN_PROTOCOL.md` + dispatcher docs; add N, temp, CIs |
| 10 | Discussion / threats to validity | ✅ | RN is unusually honest — saturation, tier/provider confound, "unmeasurable not measured" already written |
| 11 | Limitations & future work (→ Paper 2: competitive leaderboard) | 🔧 | distributive discrimination (succ-v3), §3.6 coalition-value, Group C axes |
| 12 | Conclusion | 🆕 | short |
| 13 | Reproducibility / artifact | 🔧 | deterministic builder + committed specs; add one-command repro |
| — | Figures & tables | 🆕 | difficulty distribution, Diplomat-vs-external correlation scatter, per-model profile radar, harness-lift curves, mechanism-mix bars; `viz.py` is a start |

**Writing-effort summary:** the *honest* sections (4, 10) are nearly done. The
new emphasis concentrates from-scratch effort in **§6 benchmark validity** (the
lead result — needs the correlation/calibration experiments) and Related Work
(2), plus all figures. The harness-lift sections (8) are mostly compress +
update of existing prose, now demoted to the second act.

---

## 7. Paper 1 → Paper 2 transition (what carries over)

Every 🆕 item is also a Paper 2 (competitive leaderboard) requirement, so
nothing is wasted:

| Paper 1 deliverable | Reused in Paper 2 as |
|---|---|
| Same-provider ladders + uniform temp | Paper 2's model roster, confound pre-broken |
| Structural-axis scenario sweep (Group A/B) | start of Paper 2's scenario library |
| Mechanism classifier | Paper 2's process-signature instrumentation |
| Capability probe battery | one **dimension** of Paper 2's multi-dimensional model profile |
| Benchmark score + construct-validity pipeline | the rank lens's validity baseline |
| Per-run cost capture | Paper 2's cost-coverage analysis |
| Hardened harness + repro tooling | Paper 2's released artifact |

**Reconnaissance value:** Paper 2's go/no-go (does *any* scenario separate
models head-to-head?) is answered as a byproduct of Paper 1's campaign — if a
cell shows models *rank-separating* (not just bare-unsaturated), it's a live
distributive-leaderboard candidate, bought cheaply.

## 7b. Paper 3 (separate) — Behavioral steering of LLM negotiators

The prompt-tuning "can of worms," scoped as its own paper rather than diluting
Paper 1.

**Thesis questions:**
- Does disposition instruction-following (agreeable / aggressive / deal-seeking)
  produce *predictable* negotiation-behavior change?
- Does compliance vary by model (do stronger models steer more controllably)?
- **The load-bearing question — disposition × scenario-shape interaction:**
  aggression should *help* on distributive / value-claiming scenarios and *hurt*
  on cooperative value-creation ones. This ties directly into the
  value-creation-vs-value-claiming dimension and complements Paper 2's
  competitive leaderboard.

**Why separate, not in Paper 1.** Disposition is a distinct intervention axis
(§5.9), and the full crossing is model × scaffold × disposition × scenario —
combinatorially large. Paper 1 takes only the minimal probe (§5.9); the full
study needs its own design.

**Scoping caveat.** Fix scaffold (bare) and *sample* the disposition × scenario
space rather than fully crossing it; disposition interacts with both other axes
(may help a weak model and hurt a strong one; may need scaffolding to be
actionable).

**Reuse from Papers 1/2.** Minimal disposition probe (§5.9), mechanism
classifier (§4.1), model roster (§5.8), scenario suite, harness, repro tooling.

**Project tie-in.** Reconnects the **demoted Block B** (ASSESSMENT §5) to the
research program — persona prompts become the "experimental variable" D-56
reframed them to be, rather than production tunings.

## 8. Suggested execution order

1. **Infra/hygiene first** (§5.0): uniform temp, cost capture, N-scaling
   harness check, external-index table. Unblocks clean data.
2. **Builds in parallel** (§4): mechanism classifier + probe battery. Both are
   independent of the run campaign; the probe also feeds construct validity.
3. **N-boost existing cells + roster coverage** (§5.1–5.3 ✅/🔧): cheapest path
   to statistical power on data we already trust; also populates the roster
   needed for the validity correlation.
4. **Validity & calibration analysis** (§5.7) — **the lead result.** Aggregate
   per-model scores, compute the external-index correlation + calibration
   distribution + discriminant residual. This is what makes it a *benchmark*
   paper; prioritize it over the harness-lift extensions.
5. **From-scratch cells** (§5.1–5.2 🆕): Anthropic ladder, gpt-5.5 full —
   needed both for harness lift and to thicken the validity roster.
6. **Harness-lift secondary results**: horizon sweep (§5.4), mechanism
   classifier across all no-deals (§5.3), minimal **disposition probe** (§5.9 —
   robustness + redirect-failure confirmation), optional targeted per-module
   ablation (§5.5). These are the second act, not the lead.
7. **Figures + writing**, leaning on §6 status marks (validity sections first).
8. **Meta internal publication / PR / open-source review** — start the process
   conversation **early** (silent long pole). Target venue per the full-paper
   goal; if a workshop precedes the conference submission, confirm it is
   **non-archival** so Paper 2 isn't blocked by dual-submission.

---

## 9. Open decisions / risks

- **Judge validation burden** (classifier). LLM-judge scales but needs the
  κ check; hand-labels cap N. Plan: LLM-judge + hand-labeled validation set.
- **Probe construct validity.** Reviewers may argue probe sub-skills ≠
  in-game capability. Mitigation: show the probe profile *predicts* in-game
  bare performance (cross-validate the two capability measures).
- **Related-work positioning** is the top writing risk — resolve early.
- **Group C (deception/trust)** likely stays qualitative / future work for B;
  promote into A if a clean scenario is authored.
- **Generality from few scenario points** — frame as *characterizing a
  function by sampling named axes*, not exhaustive coverage; honest scoping
  reads as rigor.
