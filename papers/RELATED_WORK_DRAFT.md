# Related Work — landscape draft (Paper 1)

> Draft of the Related Work section for the Diplomat benchmark paper. Framing is
> **benchmark-primary** (per `PAPER_PLAN.md` §0): position against the
> *benchmark / evaluation* literature first, the *negotiation-game* literature
> second, and the *scaffolding* literature only for the secondary harness-lift
> contribution.
>
> ⚠️ **CITATIONS ARE BEST-EFFORT FROM MEMORY AND MUST BE VERIFIED.** Titles,
> authors, years, and venues are placeholders for the author to confirm before
> submission. Do not submit any citation from this draft unchecked. See the
> verification checklist at the end. Where I am unsure a work exists as
> described, it is marked `⚠`.

---

## How to position (the one-paragraph strategy)

Diplomat sits at the intersection of three literatures, and its contribution is
the *combination* no single prior line achieves: a negotiation evaluation that
is (1) **contamination-resistant** because scenarios are synthetically
generated, (2) graded against **objective game-theoretic ground truth** rather
than human or LLM judges, (3) **construct-validated** by correlation against
established capability indices while retaining negotiation-specific variance,
and (4) instrumented for **scaffolding-aware measurement**. The Related Work
should make each prior cluster's *missing* property explicit and converge on
the feature matrix (§7 below).

---

## 1. LLMs in strategic / negotiation games

The most visible line couples LLMs to the board game **Diplomacy**. *Cicero*
[Meta FAIR, Science 2022 — ⚠ verify exact cite] reached human-level Diplomacy
play by combining a language model with a strategic planning engine; *Welfare
Diplomacy* [Mukobi et al., 2023 — ⚠] reformulates the reward to study
cooperative tendencies. These are landmark demonstrations, but negotiation in
them is **inseparable from board-game tactics**: dialogue is scored only
through its effect on territorial outcomes, and a dedicated planner does much of
the strategic work. Diplomat instead isolates negotiation as the *entire* game —
no board, no planner — so the measured signal is communication-and-bargaining
skill rather than tactical search.

**Gap:** negotiation not isolated from tactical play; outcomes not scored
against a negotiation-specific game-theoretic optimum.

## 2. LLM negotiation environments and arenas

A closer cluster builds dedicated LLM negotiation settings. *NegotiationArena*
[Bianchi et al., 2024 — ⚠] provides an environment for LLM-vs-LLM bargaining and
catalogues emergent strategies. *Deal or No Deal* [Lewis et al., 2017] is the
foundational pre-LLM end-to-end negotiation-dialogue task (two-party item
division). Most relevant, **Abdelnabi et al.** [“Cooperation, Competition, and
Maliciousness: LLM-Stakeholders Interactive Negotiation,” 2023/24 — ⚠] introduce
a *scored, multi-issue, multi-party* negotiation game with hidden per-party
incentives — structurally the nearest prior art to Diplomat.

These establish that LLMs *can* negotiate and that the setting yields rich
behavior. Diplomat differs on the axes that make it a *benchmark* rather than a
demonstration: (a) its scenarios are **synthetically generated** by a
constraint-driven builder, so the test set is not a fixed, eventually-memorized
corpus; (b) every outcome is scored against the **full computed Pareto frontier
/ Nash / BATNA structure**, enabling efficiency and surplus-share lenses, not
just win/lose; (c) it reports **construct validity** (correlation with external
capability) and **difficulty calibration**, which a behavior study does not
require.

**Gap:** fixed hand-authored scenarios (contamination over time); outcome
scoring typically win/lose or single-metric; no construct-validity / calibration
reporting.

## 3. Game-theoretic and multi-agent LLM evaluation

