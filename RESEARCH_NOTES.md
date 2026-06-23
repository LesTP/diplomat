# Diplomat — Research Notes

> Long-form conceptual notes that don't fit the action-oriented bias of
> `NEXT_STEPS.md`, the chronological log of `TUNING_LOG.md` /
> `DEVLOG.md`, or the metric-focused structure of `ASSESSMENT.md`.
>
> Each note has a stable heading + date stamp. Append new notes at the
> end; refine in place when evidence accumulates. When a thesis here
> converges on an actionable call, lift the call to `DECISIONS.md` or
> `NEXT_STEPS.md` and leave the rationale here.

---

## Note 1 — Harness contribution as a function of scenario complexity

**Date:** 2026-06-08
**Status:** Active thesis. Awaiting Run 14c-14e completion and Clanker Courts validation.
**Cross-refs:** `NEXT_STEPS.md` §10 (ablation runs), `ASSESSMENT.md` §3.4 (process signatures — the right instruments for measuring the effects discussed here), `DEVPLAN.md` Phase 34 close (bare-mode plumbing).

### Origin

Run 14a-b results (gpt-5.4-mini on Water Rights β-squeezed) showed
modest harness contribution: full mode 2/3 deals, bare mode 1/3 deals,
with both modes producing the **identical Pareto-optimal solution**
when they closed. The "harness helps the model find a better deal"
intuition didn't hold; harness contribution showed up only in
close-rate, not deal quality.

Operator question raised mid-experiment: *"From the previous runs it
sounds like the harness has limited application in this setup — three
players, three issues, three positions on each; bare model approaches
it closely. However I assume the harness would be meaningful in
setups where context is much larger and/or temporally longer? So that
you can't just keep everything in memory at once?"*

This note works through that thesis: **the current ablation is testing
the harness at its weakest application scale; harness contribution
should scale with scenario complexity along identifiable axes.** It
also proposes the methodology for validating that claim.

### The claim

**Harness contribution scales with scenario complexity along five
axes. The current Water Rights β-squeezed scenario tests harness
contribution at the bottom of all five — so the ablation result
("harness contribution is modest") is a finding *about that
scenario*, not about harnesses in general.**

The five axes:

1. **Context exhaustion.** Total prompt-token volume per generation
   call. When the raw transcript + persona + scoring tables fit
   comfortably in working memory (current: ~5k tokens out of 128k
   context window = 4% utilization), the model can reason over
   everything in attention. The harness's State Manager + Reconciler
   become extended-working-memory only when raw context approaches the
   model's effective working-memory limit. Modern LLMs handle 50k+
   tokens but recall degrades non-linearly; harness contribution
   should rise sharply around 30-50% context utilization.

2. **Relationship complexity.** Number of bilateral relationships the
   agent must track. With 3 factions, each agent has 2 counterparties
   — trivial to hold in attention. With 7 factions, each has 6
   counterparties, and "who said what to whom about which issue in
   which round" becomes O(N²). The Analyst's per-faction intelligence
   reports are the model's offloaded relationship-cognition cache —
   load-bearing at high N, redundant at N=3.

