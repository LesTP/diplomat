# Diplomat — Work Sequencing (master, paper-driven)

> **Purpose.** The reconciled, prioritized work sequence to get the negotiation
> benchmark **paper(s) to a solid place**. Merges `NEXT_STEPS.md` (project
> backlog), `papers/PAPER_PLAN.md` (paper execution), and `RESEARCH_NOTES.md`
> (deep questions) into one ordered plan, captured section by section during the
> 2026-06-29 walkthrough.
>
> **Status:** MASTER PLAN (reconciled 2026-06-29). The live forward backlog;
> `NEXT_STEPS.md` is retired to a pointer here (its Tier-1/2/icebox folded in).
> Lives in `papers/` for now; could move to root + fully replace NEXT_STEPS later.
>
> **Run-lane tags:** 🔨 autonomous-loopable (queue to the pirozhok/codexbot loop;
> diplomat is an e2e project driven by codexbot) · 👁 supervised (operator /
> cost / judgment — this laptop's interactive lane) · 🔀 mixed.
>
> **Framing (post-resharpen).** The category + optimality-diagnostic scoring are
> field-standard (Abdelnabi; TERMS-Bench). Diplomat's lead contributions are
> **(1) scaffolding measurement-validity, (2) multi-party/coalition scoring,
> (3) construct validity**; optimality scoring is implemented well + clearly
> visualized (rigor/clarity, not novelty). See PAPER_PLAN §0.

> **Division of labor.** `papers/PAPER_PLAN.md` owns the *spec* (contributions,
> builds, experiment-ledger detail, paper outline, risks). **This doc owns the
> *order*** — the execution sequence (§9) and the reconciled backlog. Route
> sequencing edits here; route contribution/spec edits to PAPER_PLAN.

## Agenda (reconciled sections)

1. Discriminating distributive scenarios — ✅ captured
2. Coalition-value scoring (§3.6 Path B) — ✅ captured
3. Publication builds (mechanism classifier + capability probe) — ✅ captured
4. Construct validity + roster + hygiene — ✅ captured
5. Harness-lift completion — ✅ captured
6. Scenario-class breadth (Path C) — ✅ captured
7. Deferred research questions (Notes 1/3, Path A) — ✅ captured
8. Tier-2 infra & icebox — ✅ captured

---

## 1. Discriminating distributive scenarios 👁

**Why it leads.** Single highest-leverage gap; serves *both* papers — gates
Paper 2's competitive leaderboard **and** supplies Paper 1's "third scenario
shape with headroom" (PAPER_PLAN §5.2).

**Status.** Competitive-scoring stack shipped (rank lens, `faction_models`,
`mean_rank` aggregator, seat-rotation dispatcher). `succ`/`succ2` bracket-and-
miss (focal-deal / deadlock). `succ-v3` (`succ3`) + `succ3b` authored +
brief-passing. **`succ3b` live-tested (Run 21, homogeneous bare): headroom
confirmed** (deepseek 0/3 vs sonnet 2/3).

**Open items.**
- `succ-v3` (3-way) still **pending live test**.
- **Next experiment:** single-provider **tier ladder, seat-rotated** on succ3b
  → capability gradient + controls the suspected **alpha seat-bias** (n=2).
- Run 21 failure mode: **gamma "kingmaker over-grab"** (grabs treasury+defense →
  partial-coalition no-deal). → possibly `succ3c`, or full-mode test.

**Decision — is over-grab a bug or a finding?** Distinguishing principle:
*finding if it varies with skill; bug if structurally forced (capability-
invariant).* Diagnostics, cheap-first:
1. **(free) `verify_scenario_optimum` on succ3b** — does a BATNA-clearing deal
   exist that satisfies gamma *and* clears alpha+beta? Yes → finding (failure to
   find existing deal); No → bug (build succ3c, widen loser margin).
2. Cross-model variance from the tier ladder — over-grab declines with
   capability → finding; flat → bug.
3. Rank attribution — tracks skill across rotation → usable; tracks seat → bug.
- **Lean:** a robust finding ("kingmaker over-extracts and breaks the deal;
  skill = avoiding that") is worth more than a clean cell. Instrument to decide.

**Decisions captured:** budget has no hard cap (be mindful). See also §2 — the
coalition-value engine may convert the over-grab/deadlock into a *scoreable*
coalition outcome.

**Cross-refs:** NEXT_STEPS Tier 1 (succ-v3, succ2 full-mode); TUNING_LOG Runs
19–21; RESEARCH_NOTES Note 2; PAPER_PLAN §5.2, §5.6b.

---

## 2. Coalition-value scoring (§3.6, Note 2 Path B) 🔨/👁

**Why it matters.** Multi-party/coalition is now a **lead Paper 1
differentiator** (the concurrent cluster is bilateral).

**Status — engine built + locked.** `score_game()` coalition-exclusion path is
implemented and **locked by 23 unit tests** (Phase 47 / D-61); `coalition_values`
first-class in `scenario_analysis.json`; Three-Party Coalition v1 patched as
first consumer. The hard part is done.

**Decision — Paper 1 scope = live validation only.** Demonstrate, on a real
mixed-model game (three_party_coalition_v1), that the engine scores "AB
coalition forms, C excluded → coalition values" instead of collapsing to
all-BATNA. ~$1–2, doubles as §11.b Path A. 👁
- **Deferred** (not paper-blocking): builder `coalition_values` emission;
  runtime partial-coalition detection in `RoundSteppedFlow`; rationalizing the
  synthetic `coalition_formation` issue.

**Decision — apply `coalition_values` to succ3b** (deeper design discussion
deferred). Hypothesis: re-casting succ3b's "partial coalition → no-deal
deadlock" as a coalition outcome (coalescing pair gets coalition value; excluded
faction gets BATNA) could convert §1's over-grab *bug* into a scoreable
*finding* — unifying the distributive-discrimination gap with the coalition
engine.

**Risk.** Compiler may soften the coalition-coercive structure (v(AB) ≈ v(ABC))
into cooperative issues — the live validation reveals this; if so, a compiler fix
precedes a usable result.

**Cross-refs:** NEXT_STEPS Tier 1 (§3.6 row, §11.b Path A); RESEARCH_NOTES Note 2
Path A/B; PAPER_PLAN §5.6b; ASSESSMENT §3.6.

---

## 3. Publication builds — mechanism classifier + capability probe 🔨

**Reconciliation note.** Paper-only and net-new — NEXT_STEPS doesn't track these
(it's the project backlog; these are *measurement instrumentation* the paper
needs). Clearest case for keeping a separate paper-work doc.

**Decisions (this session):** build **sequentially — classifier first, then
probe** (operator runs one workstream at a time); **full 7-probe scope**; both
queued as **autonomous pirozhok phases** (🔨, codexbot loop) with tight specs —
not manual laptop work.

**A. Mechanism classifier (§4.1) — build first.** Binary-question decomposition
(BINEVAL-style): 5 atomic Y/N questions → deterministic derivation
(`closed / strategic_refusal / near_miss / incoherence / breakdown`); fixed
independent judge; per-question Cohen's κ vs the hand-labeled seed set
(14e/Run-15 exist). Linchpin of the scaffolding three-mechanism taxonomy (the
lead contribution). Bounded build.

**B. Capability probe battery (§4.2) — build second, full scope.** All 7
auto-gradable probes (Pareto-ID, logroll-ID, preference elicitation, BATNA
accept-or-walk, bluff detection, commitment tracking, consistency-over-horizon);
ground truth computable (no LLM-judge). Provides the **independent capability
axis** (avoids the mechanical anticorrelation in lift-vs-capability) + feeds
**construct validity** (probe-vs-Diplomat correlation). Commitment/consistency
probes scale by transcript length → predict where State-Manager/Reconciler
scaffolding is load-bearing.

**Risks.** Classifier judge-validation burden (mitigated: binary decomposition +
per-question κ); probe construct validity (mitigated: show the probe profile
*predicts* in-game bare performance).

**Cross-refs:** PAPER_PLAN §4.1, §4.2, §5.3, §5.7.

---

## 4. Construct validity + roster + hygiene 👁/🔨

**#1 lead evidence** — construct validity is what makes it a *benchmark*, not
anecdote. Bundles PAPER_PLAN §5.7 (validity) + §5.8 (roster) + §5.0 (hygiene).

**The unifying decision — ONE campaign.** §1 (distributive discrimination), §4
(construct validity), and §5 (harness lift) all need the *same* thing: the model
roster run across the scenario suite at good N. **Design a single campaign
matrix** — models × scenarios × {full, bare} × N, **seat-rotated** on the
multi-party/distributive scenarios — that simultaneously yields construct-validity
data, harness-lift data, and distributive/coalition discrimination. One spend,
three contributions. Biggest efficiency lever in the plan.

**Roster (decided).**
- OpenAI ladder: gpt-4.1-nano → gpt-5.4-mini → gpt-5.5
- Anthropic ladder: claude-haiku-4-5 → claude-sonnet-4-6 → **claude-opus**
- Cross-provider: deepseek-v3, deepseek-r1
- **opus** runs at least as a **baseline**, on a **non-saturated** scenario so
  there's headroom to see its behavior — i.e. **succ3b (sonnet 2/3)** or **WR-β
  (sonnet 0/3)**, *not* jsm1 (sonnet already ceilings 3/3).

**External index (decided): both** LMArena Elo *and* MMLU for the construct-
validity correlation (Elo = general-capability proxy; MMLU = the saturating
static baseline). Sweet spot: high-but-<1, with a negotiation-specific residual.

**Items & status.**
- Per-model benchmark score (aggregate close-rate / Pareto-eff / surplus) — 🔧 components exist; need aggregation + roster coverage.
- External-index correlation — 🆕 (headline; gated on roster campaign + index lookup).
- Discriminant validity (value-claiming / strategic-refusal ≠ general capability) — 🔧 data exists, formalize.
- Diplomat-vs-probe correlation — 🆕 (depends on §3 probe).
- Calibration / difficulty distribution — 🔧 (reported property, not novel).
- Hygiene: uniform temperature 🔧 (gpt-5.5 temp=1 confound); N≥10–20 + bootstrap CIs 🔧; external-index lookup 🆕 trivial; cost capture ✅ (Phase 49).

**Dependencies / order.** Construct validity is gated on (a) the unified roster
campaign and (b) the probe (§3) for the probe-correlation. So: build
classifier+probe (§3) → run the unified campaign → compute construct validity.

**Run-lane.** Hygiene/config + the correlation *analysis* are 🔨 (loopable); the
**campaign itself is 👁 supervised** (cost + judgment) — operator-initiated on
pirozhok. *Reconciliation:* same-provider ladders + external-index correlation
are **paper-only** (NEXT_STEPS has only the V3/R1 cells).

**Cross-refs:** PAPER_PLAN §5.0/§5.7/§5.8; NEXT_STEPS Run-17 follow-ups.

---

## 5. Harness-lift completion (mostly absorbed by the §4 unified campaign)

The core matrix — roster × {WR-β, jsm1} × {full, bare} × N — **is** the §4
unified campaign. Three residual items beyond it:

1. **Mechanism-classifier application** 🔨 — **decided: yes.** Run the §3 classifier
   *post-hoc* over the campaign transcripts to produce the three-mechanism
   breakdown (ceiling / redirect-failure / mismatch). Not a new run — an analysis
   pass; gated only on the §3 classifier. This is the scaffolding contribution's
   headline.
2. **Horizon sweep** 👁 — **decided: yes.** WR-β @ 4 / 8 / 12 rounds × ladder ×
   {full,bare}. The one axis the unified campaign doesn't touch; tests the
   original Note-1 intuition ("harness matters when you can't hold everything in
   memory"), never tested. On WR-β where lift is measurable at weak/mid.
   (12-round cells ~3× cost.)
3. **Per-module ablation** 👁 — **deferred (reviewer-response / stretch).**
   Decomposes harness lift by component ("which module supplies the missing
   reasoning") — sharpens the lead claim but is a refinement, costs N×modules
   extra runs, and was demoted post-Run-16 (no single module load-bearing for
   sonnet on jsm1). Pull forward only if a reviewer asks "which module drives the
   lift?".

**Cross-refs:** PAPER_PLAN §5.1–5.5; RESEARCH_NOTES Note 1.

---

## 6. Scenario-class breadth (Note 2 Path C) 🔨/👁

Broaden the suite beyond the current 3 shapes (WR-β single-Pareto cooperative;
jsm1 multi-Pareto cooperative; succ3b distributive/competitive).

**Decisions (this session):**
- **Add hidden-value / deception — PRIORITIZE (4th shape).** One faction holds
  private info that another's BATNA is fake; detecting+exploiting the bluff is the
  skill test. *Why first:* it exercises the **Adversarial reader** (a scaffold
  module) → directly supports the "scaffold supplies the specific missing
  capability" lead thesis; and a **multi-party** deception scenario is
  differentiated (the cluster's deception work — Abdelnabi greedy/adversarial,
  MERIT — is bilateral). Don't claim deception *novelty*; claim multi-party +
  scaffold-attribution.
- **Asymmetric-BATNA-with-walkaway — NEXT (5th shape).** One faction near-
  indifferent to a deal (high BATNA); wins by extracting max surplus before
  walking; weak models over-concede. Gives the **walk-away-discipline** profile
  axis (a value-claiming dimension).
- **Divorce showcase + pressure mechanisms (Phase 38 schema) — DEFER** (showcases,
  not paper-load-bearing).

**Suite after:** WR-β, jsm1, succ3b, **hidden-value** (+ **asym-BATNA-walkaway**
stretch) — spans cooperative → competitive → deception, 4–5 shape points for the
"lift = f(scenario × capability)" + construct-validity generality.

**Tooling.** Scenario-authoring loop is **complete** (Phases 46–48: reverse
builder + narrative shell) → authoring is largely **🔨 loopable**; operator
verifies the §4 properties (🔀) via `verify_scenario_optimum`.

**Cross-refs:** RESEARCH_NOTES Note 2 Path C; NEXT_STEPS Tier 1 (Path C row,
divorce, pressure); PAPER_PLAN §2.2 (richness axes), §5.2.

---

## 7. Deferred research questions (Notes 1 & 3, Path A) 👁

**Most are already absorbed** by the walkthrough: Note-1 horizon → §5 sweep;
deception → §6 hidden-value; context-exhaustion → partial via §5 sweep + §3
commitment/consistency probes; Note 2 Path A → §2 coalition live validation.

**Residuals + decisions:**
1. **4-faction scale cell — INCLUDE in Paper 1 (decided).** The one Note-1 axis
   (relationship complexity) nothing else touches; builder unblocked to 4–6
   (Phase 42) but no live runs. Shores up the **multi-party** lead claim —
   otherwise we run 3 factions while the incumbent (Abdelnabi) runs 6, a
   reviewer-bait weakness. At least one 4-faction scenario + a few cells. 👁
   (cost rises: O(N²) relationships, longer transcripts).
2. **Note 3 provider-consistency — fold into campaign discussion (decided).** The
   same-provider OpenAI ladder across multiple scenarios (unified campaign)
   partially answers "is the gpt-4.1-mini R3→R4 defection WR-specific or
   general?" as a **free analysis pass** — no new runs. Deeper checks (Trade
   Summit, all-Anthropic baseline) stay icebox.
3. **Everything else → future work (decided):** dedicated long-context scenario;
   repeated-game tournament / cross-game state.

**Cross-refs:** RESEARCH_NOTES Notes 1 & 3; NEXT_STEPS Tier 2 (scale) + icebox.

---

## 8. Tier-2 infra & icebox (below the line) — parked

**Decision:** none of this is on the critical path for Papers 1/2; all stays
parked / future work (nothing pulled into Paper 1).

- **Tier 2 infra:** tournament / TurnBasedFlow harness → future work (§7);
  reconciliation live validation → covered by the harness ablation, not needed;
  identify-the-blocker tool / provider-native structured output / Pareto-frontier
  annotation → infra niceties, none paper-critical.
- **Icebox (D-56, no new investment):** coaching product (test loop, `/revise:`,
  Telegram review gate); conversation-model evolution (Stage 2a/2b/3); strategy
  routing; **persona tuning** (→ Paper 3 behavioral steering, separate paper);
  exogenous-events pressure + cascade scoring.

**Project-only residual (folded from NEXT_STEPS, not paper-critical):** N4
(gpt-mini + pressure × 3 on jsm1); pricing audit (cross-provider pricing
accuracy); ASSESSMENT §3.4 persuasion / concession-curve signatures (LLM-judge
over transcripts); surplus-distribution investigation (why the neutral-on-
bottleneck faction extracts 52–55% of surplus); narrative re-skin prompt-quality
tuning (Phase 48 follow-on).

**Cross-refs:** NEXT_STEPS Tier 2 + Deferred (icebox); PAPER_PLAN §7b (Paper 3).

---

## 9. Consolidated execution sequence

Ordered across all sections, respecting dependencies. **Run-lanes:** 🔨 autonomous
on pirozhok (codexbot loop) · 👁 supervised (cost/judgment) · 🔀 mixed.

**Linchpin:** the **§4 unified campaign** — it produces construct-validity (§4),
harness-lift (§5), and distributive/coalition discrimination (§1) data in one
spend. Everything before it is a prerequisite; everything after is analysis.

**Phase A — Builds (sequential, 🔨):**
1. Mechanism classifier (§3A) + per-question κ validation.
2. Capability probe battery (§3B, full 7) + run across roster.

**Phase B — Scenario authoring (🔀, builder loop; verify §4 props each):**
3. Hidden-value / deception scenario (§6) — priority new shape.
4. 4-faction scenario (§7) — multi-party scale.
5. Apply `coalition_values` to succ3b (§2) + finalize succ-v3/succ3b; run the
   free `verify_scenario_optimum` over-grab diagnostic (§1).

**Phase C — Hygiene (small, 🔨/quick 👁):**
6. Uniform temperature; external-index (Elo + MMLU) lookup; confirm N-scaling
   dispatcher. (Cost capture ✅ done.)

**Phase D — The unified campaign (👁, big spend):**
7. Run the matrix: roster (OpenAI nano→mini→gpt-5.5; Anthropic
   haiku→sonnet→**opus on a non-saturated scenario**; V3, R1) × suite (WR-β,
   jsm1, succ3b, hidden-value, 4-faction) × {full, bare} × N≥10–20,
   **seat-rotated** on multi-party/distributive. Includes the succ3b tier ladder
   (§1) + opus baseline.
8. Coalition live validation on three_party_coalition_v1 (§2; doubles as Path A).
9. Horizon sweep: WR-β @ 4/8/12 rounds × ladder × {full,bare} (§5).

**Phase E — Analysis (post-campaign, 🔨):**
10. Apply the classifier to all transcripts → three-mechanism breakdown (§5).
11. Construct validity: aggregate per-model scores; Diplomat-vs-Elo/MMLU
    correlation; discriminant residual; Diplomat-vs-probe correlation (§4).
12. Note 3 provider-consistency analysis (free, on ladder data); resolve the
    over-grab bug/finding via cross-model variance + rank attribution (§1).
13. Per-model negotiation profiles (the multi-dimensional profile).

**Phase F — Figures + writing:**
14. Figures via the consolidated viz tooling (difficulty distribution, correlation
    scatter, profile radar, harness-lift curves, mechanism-mix bars).
15. Draft per PAPER_PLAN §6 outline; **Related Work** is the long pole; start
    **Meta internal publication review early** (silent long pole).

**Stretch / on-demand:** asym-BATNA-walkaway scenario + cell (§6); per-module
ablation (§5) if a reviewer asks "which module drives the lift?".

---

## 10. Reconciliation with NEXT_STEPS (done 2026-06-29)

NEXT_STEPS.md sections superseded by this doc and **retired to a pointer**:
- *Current state* + *Now — sequencing* → §1/§2 + the §9 execution sequence here.
- *Tier 1* (succ-v3, succ2 full, §3.6 coalition, §11.b Path A, Path C, Run-17
  V3/R1, N4, pricing audit, §3.4 signatures, surplus-distribution, divorce,
  rationalize-coalition) → §1–§6 + §8 residual here.
- *Tier 2* + *Deferred (icebox)* → §8 here.
- *Autonomous-loop phases COMPLETE* (closed build phases 46–48) → stays as
  closed-work record in `DEVLOG.md`.

NEXT_STEPS retains only: its header (workstream tags + D-56 direction), a pointer
to this doc, and the *Where things live* doc-routing index. **Open:** whether to
move this doc to root and delete NEXT_STEPS entirely (deferred — NEXT_STEPS is a
framework doc; kept as a thin pointer for now). README inventory could also gain
a WORK_SEQUENCING row (follow-up).
