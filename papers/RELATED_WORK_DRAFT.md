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

## 2. LLM negotiation benchmarks — the incumbent and its critique

A dedicated cluster builds LLM negotiation benchmarks. *Deal or No Deal* [Lewis
et al., 2017] is the foundational pre-LLM two-party item-division task;
*NegotiationArena* [Bianchi et al., 2024 — ⚠] catalogues LLM bargaining
behaviors. The **direct incumbent is Abdelnabi et al.** [*Cooperation,
Competition, and Maliciousness: LLM-Stakeholders Interactive Negotiation*;
Abdelnabi, Gomaa, Sivaprasad, Schönherr & Fritz; arXiv 2309.17234, 2023, rev.
2024] — scorable, multi-issue, multi-party negotiation as an LLM benchmark, with
evolving games, difficulty tuning, role-alignment metrics, and greedy/adversarial
variants, run at **larger scale than Diplomat (6 agents, 24 rounds)**. Diplomat
does **not** introduce this category and does not out-scale it.

What Diplomat contributes is **measurement rigor**, and an independent
reproducibility study makes the case for us: *[Re] Benchmarking LLM Capabilities
in Negotiation through Scoreable Games* [Carrasco Pollo, Kapetangeorgis,
Rosenthal & Yao — ⚠ venue/year] replicates Abdelnabi and finds **model
comparison ambiguous, with its objectivity in question**, flags an
**unreproducible ablation** and **information-leakage** issues, and has to
**add social-welfare metrics post-hoc** because the original lacks
efficiency/optimality grounding. Diplomat builds those fixes in: (a)
**game-theoretic optimality scoring** — Pareto frontier / Nash / surplus-share /
skill-premium, where the incumbent uses BATNA-threshold pass/fail; (b) a
**documented, deterministic, module-level scaffolding ablation** (vs the
incumbent's CoT-only, unreproducible one); (c) **automated, property-targeted,
verifiable** scenario generation (vs manual game adaptation); (d) **construct
validity** via correlation with external indices.

**Gap (restated):** the incumbent established the category but leaves model
comparison ambiguous, its ablation unreproducible, and efficiency/construct
validity unaddressed — exactly the measurement gaps Diplomat targets. Diplomat
does *not* claim novelty on scale, adversarial/deception variants, or the
evolving-games idea (all present in the incumbent).

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

**LLM-as-judge and interpretable evaluation.** Where Diplomat *does* need
subjective judgment — classifying *how* a negotiation failed (the
three-mechanism taxonomy) and the transcript-interpretive process signatures
(§3.4) — it draws on the LLM-as-judge line: *G-Eval* [Liu et al., 2023 — ⚠]
and *UniEval* [Zhong et al., 2022 — ⚠] (holistic / multi-dimensional LLM
judges), and especially *BINEVAL* [Cho, Chawla et al., 2026 — ⚠], which
decomposes a criterion into atomic binary questions for interpretable,
calibratable scores (adopted for our mechanism classifier). The contrast
sharpens Diplomat's positioning: **outcomes are graded by objective
game-theoretic ground truth (no judge); judge-based methods are confined to
the process/mechanism layer where no ground truth exists** — pre-empting the
"why not just LLM-judge everything?" objection.

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
| Abdelnabi et al. (verified) | ✔ | ✔ | ✔ | ✘ (BATNA pass/fail) | ~ (evolving, manual) | ✘ | ~ (CoT-only) |
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
- [x] Abdelnabi et al. — **VERIFIED** (arXiv 2309.17234, 2023; rev. 2024): scorable multi-issue multi-party; BATNA-threshold scoring (no Pareto/Nash); manual game adaptation; CoT-only ablation; 6 agents / 24 rounds; greedy/adversarial variants. Still to confirm: published venue for the 2024 revision.
- [ ] Carrasco Pollo, Kapetangeorgis, Rosenthal & Yao — *[Re] Benchmarking LLM Capabilities in Negotiation through Scoreable Games* (reproducibility study of Abdelnabi); confirm venue (MLRC / TMLR?) + year. The independent critique motivating Diplomat (ambiguous comparison, unreproducible ablation, post-hoc social-welfare metrics).
- [ ] Deal or No Deal — Lewis et al. 2017, EMNLP; confirm
- [ ] GTBench — Duan et al. 2024; confirm games covered + whether any are incomplete-information
- [ ] Akata et al. repeated games — confirm authors/year
- [ ] Social-deduction LLM papers (Werewolf/Avalon) — collect 1–2 representative cites
- [ ] ReAct (Yao et al. 2022), Reflexion (Shinn et al. 2023), Tree of Thoughts — confirm
- [ ] AgentBench (Liu et al. 2023) — confirm
- [ ] Dynabench (Kiela et al. 2021) — confirm
- [ ] BINEVAL (Cho, Chawla et al. 2026, arXiv 2606.27226) — confirm; adopted for the mechanism classifier (binary-question decomposition)
- [ ] G-Eval (Liu et al. 2023) — confirm; LLM-as-judge baseline
- [ ] UniEval (Zhong et al. 2022) — confirm; multi-dimensional LLM-judge baseline
- [ ] Chatbot Arena / LMArena (Zheng et al. 2023) — confirm; this is the external-Elo source for §5.7 correlation
- [ ] Benchmark-validity critique (Raji et al. 2021 "Everything in the Whole Wide World") — confirm
- [ ] Contamination literature — pick 1–2 canonical cites
- [ ] Nash 1950; Fisher & Ury; Raiffa; Susskind — foundations, confirm editions
- [ ] **Search for newer (2024–2026) LLM-negotiation benchmarks** — the field moves fast; do a fresh literature sweep so nothing newer pre-empts the contribution

---

## 9. Risks / open issues for this section

- **Abdelnabi et al. — RESOLVED (read in full).** The overlap is substantial:
  they own the category, at larger scale, with evolving games + adversarial
  variants. Diplomat's claim is narrowed accordingly to **measurement rigor**:
  game-theoretic optimality scoring, module-level (not CoT-only) scaffolding
  ablation + mechanism taxonomy, automated property-targeted/verifiable
  generation, and construct validity. The independent reproducibility study
  (Carrasco Pollo et al.) is third-party evidence that these gaps are real.
  Do **not** claim novelty on category, scale, or adversarial/deception.
- **"Correlated with other benchmarks" cuts both ways.** Too-high correlation
  invites "why not just use MMLU/Elo?"; the rebuttal must lean on the
  discriminant residual + the multi-dimensional profile (negotiation-specific
  variance). Make sure §5.7 actually produces that residual before leaning on
  it here.
- **Field velocity.** A 2025–2026 negotiation benchmark could already occupy
  part of this niche. Fresh sweep is mandatory (checklist item above).
- **Scope of the scaffolding cluster.** Keep §4 short in the paper — the
  scaffolding ablation is a co-primary *contribution* but only one section.
  Over-citing the agent-framework literature risks re-centering the paper on
  scaffolding at the expense of the scoring-validity narrative that leads.