3. **Adversarial / deception structure.** Whether agents have
   incentives to mislead. Water Rights' persona prompts encourage
   direct negotiation; no scenario in the current matrix tests
   deception → reveal arcs. The Adversarial reader specifically
   stress-tests drafts against "what's the trap in this proposal?" —
   diagnostic only when traps exist. (Run 5's Trade Summit scenario
   exercised this but isn't in the current repo.)

4. **Temporal / asynchronous extension.** Wall-clock duration shouldn't
   matter to an LLM (context is context), but real async play —
   players away for hours, partial state, late-arriving messages —
   needs the State Manager to reconstruct "what's the current state
   and what was promised when I was away." Current synchronous
   self-play never exercises this. Clanker Courts may.

5. **Persona consistency over long horizons.** The persona prompt is
   reloaded fresh each generation call, but the model's *interpretation*
   of the persona drifts over long transcripts. The Reconciler's
   inconsistency-flagging ("you stated X in R3, NOT-X in R8") catches
   drift, but at 4 rounds the drift rarely accumulates enough to
   matter; at 12+ rounds it does.

### Evidence so far

| Scenario | Context utilization | Factions | Deception | Async | Horizon | Harness lift observed |
|---|---|---|---|---|---|---|
| Water Rights β-squeezed (4 rounds, 3 factions) | ~4% | 3 | None | No | Short | Modest close-rate diff; identical deals when closing |

Sample size: 6 runs (3 full + 3 bare with gpt-5.4-mini), plus 6 runs
in flight at the time of this note (gpt-4.1-nano). The full ablation
matrix (3 model tiers × 2 modes × 1 scenario × 3 runs = 18 runs)
provides a single data point on a single scenario.

**One data point on one scenario shape cannot validate or refute the
harness thesis broadly.** The thesis predicts harness contribution
should grow as we move along any of the five axes. To test, we need
scenarios that vary along those axes.

### Why the current scenario is "scale-1" on every axis

| Axis | Water Rights β-squeezed value | Implication |
|---|---|---|
| Context | ~5k of 128k tokens (~4%) | No working-memory pressure |
| Factions | 3 (each tracks 2 counterparties) | Trivial relationship matrix |
| Deception | None — persona prompts encourage straight talk | Adversarial module has nothing to find |
| Async | Synchronous round-by-round | State Manager's reconstruction value untested |
| Horizon | 4 rounds, ~21 messages | Persona drift doesn't accumulate |

Plus: the **deal landscape is degenerate** — 27 possible deals, 7
voluntarily acceptable, **exactly 1 Pareto-optimal** (alpha 16 / beta
18 / gamma 20). There is one "right answer" and the question is
binary: did the agent find it or not. No middle ground between
no-deal (sum 35 BATNA) and Pareto-optimum (sum 54). No coordination
problem between multiple acceptable solutions. The harness can't
demonstrate value in "helping the model find one of several
acceptable trade-offs" because there's only one.

This is **the easiest possible negotiation structure**, and at the
easiest scale on every axis. The "bare matches full" result for this
configuration is what the thesis predicts; it does not extrapolate to
larger configurations.

### Counter-considerations

Two reasons the scaling intuition might *not* fully hold:

1. **The harness components also grow with scenario complexity.** The
   Analyst's intelligence report, the Reconciler's state summary, the
   coaching-tag inventory — all scale roughly linearly with game
   complexity. At 12 rounds × 7 factions, the intel report might be
   8k tokens. If the harness produces N tokens of compressed
   summarization for what would have been N+ε tokens of raw
   transcript, the harness is wash on cost and only valuable if it
   provides better *organization* of the same information. Whether
   Diplomat's harness compresses well is testable but currently
   unmeasured.

2. **Frontier model improvements may close the gap.** Demonstrably
   better long-context recall in GPT-5.5 / Claude-Sonnet-4-6 /
   o1-style reasoning models suggests harness contributions like
   "remember the R3 commitment during R10 generation" will be smaller
   on future models than on current ones. The harness might be
   load-bearing in 2026 and obsolete in 2028 — same story as
   ReAct/Reflexion scaffolds that mattered for GPT-3.5 and matter
   less for GPT-4o. The bare-vs-full delta we're measuring is
   model-cohort-specific.

These don't invalidate the thesis — they qualify it. The right framing
is: **harness contribution = f(scenario complexity, model generation,
harness compression quality)**. We're measuring along one axis at a
time; the others are held implicitly fixed.

### Connection to Clanker Courts

Clanker Courts (per its `PROJECT.md`) is shaped along several of the
high-complexity axes simultaneously:

- **N×(N-1) bilateral private message channels** between factions →
  high relationship complexity (axis 2)
- **Commitment register as typed shared state across rounds** →
  explicit promise-lifecycle tracking, more rounds than Diplomat's 4
  → axes 1 + 5
- **Per-opponent trust modeling** → relationship state per
  counterparty (axis 2)
- **Game-state graph** (cities, troops, fog-of-war) → much larger
  state than Diplomat's 3-issue scoring table → axis 1
- **Deception detection** as a designed feature → axis 3
- **Potentially async play** if deployed on a platform with operator
  away-time → axis 4

If the scaling thesis is right, Clanker Courts is where Diplomat's
harness investment should pay off most. **The current bare-vs-full
result for Water Rights likely underestimates harness value for
Clanker Courts** — possibly by a large margin.

This has a strong implication: **don't decide "harness is theater,
drop the investment" based on the Diplomat-Water-Rights result
alone.** That decision should wait until Clanker Courts has been
running long enough to provide its own evidence.

### Validation path

To test the scaling thesis directly within Diplomat (not waiting for
Clanker Courts to mature), the cheapest investment is the **Reverse
Scenario Builder** (`NEXT_STEPS.md` §8) plus targeted game-theoretic
scenarios:

1. **Build §8 reverse builder.** Parameterized scenario generation
   keyed to outcome shape ("I want a 3-faction game where the unique
   Nash sums to 28 but the unique Pareto sums to 54"). One-time
   investment, ~Phase-33-sized.

2. **Compile a small library of complexity-axis scenarios:**

   | Scenario shape | Axis tested | What harness should help with |
   |---|---|---|
   | **Nash ≠ Pareto** (3-faction prisoner's-dilemma flavor) | Adversarial (axis 3) | Adversarial reader catches "you're being suckered"; Reconciler tracks promise → defection lifecycles |
   | **Multiple distinct Pareto solutions** with different distributions | Coordination (related to axis 2) | Analyst's per-faction intel diagnostic: "which faction is pushing which Pareto?". Tests §3.4 surplus-distribution question directly |
   | **Long-horizon Water Rights** (12 rounds instead of 4) | Context + persona drift (axes 1 + 5) | State Manager + Reconciler hold cross-round commitment state |
   | **Wide-Water-Rights** (5 factions × 5 issues × 3 outcomes) | Relationship + context (axes 2 + 1) | Analyst intel becomes load-bearing for tracking 5×4=20 counterparty positions |
   | **Repeated-game tournament** (3 sequential games with same factions) | Reputation + cross-game state (axes 4 + 5) | Cross-game persistence (doesn't exist yet — would need extending State Manager) |
   | **§2-style pressured** (round-cost decay) | Coordination — adds middle ground between Pareto and BATNA | Tests whether agents accept sub-optimal voluntary deals; harness might help "Analyst surfaces that sum-48 deal is acceptable since delay erodes everyone by 2/round" |

3. **Re-run the bare-vs-full ablation matrix** (3 model tiers × 2
   modes × 3 runs = 18 runs per scenario, ~$30-60 per scenario at
   current rates) on each new scenario. Compare harness contribution
   across scenario types. The thesis predicts **strictly larger
   full-vs-bare deltas on the richer scenarios**.

Total cost of this validation: roughly the cost of Phase 33 + Run 14
(~$50-150 + operator time + ~Phase 35 build for §8). Comparable to
one phase + one experimental campaign.

### What would refute the thesis

To make this a real thesis rather than a just-so story, name what
would falsify it:

1. **Richer scenarios show *no* larger harness contribution than Water
   Rights β-squeezed.** Multi-Pareto / Nash≠Pareto / long-horizon
   scenarios produce roughly the same close-rate delta (e.g., still
   ~33% full vs ~17% bare ratio). If true, the harness genuinely
   isn't load-bearing along the predicted axes; we'd need to
   re-examine which design assumption was wrong.

2. **Per-module ablation finds no single module is load-bearing.**
   Phase-35 candidate per-module experiment (full minus Extraction,
   full minus Analyst, full minus Reconciliation, etc.) shows every
   single-module removal produces near-identical outcomes to full.
   That would suggest the harness is genuinely composed of components
   that don't individually matter — strongly anti-thesis.

3. **Strong frontier model + bare > weak frontier model + full,
   consistently across all scenario shapes.** If model-quality
   dominates harness contribution uniformly regardless of scenario
   complexity, the thesis ("harness helps more at scale") is wrong
   and a simpler thesis applies ("buy bigger models").

The Run 14e (claude-sonnet-4-6) result is the first data point on #3
— if sonnet-bare matches sonnet-full despite the scenario being scale-1,
that's evidence FOR the thesis (model strength compensates for what
harness would do here). If sonnet-full ≫ sonnet-bare, that's
evidence AGAINST (harness contributes even at the strong tier on this
scenario, so the scale-dependence story is suspect).

### Open questions

- **How does harness compression scale?** Measure Analyst-intel-token-cost
  vs raw-transcript-token-cost across game lengths. If harness produces
  more tokens than it saves, the "extended working memory" story
  breaks down at scale.

- **What's the right scenario shape to test "harness compensates for
  weak model"?** Current 14c result (gpt-4.1-nano on Water Rights):
  first run closed the Pareto optimum cleanly. If nano can find the
  unique optimum with harness as easily as gpt-5.4-mini, the "weak +
  harness ≈ strong + bare" hypothesis gains weak support. Need wider
  matrix on richer scenarios to know.

- **Where does Clanker Courts fall on the five axes empirically?**
  PROJECT.md describes the intent, but operational reality (how many
  factions, how long games, how much deception) will determine where
  Clanker Courts sits and how much harness contribution it actually
  demands.

- **Is "harness is theater for current scenario" itself a useful
  finding?** Could pivot Diplomat toward "minimal-harness reference
  implementation" while Clanker Courts continues with full harness —
  effectively using Diplomat as a control for Clanker Courts'
  experimental design. Worth considering as a third project-direction
  option post-Run 14e (alongside "pivot away from harness" and
  "continue building harness for Clanker Courts").

### Lift-to-action when ready

When this thesis converges on a project-direction call, lift the
decision to `DECISIONS.md` and the implementation steps to a new phase
in `DEVPLAN.md`. Until then, this note holds the framing.

Provisional next investment direction (if Run 14e confirms the
scale-1 result generalizes across model tiers within this scenario):
**§8 reverse builder → game-theoretic scenarios → re-ablation**. Per
the validation-path table above. Roughly Phase 35.

### Amendment 2026-06-12 — Run 16 partial refutation

Run 16 (jsm1 ablation matrix; see `TUNING_LOG.md`) ran the cheapest
direct test of this thesis: take a scenario richer than WR-β on at
least one axis (multi-Pareto vs single-Pareto) and re-run the bare-vs-full
ablation. Result: **sonnet-bare = sonnet-full = 3/3 on jsm1, identical
deal every run, zero variance.** The thesis as written predicted harness
contribution should *grow* on the richer scenario; it went from 0 (WR-β)
to 0 (jsm1) at the strong tier instead.

The weaker tiers reinforce the partial refutation rather than diluting
it. Weak-tier harness lift on jsm1 was +33% (1/3 vs 0/3) vs +67% on WR-β
— smaller, not larger, on the "richer" scenario. Mid tier is 0/3 in both
modes on jsm1 (harness-immune failure) vs 2/3 vs 1/3 on WR-β (clear
harness lift). The "harness contribution grows with complexity"
prediction failed at every tier on the one axis Run 16 varied.

**What this refutes:** the thesis's strongest form ("harness contribution
strictly grows with scenario richness, along every axis").

**What this does NOT refute:** the thesis's weaker form ("harness can
become load-bearing on scenarios with cognitive demands the model can't
meet unaided"). Run 16 only varied multi-Pareto vs single-Pareto; the
four other axes (context exhaustion, relationship complexity, deception,
horizon/persona drift) remain untested. A 5-faction × 12-round scenario
with deception incentives might still produce the predicted harness
lift; Run 16 has nothing to say about that.

**Re-stated thesis:**

> **Harness contribution = f(scenario shape, what the model already does
> well).** When the scenario rewards reasoning the model finds naturally
> — sonnet on jsm1's multi-Pareto coordination — the harness is
> redundant regardless of how "rich" the scenario is on other dimensions.
> When the scenario rewards reasoning the model needs scaffolding to
> surface — weak/mid OpenAI finding asymmetric concessions on WR-β — the
> harness is load-bearing. Note 1's five axes (context, relationships,
> deception, horizon, persona drift) are five candidate dimensions that
> can plausibly produce reasoning a model can't do unaided, but each
> axis-meets-model pair is an empirical question, not a derivation.

This is strictly weaker than the original claim. It still predicts
harness lift at Clanker Courts scale (more factions, longer horizon,
deception structure all in play), but with a clear caveat: lift only
materializes if at least one axis crosses the model's unaided
capability boundary. Sonnet's existing capabilities at scale may erase
the predicted lift even there — that's the empirical question Clanker
Courts will answer.

**What the new framing changes about the validation path table:**

The library of complexity-axis scenarios proposed above is still the
right next-investment direction. But the cell-by-cell prediction should
be revised:

| Scenario shape | Original prediction | Revised prediction |
|---|---|---|
| Nash ≠ Pareto (axis 3) | Larger harness lift | **Conditional** — only if the deception structure produces reasoning the model can't do unaided. Likely yes for weak/mid; uncertain for sonnet. |
| Multiple distinct Pareto (axis 2) | Larger harness lift via coordination | **Refuted by Run 16.** Sonnet finds balanced consensus without harness. Could still produce weak/mid lift on a different multi-Pareto scoring topology where balanced consensus is less attractive. |
| Long-horizon Water Rights (axes 1+5) | Larger harness lift via persona drift / commitment tracking | **Likely yes for OpenAI Generators** (R3→R4 defection is a documented OpenAI failure mode that long-horizon would amplify). Uncertain for sonnet. |
| Wide-Water-Rights (axes 1+2) | Larger harness lift via intel compression | **Conditional** — needs Phase 41/42 to even build. Most likely candidate for "richer scenario produces harness lift" if Note 1 is mostly right. |
| Repeated-game tournament (axes 4+5) | Larger harness lift via cross-game state | Untested. Cross-game state harness doesn't exist yet (Phase 40 indefinitely deferred). |
| §2-style pressured (Phase 38) | Larger harness lift via concession surfacing | **Specific testable prediction:** N4 (gpt-mini + Phase 38 pressure × 3 on jsm1). If pressure unsticks mid-tier on jsm1, that's harness-via-scenario-design lift; if not, the mid-tier-stuck pattern is robust and Phase 38 has lower leverage than hoped. |

The cheapest single next test remains the same: **N4 (gpt-mini + Phase
38 pressure on jsm1, ~$1.50)** — but its interpretation now sits in the
revised framework above rather than the original "richer = more lift"
prediction.

**Counter-considerations to the amendment itself:**

1. **n=3 per cell is noisy.** Run 16 cells had identical scores across
   runs (zero within-cell variance for the closing cells), so the
   determinism question is well-answered, but the cell counts are still
   small. A single 1/3 outlier could shift framing.
2. **jsm1 may have a degenerate attractor.** Balanced-consensus deal
   (`{α:19, β:18, γ:22}`) is dramatically better than the other two
   Pareto deals on aggregate score — it's not really a "coordination
   problem with multiple acceptable answers" in the way the spec
   intended (it is both highest-sum *and* most balanced, so it dominates).
   N5 (jsm-v2 with multiple **equal-/near-equal-sum** Pareto deals, each
   favoring a *different* faction, and no equal-split Schelling point)
   would test whether the harness-zero result for sonnet is specific to
   jsm1's particular scoring topology — and is also the precondition for
   the §3.5 rank lens / `pareto_outcome_diversity` to produce any signal.
3. **Sonnet at the time of Run 16 may not be sonnet at scale.**
   Frontier-model improvements (per the original counter-considerations)
   could close the gap for *future* sonnet generations on harder
   scenarios. The harness might be load-bearing for sonnet-2027 on
   Clanker Courts even though it's redundant for sonnet-2026 on jsm1.
   Argues for empirical re-test on every model generation, not a
   one-time "harness theater" call.
4. **Both sonnet cells are saturated — the "0 → 0 harness contribution"
   is unmeasurable, not measured (added 2026-06-16).** WR-β sonnet sits at
   the floor (full 0/3 = bare 0/3, via strategic refusal) and jsm1 sonnet
   at the ceiling (full 3/3 = bare 3/3). Neither cell has headroom to show
   a harness *lift*, so sonnet contributes no usable evidence on whether
   harness contribution grows with richness. The Run 16 "partial
   refutation" therefore rests on the weak/mid tiers (which do have
   headroom) plus the *absence* of a ceiling-breaking effect at strong
   tier — it is not the clean "0 → 0" decline the amendment's prose
   implies. The amendment's headline still holds on the weak/mid evidence,
   but should not be quoted as a strong-tier result.
5. **Tier is confounded with provider (added 2026-06-16).** The ablation
   ladder is gpt-4.1-nano (weak, OpenAI) / gpt-5.4-mini (mid, OpenAI) /
   claude-sonnet-4-6 (strong, *Anthropic*). Given Runs 9–11 established
   provider as a first-order variable (OpenAI defects R3→R4; Anthropic is
   consistent / over-cooperates), any "strong-tier" effect cannot be
   separated from an "Anthropic" effect. A same-provider tier ladder
   (OpenAI nano→mini→gpt-5.5, and/or Anthropic haiku→sonnet→opus) is
   required before tier-vs-provider claims about the harness are clean.
   This is the highest-value addition to the matrix.
   **Update (Run 18, 2026-06-22):** tested on the bare axis — `gpt-5.5`
   (strong, OpenAI) closes WR-β bare 3/3 where sonnet (strong, Anthropic)
   floors 0/3. So the WR-β strong-tier "strategic refusal" was
   **sonnet-specific, not a strong-tier property** — the confound was real
   and material. Caveat: gpt-5.5 only accepts temperature=1 (vs the matrix's
   0.7); a temperature flip of that magnitude producing 0/3→3/3 is
   implausible, so the uniform-temp confirmation was judged low-value and
   skipped. Strong cells ceiling bare (3/3), so full-mode harness *lift*
   stays unmeasurable on either provider.

### Footer 2026-06-16 — Under D-56 (benchmark direction)

Note 1 stays open as an active thesis container under `DECISIONS.md` D-56 (benchmark direction commit). What changes is the *framing* of the four untested axes (context exhaustion, relationship complexity, deception, horizon / persona drift):

- **Pre-D-56 framing:** abstract validation questions — "would the harness-contribution thesis still hold if we tested richer scenarios?"
- **Post-D-56 framing:** **Tier-1 benchmark scenario-design work** — each untested axis is a concrete scenario class the benchmark needs in its scenario library to credibly differentiate models. Phase 41/42 (scale-matrix verification + algorithm fixes for 4+ factions / 4+ issues) is the gating infrastructure; once it lands, scenario authoring along each axis proceeds.

The Run 16 amendment's "revised thesis" — *harness contribution = f(scenario shape, what the model already does well)* — remains the canonical formulation. Future campaign findings should refine this in place rather than overwriting; the original five-axis claim is preserved here for historical context.

**What's open under D-56** (vs being "speculative validation questions"):
- Build scenarios along each axis using `scenario_authoring.scenario_builder` post-Phase-41/42.
- Re-run bare-vs-full ablation matrices on those scenarios.
- See whether the harness-contribution function picks up new structure beyond the current "scenario rewards reasoning model can/can't do unaided" frame.

**What's closed under D-56:**
- The product-direction fork ("does Note 1 say we should pivot away from the harness?") — D-56 commits to keeping the harness because Block C scenario-design is the primary surface and the harness is the substrate for that. Note 1's "is harness theater" framing was a coaching-product question; under benchmark framing the harness is an *experimental variable* (full vs bare) rather than a production component to defend.

---

<!-- Append new notes below this line. Use ## Note N — Title format. -->

---

## Note 2 — Competitive vs cooperative scoring; making mixed-model runs produce winners

**Date:** 2026-06-12
**Status:** **RESOLVED 2026-06-16 — see "Resolution: D-56 commits to benchmark direction" amendment at end of note.** Operator chose the benchmark direction (Note 2 §"Two coherent product directions" option 2: "Diplomat as model-evaluation harness"). Note 2's framing of the agreeableness-bias structural problem, four design options, three paths forward, and two coherent product directions remains the canonical rationale for that decision; only the *fork* itself is closed.
**Cross-refs:** `DECISIONS.md` D-56 (project-direction decision lifted from this note), `NEXT_STEPS.md` §11 (tactical pointers per Path A/B/C), `ASSESSMENT.md` §3 (scoring lenses §3.5 + §3.6 queued per Path B; §5 workstream tiers reframed per D-56), Run 6/7 archived findings (Three-Party Coalition first surfaced the coalition-exclusion gap).

### Origin

Operator question 2026-06-12, mid-Run-17: *"right now it sounds like our game setup is testing for agreeableness… if we play two or three models where one is bad at negotiating, we end with a deadlock and everyone loses, rather than that one bad model loses and the others win. Is there a game setup that would allow the models to compete?"*

The question identifies a structural property of the current harness that the existing test campaigns have systematically obscured by using homogeneous populations (every Run 14, 15, 16, 17 cell uses the same model for all three factions). This note works through the structural diagnosis, the design options, the harness-engineering gap that complicates the cheapest fix, and the two coherent product directions Diplomat could pursue.

### Diagnosis — why the current setup rewards agreeableness

Three structural reasons compound:

1. **Unanimity requirement.** `score_game()` requires every faction to agree on every issue. Any holdout kills the deal and *everyone* falls to BATNA. The "bad" model's failure mode = "blocks a deal" → punishes everyone equally, including the good models. Two good models can't form a coalition and split the value while excluding a weak partner — they fall to BATNA together with the holdout.

2. **BATNA-floor scoring asymmetry.** `score > BATNA = WIN`, `score ≤ BATNA = LOSE`. The discrete win/lose distinction means "barely beat BATNA" and "extracted maximum surplus" both register as WIN; "missed by an inch" and "missed by a mile" both register as LOSE. The ASSESSMENT.md operator decision 2026-06-01 ("no agreement = no agreement, doesn't matter if missed by an inch or a mile") is honest about this but it's what makes the lens cooperative.

3. **Pareto-efficiency metric measures the group, not the individual.** `negotiated_surplus_share` is a *group-level* outcome — "did the team leave value on the table." A homogeneous run answers "is this model class capable of finding joint value?" cleanly. A heterogeneous run produces a single group-level score that flattens individual model differences.

All four ASSESSMENT §3 scoring lenses (BATNA-relative, Pareto efficiency, vs-naive baseline, process signatures) compound this — they measure *whether* the group reached good outcomes, not *who* did better than whom.

### What we actually have: `--per-faction-providers` already supports mixed populations

Every Run 14, 15, 16, 17 cell to date uses the same model for all three factions. This was an experimental convention ("isolate model effects by holding population homogeneous"), not a harness limitation. `--per-faction-providers` was designed for heterogeneous populations and works today.

**This convention is what makes Diplomat agreeableness-flavored at the experimental level, not the underlying harness.** The harness's structural problem (#1 above — unanimity) is real and separate; this is the convention-level problem.

### Four design options for competitive scoring

**Option A — Coalition-coercive scenarios (uses existing infra at the scenario layer).**
Scenarios where `v(2-party) ≈ v(grand)` — two-party coalitions are nearly as valuable as the grand coalition, so excluding the weakest player costs almost nothing per included player. The clean game-theoretic template is Susskind's Three-Party Coalition (already in `scenarios/three_party_coalition.md`, used in Runs 6-7): `v(AB)=118`, `v(AC)=84`, `v(BC)=50`, `v(ABC)=121`. Existing infra runs the scenario but cannot score coalition-exclusion outcomes — see Path B below.

**Option B — Rank-based scoring lens (5th lens for ASSESSMENT §3).**
Add `rank_among_factions` — 1st/2nd/3rd by absolute score per game, accumulates over multiple games. Skill = "consistently score higher than your opponents." Already implicit in per-faction scores; needs aggregation + reporting + optional position-rotation harness to control for scenario asymmetry across faction slots. ~50 LOC build. Meaningful only in mixed populations AND only when scenarios have score asymmetry (your win is at least partly someone else's loss).

**Empirical update (Run 19, 2026-06-22):** The rank lens (Option B) shipped and ran end-to-end on the first mixed-model experiment (sonnet / gpt-5.4-mini / deepseek-v3, seat-rotated, on the new constant-sum `succ` scenario). It confirmed the precondition above is *binding but not sufficient*: all 6 games converged on the same "everyone takes their own priority asset" deal, so ranks were seat-determined, not skill-determined. Removing the *mathematical* dominant attractor (constant-sum payoffs) did not remove a *salience* focal point. So "score asymmetry" alone is not enough - the scenario must also lack an obvious coordination focal point, which a 1:1 faction-to-priority mapping fails to provide. Path C scenario design needs **priority collision** (a contested asset) for the rank lens to surface skill. See `TUNING_LOG.md` Run 19.

**Empirical update (Run 20 + framing, 2026-06-22):** Following Run 19, `succ2`
added a HARD priority collision (alpha & beta both want the heartland) to
destroy the focal point. It did - but the contest then *deadlocked* (5/6 bare
games no-deal). So the two distributive scenarios fail to discriminate for
opposite reasons: succ converges on a focal deal (no variation), succ2
deadlocks (no deal). **Key framing distinction - whether deadlock is bad
depends on the question.** For the rank-lens / model-comparison goal (Option B
above), you want the *sweet spot*: deals close AND vary by skill. For the
bare-vs-full harness-contribution goal (Note 1), a bare-deadlock scenario is
*desirable* - it leaves headroom for the harness to demonstrate value (cf. the
section 10 finding that lift is only measurable where bare is unsaturated). So
succ2 may be the wrong scenario for Option B but the *right* one for a Note-1
harness test: run it full-mode and measure close-rate lift. Two scoring bugs
were fixed along the way (deal_reached normalization, below-BATNA deal
rejection); the aggregator now excludes no-deal games. See `TUNING_LOG.md`
Runs 19-20.

**Option C — Adversarial-scoring scenarios (structural shift in scenario design).**
Scenarios where the score function is at least partly **zero-sum** — divide a fixed pie, ranked-choice voting on a single outcome, allocation of a contested resource. Current scenarios have low zero-sum content; even Water Rights' payment_structure (the most zero-sum issue) doesn't fully zero out. Extending ScenarioSpec to support "fixed pie" issues where outcome scores sum to a constant would enable reverse-builder targeting of these. Tradeoff: pure zero-sum is less interesting negotiation (no logrolling) but cleaner skill testing.

**Option D — Tournament harness (largest, most ambitious).**
Multi-game round-robin with position rotation. Each model plays each faction position across multiple scenarios; final ranking by cumulative score. Academic gold standard for game AI (chess Elo, poker AIVAT). Diplomat becomes a model-evaluation benchmark instead of (or alongside) a negotiation product. Phase 40 ("cascade scoring — cross-game state") was deferred "indefinitely — wait for tournament use case." This is that use case.

### The fundamental problem — even Option A on the existing scenario needs a harness change

The cheapest test (Option A: compile Three-Party Coalition with mixed models and rotated positions) hits a deeper blocker: **the harness doesn't actually score coalition-exclusion outcomes.** The Diplomat compiler maps any narrative (including the Susskind coalition-formation narrative) into the harness's standard frame: *issues with per-faction-scored outcomes requiring unanimous agreement.*

When the compiler runs on `three_party_coalition.md`, it produces 3-4 issues (e.g., `membership`, `leadership`, `profit_split`) each with outcomes all three factions must agree on. The deal-detection logic in `game_environment.score_game()` requires all three factions to agree on every issue. **A+B aligning while C dissents → no deal → everyone scores BATNA, not "A+B split 118."**

Run 7's archived headline captured this exact phenomenon: *"no deal because A+B align but C dissents (game-theoretically reasonable for coalition exclusion)."* The harness *noticed* the coalition structure was working game-theoretically but couldn't *score* it as a coalition outcome.

**This means mixed models on coalition-narrative ≠ coalition-exclusion game in the current harness.** Same agreeableness trap, different scenario.

### Three paths forward

**Path A — Run mixed-models on existing scenario anyway, accept the unanimity limitation.**
9 cells (3 model permutations × 3 rotated positions) on compiled Three-Party Coalition. ~$3-5, ~60 min. What we can still learn: *behavioral patterns within the unanimity frame* — which model pairs recognize each other as competent partners (via transcript analysis), differential R4 final positions, who holds out and why. Produces real signal but not "X model wins, Y model loses" outcomes. Closer to mixed-population behavioral diff study than to competitive benchmark.

**Path B — Engineer coalition-exclusion scoring in the harness.**
The actual structural fix. Extend `scenario_analysis.json` schema to include `coalition_values: {AB: 118, AC: 84, ...}` alongside per-issue scoring; modify `score_game()` to detect partial-agreement coalitions (via final-round position alignment on a designated "coalition membership" issue) and assign coalition value to the agreeing faction subset; assign BATNA or coalition-specific exclusion payoff to excluded faction. 1-2 day build. Unblocks proper competitive mixed-model tests on coalition-coercive scenarios. Worth a phase number when promoted.

**Path C — New scenario class that doesn't need harness changes.**
Scenarios where unanimity-deal scoring naturally produces differential outcomes:
- **Distributive bargaining** ("divide $100, each faction proposes a 3-way split, deal closes if all agree on identical numbers"). Skill = anchor + concede precisely. Bad models leave money on the table, good models extract more.
- **Asymmetric BATNA + walkaway option**: design WR-style scenarios where one faction's BATNA is high enough that they're INDIFFERENT to deal vs no-deal. They "win" by extracting maximum surplus before walking; bad models concede too much.
- **Hidden-value asymmetry**: one faction has private info that another's BATNA is fake. Detecting + exploiting that bluff is a clean skill test.

Cheaper than Path B (only new scenario design with the existing reverse builder + Phase 38 pressure); less direct than Path B for coalition-formation specifically.

### Two coherent product directions

Diplomat's project hypothesis has been ambiguous between two distinct purposes:

| Direction | Audience | Success metric | Native scoring |
|---|---|---|---|
| **Operator coaching tool** (current PROJECT.md vision) | Human operator playing one faction | Their faction does well in real games | Cooperative — operator's faction maximizes their own score, often via joint-value creation |
| **Model-evaluation harness** | Researchers comparing model classes on adversarial negotiation | Produces differential rankings between models | Competitive — rank-based scoring across mixed populations on coalition-coercive / zero-sum scenarios |

These aren't mutually exclusive — same infrastructure, different scoring conventions and different scenario design priorities. But they have different evaluation signals, different scenario design priorities, and different next-phase work.

The current Run 14 / 15 / 16 / 17 campaign is *de facto* a model-evaluation harness operating under the operator-coaching tool's scoring conventions, which produces the homogeneous-population convention and the "agreeableness reward" structure. Recognizing the tension explicitly enables a clean decision.

### What would refute this thesis (or change which path is right)

1. **Run 17 in-flight + n=3 expansion shows mixed populations on existing scenarios already produce clear winners.** If transcripts from heterogeneous mixed runs (still future work) show one model consistently outperforming on absolute score, the rank-based scoring lens (Option B, ~50 LOC) is sufficient — no harness change needed. The competitive direction is already viable on existing scenarios; it just needs a new lens to surface it.

2. **Path A produces no signal differentiation at all.** If 9 cells of mixed-Three-Party-Coalition all hit "no deal, everyone at BATNA," the unanimity blocker is fully load-bearing on coalition scenarios → Path B (harness engineering) is the actual unblock, not just a nice-to-have.

3. **Distributive bargaining or asymmetric-BATNA scenarios (Path C) produce clear rank-discriminating outcomes on existing harness.** If we can get competitive behavior from scenario design alone without harness changes, Path C is the cheapest competitive direction and Path B drops in priority.

### Cheapest immediate test (when ready to act on this note)

Run Path A — compile Three-Party Coalition narrative + mixed-model + rotated positions, n=1 calibration first. ~$1-2, ~30 min. Tells us:
- Does the existing scenario + mixed population produce *transcript* differentiation (different coalitions form across position rotations), even if scoring still falls to BATNA?
- Does the compiler produce a scoring table that actually preserves the coalition-coercive structure (`v(AB)≈v(ABC)`), or does it soften it into cooperative-flavored issues?

If transcript differentiation is rich → Path A at n=3 (9 cells) is enough for a behavioral-diff study; Path B becomes a follow-up to make the scoring match the transcripts.

If transcript differentiation is weak → compiler's softening of the coalition structure is the bottleneck; need Path C (new scenario class) or Path B (harness change) before mixed-model tests are informative.

### Open questions

- **How much does the position rotation in Path A actually control?** Faction roles in the existing scenarios aren't symmetric (alpha, beta, gamma have different scoring tables). A 3-position rotation × n=3 = 9 runs may not be enough to disentangle model effects from position effects. Tournament harness (Option D) handles this via repeated rotation; the cheap Path A test does not.
- **Is there a Path between B and C?** "Augment existing scenarios with a fixed-pie zero-sum overlay" — keep the integrative scenarios as-is but add a zero-sum bonus pool that goes to the highest-scoring faction. Adds rank-discriminating outcomes without abandoning the cooperative-skill testing the current scenarios do well. Worth scoping if both B and C feel expensive.
- **Does Run 17's mid-flight DeepSeek V3 finding (sonnet-class behavior on both scenarios) change the design priority?** If DeepSeek V3 ≈ sonnet at 1/10 cost, the cost-economics argument for competitive testing (find the cheapest model that exhibits desired capabilities) gets sharper. Argues for prioritizing whatever direction makes cost-comparison rankings cleanest.

### Lift-to-action when ready

When this thesis converges on a project-direction call, lift the decision to `DECISIONS.md` and the implementation steps to a new phase in `DEVPLAN.md`. Most likely shape:
- **Decision:** Pursue model-evaluation direction as a co-equal use case alongside operator coaching (not abandoning either), with explicit scoring-convention separation.
- **Phase X:** Implement Path B (coalition-exclusion scoring) as a 1-2 day build.
- **Phase X+1:** Implement Option B (rank-based scoring lens) as a small follow-up.
- **Operator backlog:** Author 2-3 new scenarios under Path C class (distributive, asymmetric-BATNA, hidden-value) using existing reverse builder.

Until then, this note holds the framing.

### Resolution 2026-06-16 — D-56 commits to benchmark direction

Operator decision after the 2026-06-16 consolidation discussion: **commit to the benchmark direction** (Note 2's "Diplomat as model-evaluation harness" option from §"Two coherent product directions"). The "co-equal use case alongside operator coaching" framing in the original Lift-to-action paragraph above is **superseded** — the operator chose a clean direction commit rather than parallel pursuit, on the grounds that parallel pursuit was producing the thrashing pattern that motivated the consolidation discussion in the first place.

**Decision details lifted to `DECISIONS.md` D-56.** Summary:
- Coaching product (live games, coached self-play, `/revise:`, persona drift, Clankmates) deferred — infrastructure preserved, no new investment.
- Benchmark direction promoted to primary investment surface (Block C in `ASSESSMENT.md` §5).
- Note 2's Path B (coalition-exclusion scoring engine) and Path C (adversarial-scoring scenario class) both queued as Tier 1 in `NEXT_STEPS.md` §11.
- ASSESSMENT §3 gains §3.5 (rank-among-factions) and §3.6 (coalition-value scoring) as queued lenses; existing four lenses kept unchanged.
- Note 2 itself stays in this file as canonical rationale — the framing (agreeableness-bias structural problem, four design options, three paths forward, two product directions) remains the explanation for *why* D-56 chose what it did. Only the fork is resolved.

**What this resolution does NOT close:**
- Path B build itself (~1-2 days, queued)
- Path A calibration (mixed-model Three-Party Coalition probe — patched scenario JSON is ready, dispatcher needs heterogeneous-population extension, hasn't run yet)
- Path C scenario authoring (~3 new scenarios needed)
- The open questions above remain open under the benchmark direction; they're now empirical questions to answer with future campaigns rather than fork-deciding questions.

**Note 2 stays open** as an active thesis container for future Path A/B/C evidence. Append new findings under their respective Path headers when campaigns run.

---

## Note 3 — Provider consistency as a deal-making variable

**Date:** 2026-06-23 (consolidated from the former `NEXT_STEPS.md` §1.7 / §1.8; evidence in `TUNING_LOG.md` Runs 9 / 10 / 18)
**Status:** Active finding. The follow-up *tests* are deferred under D-56 (they would still produce benchmark-relevant data, but are not Tier-1 priority).
**Cross-refs:** `TUNING_LOG.md` Runs 9 / 10 / 18, Note 1 provider-confound bullets (2026-06-16 + Run 18 update), `DECISIONS.md` D-56.

### Finding

Run 10 B' (α-squeezed BATNAs, beta's Generator re-routed from OpenAI
`gpt-4.1-mini` to Anthropic `claude-haiku-4-5`) reached the Pareto-optimal deal
that Run 9 α-squeezed (all-OpenAI) had missed. The breaking pattern was an
**R3→R4 defection**: a faction on `gpt-4.1-mini` textually commits at R3 to the
position the other two are converging on, then proposes a personally-preferred
alternative at R4, killing consensus. Observed **two-of-two times on
`gpt-4.1-mini`**, different factions (Run 9 α-squeezed beta; Run 10 C' gamma).
Anthropic `claude-haiku-4-5` honored beta's R3 contingent verbatim at R4 (Run 10 B').

### Thesis

BATNA pressure and provider consistency reached the *same* Pareto deal via
different mechanisms: BATNA pressure *forced* the OpenAI agent to stay consistent
(defecting back to BATNA was too costly), while Anthropic was consistent by
default. So **BATNA pressure is a *substitute* for native cross-round consistency
on consistency-flaky models, and a *no-op* on consistency-reliable ones.**

**Tuning implication:** consistency-critical seats (bottleneck-holders whose R3
contingent everyone else is converging toward) should default to a
consistency-reliable provider for multi-round games.

### Open scope question (deferred under D-56)

Is the `gpt-4.1-mini` R3→R4 defection **Water-Rights-specific or general**? Two
cheap cross-scenario checks would generalize it (re-run Three-Party Coalition and
Trade Summit on all-`gpt-4.1-mini`, watch R3→R4 transitions). Plus an
all-Anthropic baseline across the three BATNA variants (symmetric / α / β) to
confirm Anthropic reaches Pareto across the spectrum. All deferred — see the
NEXT_STEPS "Deferred (icebox)" list.

Run 18 (2026-06-22) added a strong-tier data point on the same provider axis:
`gpt-5.5` (OpenAI) closes WR-β bare 3/3 where `claude-sonnet-4-6` (Anthropic)
floors 0/3 — i.e. the WR-β strong-tier failure was sonnet-specific, not a
strong-tier property (see Note 1 amendment bullet 5).
