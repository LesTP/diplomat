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

---

<!-- Append new notes below this line. Use ## Note N — Title format. -->