A broader evaluation line probes strategic reasoning. *GTBench* [Duan et al.,
2024 — ⚠] scores LLMs across a suite of game-theoretic games; *Playing repeated
games with LLMs* [Akata et al., 2023 — ⚠] studies 2×2 matrix games (prisoner's
dilemma and kin); social-deduction settings (Werewolf / Avalon [⚠ collect
cites]) test deception and theory-of-mind. These largely use **complete- or
known-payoff abstractions** or small canonical games. Diplomat's defining
feature — the **calculation-vs-negotiation gap** under *asymmetric private
utilities* (ASSESSMENT §1) — is precisely what these abstract away: with known
payoffs the equilibrium is computable and the *communication* skill that
Diplomat measures collapses.

**Gap:** complete-information or toy-game abstractions; the
asymmetric-information bargaining skill is not the target.

## 4. Agent scaffolding and frameworks (for the secondary harness-lift result)

The harness-lift contribution engages the agent-scaffolding literature —
*ReAct* [Yao et al., 2022 — ⚠], *Reflexion* [Shinn et al., 2023 — ⚠], *Tree of
Thoughts* [⚠], and agent-evaluation suites such as *AgentBench* [Liu et al.,
2023 — ⚠]. A recurring narrative there is that scaffold benefit **diminishes as
base models improve**. Our contribution sharpens this: in negotiation,
scaffolding lift is **non-monotonic and a function of (scenario shape × the
model's unaided capability)**, and apparent "zero lift" decomposes into three
distinct mechanisms (ceiling / redirect-failure / mismatch) that aggregate
metrics conflate. This is a finding *about how to measure*, not only *about
scaffolds*: it implies a negotiation leaderboard that does not fix the harness
is partly measuring the harness.

**Gap:** scaffold benefit reported as a single trend vs. model scale, on
task-completion metrics; the scenario×capability interaction and the
mechanism-decomposition are unaddressed.

## 5. Benchmark methodology: contamination, dynamic eval, construct validity

Diplomat's primary claims are methodological, so it should be situated in the
benchmark-design literature. Data-contamination concerns motivate **dynamic /
generated** benchmarks — *Dynabench* [Kiela et al., 2021 — ⚠] and the broader
contamination literature [⚠ collect]. *Chatbot Arena / LMArena* [Zheng et al.,
2023 — ⚠] supplies the external Elo we correlate against for construct validity.
Critiques of benchmark validity (e.g., *AI and the Everything in the Whole Wide
World Benchmark* [Raji et al., 2021 — ⚠]) frame the "does this benchmark measure
what it claims?" question we answer with the validity triad. Diplomat
contributes a benchmark that is **contamination-resistant by construction**
(deterministic synthetic generation), **objectively graded** (no judge for
outcomes), and **explicitly construct-validated** — a combination rarely
reported together for a *generative, multi-agent* task.

**Gap:** few generative multi-agent benchmarks report contamination-resistance
+ objective grading + construct validity together.

## 6. Negotiation and bargaining theory (foundations)

The scoring lenses and scenario provenance draw on negotiation/bargaining
theory: Nash bargaining [Nash, 1950], integrative-bargaining and BATNA [Fisher &
Ury, *Getting to Yes*], multi-party consensus and coalition design [Susskind;
Raiffa — ⚠], and the Harvard PON exercise catalogue (provenance for several
seed scenarios; see `Multi-Party Negotiation Scenarios.md`). These are cited as
the grounding for *what counts as a good outcome* (Pareto frontier, Nash
product, surplus share), not as comparison systems.

---

## 7. Feature matrix (the differentiation device)

Draft comparison; ✔ = property present, ✘ = absent, ~ = partial. **Verify each
row against the actual paper before relying on it.**

| Work | Negotiation isolated | Multi-party | Asymmetric private info | Game-theoretic ground truth | Synthetic / contamination-resistant | Construct validity reported | Scaffolding-aware |
|---|---|---|---|---|---|---|---|
| Cicero ⚠ | ✘ (board-coupled) | ✔ | ✔ | ~ (board outcome) | ✘ | ✘ | ✘ |
| Welfare Diplomacy ⚠ | ✘ | ✔ | ✔ | ~ | ✘ | ✘ | ✘ |
| Deal or No Deal | ✔ | ✘ (2-party) | ✔ | ~ (item values) | ✘ (fixed) | ✘ | ✘ |
| NegotiationArena ⚠ | ✔ | ~ | ✔ | ~ | ✘ | ✘ | ✘ |
| Abdelnabi et al. ⚠ | ✔ | ✔ | ✔ | ~ (per-party score) | ✘ (hand-authored) | ✘ | ✘ |
| GTBench ⚠ | ~ | ✔ | ✘ (known payoff) | ✔ | ~ | ~ | ✘ |
| Akata et al. (repeated games) ⚠ | ~ | ✘ | ✘ | ✔ | ✘ | ✘ | ✘ |
| **Diplomat (ours)** | ✔ | ✔ | ✔ | ✔ (Pareto/Nash/BATNA) | ✔ (builder) | ✔ (correlation + calibration) | ✔ (bare/full ablation) |

The right-most three columns are where Diplomat is differentiated; the matrix
should make the empty bottom-right quadrant of prior work visually obvious.

---

## 8. Citations to verify / collect (do before drafting prose into the paper)

- [ ] Cicero — exact title, authors, *Science* 2022 cite + DOI
- [ ] Welfare Diplomacy — authors, venue, year; confirm it's LLM-based
- [ ] NegotiationArena — authors (Bianchi et al.?), venue, year; confirm scope (bilateral vs multi-party)
- [ ] Abdelnabi et al. — **most important**; confirm exact title/venue, whether scenarios are fixed/hand-authored, scoring scheme, single vs multi-issue, contamination discussion. This is the nearest competitor; the differentiation must be precise and fair.
- [ ] Deal or No Deal — Lewis et al. 2017, EMNLP; confirm
- [ ] GTBench — Duan et al. 2024; confirm games covered + whether any are incomplete-information
- [ ] Akata et al. repeated games — confirm authors/year
- [ ] Social-deduction LLM papers (Werewolf/Avalon) — collect 1–2 representative cites
- [ ] ReAct (Yao et al. 2022), Reflexion (Shinn et al. 2023), Tree of Thoughts — confirm
- [ ] AgentBench (Liu et al. 2023) — confirm
- [ ] Dynabench (Kiela et al. 2021) — confirm
- [ ] Chatbot Arena / LMArena (Zheng et al. 2023) — confirm; this is the external-Elo source for §5.7 correlation
- [ ] Benchmark-validity critique (Raji et al. 2021 "Everything in the Whole Wide World") — confirm
- [ ] Contamination literature — pick 1–2 canonical cites
- [ ] Nash 1950; Fisher & Ury; Raiffa; Susskind — foundations, confirm editions
- [ ] **Search for newer (2024–2026) LLM-negotiation benchmarks** — the field moves fast; do a fresh literature sweep so nothing newer pre-empts the contribution

---

## 9. Risks / open issues for this section

- **Abdelnabi et al. is the load-bearing differentiation.** If their setup is
  closer to Diplomat than assumed (e.g., if they also generate scenarios or
  report ground-truth efficiency), the novelty narrows. Read it carefully and,
  if needed, narrow Diplomat's claimed contribution to the parts that remain
  clearly distinct (synthetic generation + construct validity + scaffolding
  ablation, even if the game structure overlaps).
- **"Correlated with other benchmarks" cuts both ways.** Too-high correlation
  invites "why not just use MMLU/Elo?"; the rebuttal must lean on the
  discriminant residual + the multi-dimensional profile (negotiation-specific
  variance). Make sure §5.7 actually produces that residual before leaning on
  it here.
- **Field velocity.** A 2025–2026 negotiation benchmark could already occupy
  part of this niche. Fresh sweep is mandatory (checklist item above).
- **Scope of the scaffolding cluster.** Keep §4 short in the paper — it's the
  secondary contribution. Over-citing the agent-framework literature risks
  re-centering the paper on scaffolding, which the benchmark-primary framing
  explicitly avoids.
