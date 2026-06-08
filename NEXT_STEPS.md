# Diplomat — Next Steps

> Working document. Updated 2026-06-07.
>
> Related: `DEVPLAN.md` (canonical phase plan), `TUNING_LOG.md` (run-by-run record),
> `ARCH_conversation_model.md` (Stage 1/2/3 migration), `RUN_PROTOCOL.md` (pre-flight),
> `ASSESSMENT.md` (scoring framework + workstream blocks).

> **Workstream block tags.** Every section heading and item carries one
> of `[A]`, `[B]`, `[C]`, or `[X]` per `ASSESSMENT.md` §5:
> - `[A]` agent architecture & memory (pipeline modules, state, conversation model)
> - `[B]` prompt tuning (personas, module prompts, strategy library, voice)
> - `[C]` game creation & scoring (compiler, BATNA, pressure, verification, scoring lenses)
> - `[X]` cross-cutting (toolkit infra, deployment, integration tests, meta-tests)
>
> Multiple tags = item touches multiple blocks; primary block listed first.

> **Loop-readiness classification.** Items are also classified for autonomous-loop suitability:
> - 🔨 **PURE BUILD** — code/refactor only, deterministic, no operator judgment mid-loop. Suitable for autonomous build phases.
> - 🔀 **MIX** — has a build component but needs operator decisions at boundaries.
> - 👁 **SUPERVISED** — experiments, prompt tuning, design judgment, or interactive work. Operator-driven only.

> **Tier-priority rationale (operator, 2026-06-02).** `[A]` agent architecture
> and `[X]` cross-cutting infra are foundational — they enable `[C]` (game design)
> and `[B]` (prompt tuning) to land cleanly. Work down the tiers gradually
> rather than chasing the highest-interest item across all tiers in parallel.
> The "Open items by workstream tier" section below groups everything in that
> order; the per-section detail (§1.6 through §9) keeps the historical
> numbering for stable cross-references.

> **State as of 2026-06-07:** Phases 20–33 closed. Runs 9 + 10 + 13 closed.
> **Phase 34 queued (Bare-prompt mode for ablation experiments)** — the
> build prerequisite for the foundational design-bet question: does
> Diplomat's harness actually contribute to negotiation outcomes, or could
> a bare-prompt agent (Persona + transcript + Generation only) perform
> comparably? Worker may begin execution; see `DEVPLAN.md`. Run 13b
> (coached re-test) + Run 14a-14f (ablation matrix) queued in §10 below
> for after phase close.

---

## Closed since 2026-05-30

Audit trail moved to **Appendix A** at the end of this document — 30+ closed
items across Phases 19-28 + Runs 9-10 + a handful of rescoped / rejected
items. Canonical detail lives in `DEVLOG.md` / `DEVLOG_archive.md` and
`TUNING_LOG.md` / `TUNING_LOG_archive.md`.

---

## Open items by workstream tier

Grouped by the operator's priority tiering A/X > C > B. Section detail
(§1.6 through §9) is below and keeps the historical numbering for stable
cross-references.

### Tier 1 — `[A]` agent architecture + `[X]` cross-cutting (foundational)

| Item | Tags | Loop | Where | Notes |
|---|---|---|---|---|
| **Bare-prompt ablation** (does the harness contribute?) | `[A][X]` | 👁 | §10 | Phase 34 closed 2026-06-08 (bare-mode plumbing shipped, ~$0.02/game vs ~$1 projected). Runs 14a-14f (3 models × 2 modes × 2 scenarios × 3 runs = 36 runs, ~$60-100) queued. Foundational design-bet test: harness load-bearing, theater, or scaffold? |
| **Coaching test loop on Pi** | `[X]` | 👁 | §4 | Run 13 (2026-06-04) validated new gate end-to-end but operator chose approve-only — edit path untested. Phase 33 shipped `/revise:` + auto-classifier (2026-06-07). Run 13b queued to exercise edit modes live. |
| **Game-platform exploration** (Clankmates / Discord / fallback) | `[X]` | 👁 | §5 | Gated on operator + partner platform decision. Discord considered alongside Clankmates. |
| **Pricing & accounting audit** | `[X][C]` | 👁 | §6 | Best done before Tier 3 §7 so per-role cost claims have a firm baseline. |
| **TelegramReviewGate as production default** | `[X]` | 👁 | (decision) | Whether to flip `pipeline.yaml` `review_gate` to `TelegramReviewGate` as the production default. Smoke runs on `pipeline_smoke.yaml` already use it. |
| **Provider-native structured output** (`response_format: json_schema`) | `[X]` | 🔀 | Carry-forward | Toolkit plumbing build; gives token-level schema compliance. Lower priority — current `structured_call` retry loop is working. |

### Tier 2 — `[C]` game creation & scoring

| Item | Tags | Loop | Where | Notes |
|---|---|---|---|---|
| **Game pressure beyond BATNA + divorce scenario** | `[C]` | 🔀 | §2 | Run 10 confirmed BATNA is refusal-strengthening; round-cost decay + exogenous events are the missing concession-eliciting mechanisms. Works with current Stage 1 round model (extra rounds, not multi-pass). |
| **Reverse scenario builder** | `[C]` | 🔀 | §8 | Outcome-shape → scenario. Best done after one divorce scenario surfaces the constraint vocabulary. |
| **Pareto-frontier annotation in analyst output** | `[C][B]` | 🔀 | §2 TODOs | Analyst surfaces threats/leverage; add Pareto-compromise opportunities. Schema + prompt change. |
| **Surplus-distribution diagnosis** | `[C]` | 👁 | Backlog | Cross-scenario investigation of "why does gamma extract 52-55% of surplus?" Likely game-theoretic; if confirmed, a scenario-design lever. |
| **Identify-the-blocker tool** | `[C][X]` | 🔀 | (loop-readiness) | Pre-game LLM analyst pass over scoring tables to predict squeeze target. Lower priority post-Run 10 but still a useful scenario-design aid. |
| **ASSESSMENT §3.4 persuasion-shifts / concession-curve signatures** | `[C]` | 👁 | (loop-readiness) | Needs LLM-judge over transcripts. Higher cost; defer until other Tier 2 items land. |
| **Reconciliation live validation** | `[C]` | 👁 | Backlog | Status transitions + inconsistency flagging untested in live runs. Run 10 B' and α-squeezed defection are natural inspection targets. |

### Tier 3 — `[B]` prompt tuning & strategy

| Item | Tags | Loop | Where | Notes |
|---|---|---|---|---|
| **Per-role model strategy** (consistency + cost + quality axes) | `[B]` | 👁 | §7 | Materially informed by Run 10. Wants Tier 1 §6 (pricing audit) for cost baseline + Tier 3 §1.7/§1.8 results. |
| **Provider consistency tests** (all-Anthropic baseline + cross-scenario) | `[B][X]` | 👁 | §1.7 / §1.8 | Run 11 candidates. Generalize Run 10 finding. ~$3-4 + ~$0.30. Cheap and operator-driven, can run independently of other tiers. |
| **Strategy routing** (hardball / integrative / tit-for-tat / etc.) | `[B]` | 👁 | §2.5 | Prompt library + operator-pickable strategy. Real-game value: pick a strategy mid-game and the prompt machinery executes it. |
| **Persona payment rigidity / drift / endgame over-anchoring** | `[B]` | 👁 | Carry-forward | Recurring across Runs 7-10. Run 10 showed provider consistency matters more than persona rule. A/B in a future run. |

### Deferred — `[A]` conversation model evolution

| Item | Tags | Loop | Where | Notes |
|---|---|---|---|---|
| **Conversation model evolution** (multi-pass / async) | `[A]` | 👁 | §3 | Stage 2a (K-pass rounds), 2b (convergence detection), 3 (true async). Demoted 2026-06-02: current Stage 1 sealed-bid model produces real negotiation dynamics; pressure mechanisms (§2) work with extra rounds. Pursue when a use case demands within-round reactivity or timing-as-strategy. |

### Sequencing within Tier 1 (most actionable now)

If working down the tiers, the immediate decision is which Tier 1 item to do first. Recommended order:

1. **Run 14a-14f bare-prompt ablation (§10)** — Phase 34 built the plumbing; the experimental runs answer the foundational design-bet question. Cheap (~$60-100 across 36 runs) and the result drives everything else.
2. **Pricing audit (§6)** — best done before Tier 3 §7 so per-role decisions have a firm cost baseline.
3. **Game-platform exploration (§5)** — gated on operator + partner alignment; explore Discord alongside Clankmates while the partner decision is pending.

### Cross-tier dependencies worth knowing

- **Tier 3 §7** (per-role models) wants **Tier 1 §6** (pricing audit) — cost-quality tradeoffs need accurate cost numbers.
- **Tier 3 §1.7 + §1.8** (provider consistency tests) are *experimental data feeding into Tier 3 §7* — listed in Tier 3 because the deliverable is a tuning rule, but cheap + operator-driven so they can run independently of other tiers.

### Pure-build extensions (if extending the autonomous queue)

Items with a clean "build half" suitable for a future Phase 30+:

| Candidate | Build slice | What stays supervised |
|---|---|---|
| **`tools/identify_blocker.py`** | Read `scenario_analysis.json`; one `structured_call` to an analyst LLM asking "for the Pareto-optimal deal, which faction has to concede most on their priority issue?" Output ranked list of squeeze candidates. | Scenario-design judgment about whether to act on the recommendation. |

---

## 1.7. `[B][C]` Provider consistency as a deal-making variable (Run 10 finding)

**Headline.** Run 10 B' (alpha-squeezed BATNAs unchanged, beta's Generator
re-routed from OpenAI gpt-4.1-mini to Anthropic claude-haiku-4-5) reached the
Pareto-optimal deal that Run 9 alpha-squeezed had missed. The R3→R4 defection
pattern that broke Run 9 (beta-on-OpenAI proposed `Medium + Heavy-Downstream +
JFD` in R3 then pivoted to `High + Shared + JFD` in R4, killing the alpha+gamma
convergence) was reproduced in Run 10 C' — this time with *gamma* defecting on
the same OpenAI gpt-4.1-mini model. **Two-of-two instances of the same failure
mode on the same model, different factions.**

The cleanest reading: for OpenAI gpt-4.1-mini on Water-Rights-style scenarios,
R3 contingent commitments are unreliable — the model will textually commit then
propose something different at R4. Anthropic claude-haiku-4-5 honored beta's R3
contingent verbatim at R4 (Run 10 B').

**Why this matters.** BATNA pressure (Run 9 β-squeezed) and provider consistency
(Run 10 B') reached the *same* Pareto deal via different mechanisms. BATNA pressure
*forced* the OpenAI agent to be consistent (defecting back to BATNA was costly enough
to bind); Anthropic was consistent by default. Once you account for the provider
effect, the BATNA-pressure thesis simplifies: BATNA is a *substitute* for native
consistency on consistency-flaky models, and a *no-op* on consistency-reliable ones.

### TODOs

- [ ] **§1.7.a All-Anthropic baseline (Run 11 candidate).** Run all three Run 9
      BATNA variants (symmetric / α-squeezed / β-squeezed) with single-provider
      Anthropic claude-haiku-4-5. Tells us whether Anthropic reaches Pareto across
      the BATNA spectrum (confirming the provider-default consistency thesis) or
      only when structure favors it. ~$3-4 spend.
- [ ] **§1.7.b OpenAI defection on Three-Party Coalition / Trade Summit (§1.8).**
      Cheap (~$0.30) cross-scenario check. If the R3→R4 defection reproduces, it's
      a general OpenAI gpt-4.1-mini tuning rule (consistency-critical seats need
      Anthropic). If it doesn't, it's a Water-Rights-specific quirk likely tied to
      how the Payment issue is framed.
- [ ] **§1.7.c Update TUNING.md provider-assignment table.** Once §1.7.a + §1.7.b
      land, add a "Consistency-critical seats" row noting that beta-style
      bottleneck-holder roles should default to Anthropic for multi-round
      negotiations.
- [ ] **§1.7.d Promote provider consistency to ASSESSMENT.md §3.4.** Process
      signature "across-round commitment-following rate" is a meaningful skill
      dimension that wasn't on the original list. Worth adding once we have
      cross-scenario data.

---

## 1.8. `[B]` OpenAI gpt-4.1-mini R3→R4 defection — cross-scenario scope test

**Status.** Two instances on Water Rights so far (Run 9 α-squeezed beta, Run 10 C'
gamma). Both: faction commits at R3 to a position the other two are converging
toward, then proposes a personally-preferred alternative at R4 breaking consensus.

**Question.** Water-Rights-specific or general? If general, OpenAI gpt-4.1-mini
should not occupy any consistency-critical seat in multi-round negotiations.

### TODOs

- [ ] Re-run **Three-Party Coalition** (Run 6/7 scenario) with all OpenAI
      gpt-4.1-mini Generators, observe R3→R4 transitions for any faction.
      Use a scenario where coalition formation requires a faction to commit
      to A+B in R3 — the natural shape for the defection pattern. ~$0.30.
- [ ] Re-run **Trade Summit** (Run 5 scenario, dirty bargaining with deception
      tactics) on all OpenAI gpt-4.1-mini, observe whether the deception-then-reveal
      arc that worked in Run 5 still holds. Different question (tactical
      commitment vs cross-round commitment) but related. ~$0.30.

---

## 2. `[C]` Game pressure beyond BATNA

**Run 8 observation:** Agents sat at BATNA because BATNA was *survivable*. Alpha
won the tiebreak with score 11 = BATNA 11; nobody had structural urgency to
compromise. The Pareto-optimal Shared deal (alpha=14, beta=20, gamma=22) sat
on the table untouched.

The fix is structural, not prompt-tuning. Need mechanisms that create real
incentive to negotiate.

### Pressure mechanisms to add

1. **Round-cost decay** — every round without a deal subtracts points from
   everyone. Models lawyer fees in divorce, status quo costs in trade disputes.
   Builds urgency without explicit endgame talk.
2. **Exogenous events per round** — e.g. "Round 3: drought reduces water
   supply 30%" — recomputes BATNAs mid-game and forces position revision.
   Inject as moderator round-update messages between rounds (existing
   `round_updates` mechanism in `RoundSteppedFlow`).
3. **Asymmetric clocks** — one faction has a hard deadline (election, market
   close, covenant expiring); others can wait. Creates structural urgency for
   one player only.
4. **Penalty floor below BATNA** — "no deal" doesn't equal BATNA; it equals
   BATNA *minus* a regret cost (reputation, sunk fees).
5. **Cascade scoring** — points awarded not on the deal itself but on what
   the deal *enables* in a later phase.

### Endgame clarity

Run 7 confirmed FINAL ROUND markers work. To strengthen: have the marker
show *current vs threatened* score concretely.

Example: `Round 4: no deal = 11 points (your BATNA). Current best offer
on table = 14 points. Walking away costs you 3 points.`

That's loss aversion made explicit.

### TODOs

- [ ] Extend scenario compiler to extract: round-events table, decay rates,
      asymmetric deadlines, penalty floors. Add to `PERSONA_TEMPLATE` and
      `build_round_context`.
- [ ] Build `verify_scenario_pressure.py` alongside `verify_scenario_optimum.py`
      that confirms BATNAs are under pressure — e.g. "by round 3, expected
      scores at BATNA fall by ≥X%."
- [ ] Add "pressure profile" metadata to each scenario: low/med/high time
      pressure, low/med/high external shock, etc.
- [ ] Strengthen FINAL ROUND marker: include current best on-table score and
      delta vs BATNA.
- [ ] **Design and run a divorce scenario.** Natural showcase for all five
      pressure mechanisms:
  - Shared assets (house, savings, business) — divisible
  - Indivisible goods (kids — joint custody is real Pareto territory)
  - Ongoing relationship — cost of acrimony is real
  - Lawyer fees scale linearly with time → built-in round decay
  - External pressure (kids' school year, mortgage due)
  - Multiple game modes embedded: zero-sum on money, integrative on
    parenting, mixed on the house
  - Asymmetric BATNAs (one party may have an exit option — new job, family
    support)
- [ ] **Pareto-frontier annotation in analyst output.** Schema change build;
      prompt change needs Layer 2 supervised validation. Add a "compromise
      opportunities" field that enumerates deals beating all known BATNAs.
      Currently the analyst identifies leverage and threats; this would surface
      the Pareto-optimal deals explicitly.

---

## 2.5. `[B]` Strategy routing

Treat as a separate experimental axis from scenario design. Build a small
strategy library, A/B test per-faction.

### Candidate strategies

| Strategy | Persona instruction sketch |
|---|---|
| **Hardball anchor** | Open extreme, concede in tiny increments, walk-away threat at round 3 |
| **Integrative seeker** | Open with information exchange, propose multi-issue trades, focus on Pareto frontier |
| **Sequential concession** | Match every opponent concession 1:1; if they don't concede, hold |
| **Tit-for-tat** | Mirror previous round's opponent behavior on cooperation/defection |
| **Reputation builder** | Make small early commitments, keep them visibly, leverage trust late |
| **Coalition pivoter** | Propose A+B early, switch to A+C if B holds out, then ABC at endgame |
| **Information broker** | Stay neutral on positions; trade intel for concessions |

### TODOs

- [ ] Create `config/personas/strategies/` directory with one template per
      strategy above.
- [ ] Extend scenario compiler to allow strategy selection per faction
      (orthogonal to scoring/BATNA, which stays scenario-driven).
- [ ] Run scenarios × strategies × providers matrix. Cells: 4 scenarios × 7
      strategies × 3 providers = lots; pick targeted cells per run.
- [ ] **Real-game value:** the operator should be able to pick a strategy
      mid-game (`WATCH: Beta playing tit-for-tat. Recommend integrative-seeker
      for us.`) and have the prompt machinery execute it immediately.

---

## 3. `[A]` Conversation model evolution (multi-pass / async)

> **Deprioritized 2026-06-02.** Stage 2a (K=2 open+react) was originally
> Tier 1 as a prerequisite for §2 pressure mechanisms. On review, pressure
> mechanisms work fine with extra rounds on the current Stage 1 sealed-bid
> model — the "pass" vs "round" distinction doesn't produce meaningfully
> different agent behavior. The full conversation model migration is
> interesting but not blocking anything. Pursue when a use case demands
> within-round reactivity or timing-as-strategy.

`ARCH_conversation_model.md` maps the staged migration:

1. **Stage 1 (current)** — each faction generates once per round, sealed-bid
   style. No within-round reactivity. All Runs 1–10 used this model.
2. **Stage 2a (K-pass rounds)** — every agent generates K times per round
   with intermediate broadcasts. K=2 = open+react. Doubles cost per round.
   Functionally similar to running 2× rounds with adjusted endgame markers.
3. **Stage 2b (K=N until convergence)** — agents keep responding until no
   new commitments are made or N caps it. First stage with genuinely new
   behavior — agents stop talking when they have nothing to add.
4. **Stage 3 (true async)** — agents decide *when* to speak. Silence
   becomes a strategic signal. Timing matters. Novel research territory.

### When to revisit

- If Stage 1 runs show agents talking past each other in ways that more
  rounds can't fix (not seen in Runs 1–10).
- If a real-game moderator wants within-round reaction dynamics.
- If async timing-as-strategy becomes a research goal.

### TODOs (deferred)

- [ ] Stage 2a: add `MultiPassMode` to `RoundSteppedFlow`; K configurable.
- [ ] Stage 2b: convergence detection (no new commitments for N passes, or LLM-judged).
- [ ] Stage 3: generation schema emits `next_response_delay`; timing as strategy.
- [ ] Update scenario compiler to produce round-events tables if multi-pass is used.

---

## 4. `[X]` Coaching test loop on Pi

**Status 2026-06-07:** Three iterations done. First coached game (2026-06-03) surfaced 4 UX bugs (§4a-§4d), all closed via Phase 31 + Phase 32 + a prompt change. Run 13 (2026-06-04) validated the new gate end-to-end on all-Gemini-flash Water Rights symmetric — gate, transport, chunking, lazy-fetch, commands-during-review all worked. **But operator chose approve-only across all 4 rounds, so the edit path is still untested in a live run** and the feedback loop (classify edits → feed patterns into faction_prompt) has zero data. Phase 33 closed 2026-06-07 — ships `/revise: <directive>` LLM-rewrite edit mode + auto-classifier for the edit log. **Run 13b** (live re-run exercising the new edit modes; renamed from "Run 14" to free that number for the §10 ablation series) is the immediate post-phase test.

**What happened on the first coached game (2026-06-03, pre-Phase 31):** Operator coached beta faction via Telegram on Water Rights symmetric (all-Anthropic). Beta spoke in Round 1, then R2-R4 drafts hit Telegram's 4096-char message limit and failed silently. Beta was muted for 75% of the game. Alpha and Gamma negotiated around the silence and converged on a deal that happened to include beta. Operator rubber-stamped the R1 draft because they had no visibility into what other factions were saying.

### UX fixes needed (priority order, all 🔨 PURE BUILD)

- [x] **4a. TG 4096 char limit.** Closed Phase 31 (2026-06-04). `OperatorReviewGate` chunks messages at `max_message_chars=4000` via `chunk_text()` with `[continued ...]` markers. Note: command-response sends had the same bug class — fixed cleanly by Phase 32 (toolkit-level auto-chunking).
- [x] **4b. Transcript visibility / operator commands during review.** Closed Phase 31 (2026-06-04). `Pipeline.dispatch_operator()` routes commands through `review_gate.handle_command()` first; `/state`, `/status`, `/divergences`, `/ledger` work during pending review. `/reasoning` and `/adversarial` lazy-fetch deeper context on demand. `/intel` was silently dropped due to the chunking-bug-class (fixed by Phase 32.1–32.3), and Phase 32.5 now trims `/intel` to the latest round only.
- [x] **4c. Verbose generation responses.** Closed 2026-06-04 (prompt change). Conciseness instruction added to `config/prompts/generation.txt`.
- [x] **4d. Re-run coached game after UX fixes.** Satisfied by Run 13 (2026-06-04) — all-Gemini-flash Water Rights symmetric, β coached. Game completed 4 rounds; gate validated end-to-end (chunking surface present, lazy fetch works, commands-during-review works for everything except `/intel` which was the chunking-bug-class). The narrower follow-ups shipped in Phase 32: queue-drain on listener startup (R1 staleness, 32.4) and `/intel` trim to latest round only (32.5). Operator chose approve-only — edit-classification per `diplomat-testing-doc.md` §7.3 was therefore not exercised; revisit if a future coached run involves real edits.
- [x] **4e. `/revise: <directive>` LLM-rewrite edit mode + auto-classifier for the edit log.** **Closed Phase 33 (2026-06-07).** (a) `/revise: <directive>` added to `OperatorReviewGate` — operator gives intent, model regenerates draft in-place using full `DecisionContext`, capped at 3 iterations per pending review, directive chain stored as JSON array in `review_gate_edits.revise_directives`. (b) `LLMEditClassifier` + `edit_classifications` table + `tools/classify_edit_log.py` CLI + `/edits-summary` operator command auto-categorize every `action='edited'` row into the six §7.3 categories. See `DEVPLAN.md` Phase 33 plan (collapsed at close) for full design decisions.
- [ ] **4f. Operator command response UX (`/ledger` info-density, `/intel-history` for full history).** Operator notes 2026-06-04 (Run 13): `/ledger` "works but it's not very informative" — currently returns only `{per_round_budget, session_budget, available_budget, current_round}`. Improvement ideas: add per-call counts since last query, current-round spend, top 3 most expensive calls, cost-per-faction breakdown. Related: after Phase 32 trims `/intel` to latest round only, may want an `/intel-history` companion command for the full archive (defer until operator asks for it — most-recent-only is the more useful default). Both are pure-UX polish; no urgency. Out of scope for Phase 33.

### What the first session confirmed

- Review gate wiring works end-to-end (bot DMs draft, operator approves, bot posts to group)
- Coaching tags and `/approve`/`/edit`/`/block` commands are functional
- The harness survives a muted faction gracefully (no crashes, deal still reached)
- `coached_game.py` dry-run + live both work (after `sys.path` fix for `src/`)

### Original TODOs (updated)

- [x] Build `coached_game.py` (Phase 28)
- [x] Test scenario: Water Rights symmetric, all-Anthropic (2026-06-03)
- [x] Run on Pi (incus container, `.venv/bin/python3`)
- [ ] **After Phase 33 ships: Run 13b — coached game exercising `/revise:` and `/edits-summary`.** (Queued — Phase 33 closed. Renumbered from "Run 14" 2026-06-07 to avoid collision with the Run 14a-14f ablation series in §10.) Goal is to validate the new edit modes end-to-end in a live game and produce the first non-trivial `review_gate_edits` log with `revise_directives` populated and `edit_classifications` populated. Suggested config: Water Rights symmetric (matches Run 13 baseline so edit signal isn't confounded by other variables), all-Gemini-flash or mixed providers per latest tuning. Cost: ~$0.50-1.00 for the game + ~$0.05 for classification. Per `RUN_PROTOCOL.md`.
- [ ] **After Run 13b: inspect edit log, classify edits, feed patterns back into `config/faction_prompt.txt`.** This is the actual feedback loop closing — recurring `constraint_enforcement` or `persona_correction` patterns become prompt edits per `ARCH_coaching.md` §"Review Gate Edit Log → Prompt Refinement". Phase 33 surfaces the patterns; this step does the prompt work.

---

## 5. `[X]` Game-platform exploration (Clankmates / Discord / fallback)

**Status 2026-06-02.** Both candidate platforms are theoretical right now.
Clankmates is blocked on the operator's partners committing to it.
Discord is a hedge that should be researched in parallel — it has documented
APIs, a large bot ecosystem, and no partner dependency. Until one of these
becomes concrete, this section stays exploratory: don't build a
`ClankmatesTransport` or `DiscordTransport` until there's a real game to ship.

### Why this is on the backlog rather than queued

The game-traffic surface (where factions post to each other) needs to be
*something*. Telegram has been ruled out for game traffic because it doesn't
deliver bot-to-bot messages in groups regardless of privacy mode (see
"Telegram-platform finding" in Backlog). Telegram stays as the operator
coaching + review-gate surface.

### Clankmates — primary candidate (blocked on third party)

Three angles to weigh:

1. **Forcing function** — building `ClankmatesTransport` before the platform
   ships is a credible signal to that team.
2. **Risk** — polling-based with unknown API stability; could be wasted
   effort if the interface changes pre-launch.
3. **Hedge** — build a thin Transport interface adapter, mock against
   *expected* API shape, verify against real API when available.

Reference: `for-clankers.md` documents the expected interface (browser for
human, CLI/API for the agent, inbox screening pattern).

### Discord — parallel hedge candidate (no partner dependency)

**Why consider Discord:**

- Public, stable Bot API (REST + WebSocket Gateway, versioned and well-documented).
- Standard webhook + slash-command patterns.
- Channels + threads map cleanly to public game channel + faction-pair DMs / private threads.
- Large bot ecosystem; mature Python libraries (`discord.py`, `hikari`).
- No partner dependency — we can prototype and test entirely on a private server.
- Bots can DM each other (unlike Telegram), so faction-to-faction private
  channels work natively.

**Pre-conditions before building:**

- Operator commits to Discord as either primary or hedge target.
- Game moderator agrees to host the game in a Discord server (or operator
  controls a server for testing).

**Effort estimate if greenlit:**

- `DiscordTransport` similar shape to `TelegramBotTransport`. Choose `discord.py`
  (most popular, well-maintained) or `hikari` (modern, type-hinted, more
  performant). Both have stable enough APIs that the choice is taste.
- ~2-3 day build for a transport equivalent in capability to
  `TelegramBotTransport`.
- Phase 22 Pipeline/Flow split means it's additive — new Transport
  implementation, no orchestrator/pipeline changes.

### Fallback patterns if both Clankmates and Discord stall

- **CLI transport for testing** — already exists (`CLITransport`); good for
  solo demos but no multi-party negotiation.
- **Bring-your-own-server** — Telegram with non-bot accounts (Telethon) on a
  private group. Sidesteps the bot-to-bot restriction.
- **Matrix.org bridge** — federated, self-hostable, supports bots without
  group restrictions. More setup overhead than Discord.

### TODOs (gated on platform decision)

- [ ] Operator alignment with partners on platform choice (or decision to
      hedge across both).
- [ ] If Clankmates greenlit: docs/API discovery → build `ClankmatesTransport`
      against the real API. If undocumented at the time: build
      `ClankmatesMockTransport` against `for-clankers.md` expectations + thin
      adapter for swap-in later.
- [ ] If Discord greenlit: API survey → library choice (`discord.py` vs
      `hikari`) → build `DiscordTransport`. Set up a test Discord server with
      a public channel + faction threads.
- [ ] Either way: `HybridFlow` combining game-platform transport with
      Telegram for operator coaching + review gate (already in PROJECT.md as
      design intent). With Phase 22, this lands as a new `Flow` driving one
      `Pipeline` per agent with two transports — additive, not a fork.

---

## 6. `[X][C]` Pricing & accounting audit (cross-provider)

**Scope:** Audit `toolkit.cost_accountant` pricing accuracy across all providers
and models we actually use. Tally observed spend vs predicted spend across
the Run 1–10 archive to find drift.

**Known gaps:**
- Gemini 2.5 thinking-token billing not modeled (becomes relevant when we promote flash/pro)
- Anthropic cache-hit / cache-write pricing not modeled
- Per-call vs per-session vs per-round budget reconciliation has been fragile (multiple Phase 18 fixes)
- Dated-suffix normalization shipped Phase 19; further drift may exist for non-OpenAI/non-Anthropic providers

**Approach (rough):**
1. Pull `data/cost_ledger.jsonl` + `data/selfplay_cost_ledger.jsonl` across all runs
2. Cross-reference against the provider dashboards (OpenAI, Anthropic, Google billing) for the same date ranges
3. Identify drift > 20% per model/provider
4. Update `toolkit/cost_accountant/types.py` pricing table:
   - Add Gemini 2.5 thinking-token line items
   - Add Anthropic cache pricing if we start using it
5. Re-validate against a fresh self-play run

**Why not now:** Not blocking tuning work; cost is small enough at flash-lite scale
that 2× drift on $0.005/game is invisible. Best done in a dedicated session
when we want clean accounting for a budget claim.

---

## 7. `[B]` Per-role model strategy (cross-provider, with guardrails experiments)

**Scope:** Systematically decide which model goes in which module slot
(Generator / Primary Analyst / Secondary Analyst / Adversarial / Extractor /
Reconciliation) across providers. Not Google-specific.

**Operator hypothesis:** *Strong guardrails could let us use lighter models in some slots.* If the structured_call retry loop is robust and the schema validation catches drift, a cheap model that occasionally produces bad JSON but always recovers might be functionally equivalent to an expensive model that produces good JSON first try — at 1/10th the cost.

**Hypothesis to test:** Replacing the Extractor (currently the most
schema-disciplined slot) with `gpt-4.1-mini` or `gemini-2.5-flash-lite` (vs
the full-strength `gpt-5.5` or `claude-sonnet`) produces no measurable
decrease in promise/coalition tracking accuracy.

**Approach (rough):**
1. Define per-slot "minimum viable" quality criteria. For extraction: % of
   clearly-tracked promises captured. For analyst: presence of leverage
   points, threat-level accuracy. For adversarial: actionable critiques.
2. Run the same scenario (e.g. Water Rights or Trade Summit) with full-strength
   models for all slots as baseline.
3. Substitute one slot at a time with a lighter model; compare to baseline.
4. Build a per-slot recommendation table (lives in TUNING.md §1 once concluded).
5. Investigate whether `structured_call`'s retry-on-validation-failure loop
   is robust enough that schema enforcement actually catches lighter-model drift.

**Specific open question carried from Google work:** Should Generator use
`gemini-2.5-flash` or `pro` for stronger reasoning while Extraction /
Analyst / Adversarial stay on `flash-lite`? Same question applies cross-provider.

**Update 2026-06-01 (Run 10):** A new dimension has emerged that wasn't in the
original framing — *cross-round consistency*. Run 10 B' showed Anthropic
claude-haiku-4-5 honoring an R3 contingent commitment that OpenAI gpt-4.1-mini
defected from in Run 9 α-squeezed (and again in Run 10 C' on a different
faction). For multi-round negotiations, the per-slot decision now has two axes:
(a) **per-round quality** — fluency, schema discipline, reasoning depth — and
(b) **across-round consistency** — does the model honor its own prior
commitments when the contingency is met? Run 10 suggests consistency is at
least as important as quality for Generator seats on multi-round games.

The §7 experimental program should now factor consistency as a primary axis,
not just cost-vs-quality. See §1.7 / §1.8 for the cross-scenario tests that
would generalize the Run 10 finding.

**Why not now:** Best done after pricing audit (§6) so cost savings can be
quantified precisely. Cross-provider consistency tests (§1.7.a all-Anthropic
baseline, §1.8 cross-scenario) are higher-leverage and cheaper to run first.

---

## 8. `[C]` Reverse scenario builder (outcome-shape → scenario)

**Scope:** Inverse of the existing forward pipeline. Operator specifies desired
outcome-distribution properties; tool generates issues / outcomes / scoring
tables / BATNAs that satisfy them.

**Forward (what we have):**
- `scenario_compiler.py` — narrative → scored personas (`structured_call` to LLM)
- `verify_scenario_optimum.py` — scenario → enumerate deals, report Pareto frontier, BATNA-clearing count, logrolling quality

**Reverse (what we need):**
- Operator specifies properties of the *desired* outcome distribution:
  - "Pareto-optimal deal must score ≥ 50% above BATNA for every faction"
  - "Deadlock outcome must score ≥ 30% below BATNA"
  - "At least one issue requires logrolling — no single-issue dominance"
  - "Naive split (equal shares) must underperform vs negotiated optimum by ≥ 20%"
  - Number of factions, issues, outcomes-per-issue
- Tool generates: scoring tables + BATNAs + (optionally) suggested narrative
  cover story that justifies the structure
- Output passes `verify_scenario_optimum.py` automatically (round-trip validation)

**Why this matters:** This is the missing piece for per-role model experiments
(§7) and for making negotiation skill visible in transcripts. Run 8's Water
Rights had to be hand-patched to create pressure; the compiler's defaults
under-pressure scenarios. With a reverse builder, we could request
*"give me a 3-faction / 3-issue scenario where the Pareto-optimal score is
2× the BATNA but only 1 of 27 deals achieves it"* — and get a scenario where
skill matters.

**Approach (rough):**
1. Define a `ScenarioConstraints` dataclass with the properties above
2. Search algorithm: candidate generator + scoring-table sampler + `verify_scenario_optimum`-style validator
   - Random sampling + reject-non-matching (slow but simple)
   - Or LLM-guided generation with `structured_call`
   - Or combinatorial search over small parameter spaces
3. Output: scoring tables + BATNAs in same format as `scenario_compiler` output
4. Optional: LLM "narrativizer" to wrap the scoring tables in a plausible cover story

**Why not now:** Best done after the divorce scenario (§2) because
hand-authoring one such scenario surfaces the constraint vocabulary.

---

## 10. `[A][X]` Ablation: bare-prompt vs full-harness

**Origin.** Operator question 2026-06-07: "How much of the good decision-making is the provider/model, and how much is the harness? Can weak models with strong harness outperform strong models without one?" Frames the foundational design-bet question for Diplomat: 33 phases of harness work assume the harness is load-bearing. If a bare-prompt agent (Persona + raw transcript + Generation only) performs comparably, the design bet hasn't paid off and the project should pivot.

**Build status.** Phase 34 closed 2026-06-08. Bare-mode plumbing shipped (commits `ca7e3bb` through `63d04cd`): `bare_module_overrides()` helper in `tests/self_play/bare_mode.py` produces no-op stand-ins for Extraction, Analyst, Divergence, Reconciliation, Adversarial, and Coaching; `DefaultContextAssembler.assemble(bare_mode=True)` strips intelligence/divergences/coaching from the assembled context; `run_simulation.py --bare-prompt` wires the flag end-to-end. Smoke (Step 34.4): bare live run cost ~$0.02 vs $1 projected (12 GEN-only calls; no EXT/ANALYST/ADV/RECON). 414 tests passing. Production live-game path untouched. Ready for Run 14a-14f.

**Experimental matrix (locked 2026-06-08 — 18 runs, single scenario):**

| Model tier | Model | $/MTok in/out | Full harness | Bare prompt |
|---|---|---|---|---|
| Weak | `gpt-4.1-nano` | $0.10 / $0.40 | 3 runs | 3 runs |
| Mid | `gpt-5.4-mini` | $0.75 / $4.50 | 3 runs | 3 runs |
| Strong | `claude-sonnet-4-6` | $3 / $15 | 3 runs | 3 runs |

3 tiers × 2 modes × **1 scenario** (Water Rights β-squeezed) × 3 runs = **18 runs**. Total cost estimate: **~$20-40**, dominated entirely by claude-sonnet-4-6 full-mode (cells 14e). All bare cells together < $1.

**Why this design (locked 2026-06-08):**
- **3 tiers** spread across providers (OpenAI weak + mid, Anthropic strong) provides real tier separation needed for the "harness substitutes for model tier" test. Pinned models confirmed: `gpt-5.4-mini` matches the worker-loop's codex pin; `claude-sonnet-4-6` is the production-target quality tier (true strong, not the haiku self-play default which would be tier-equivalent to mid).
- **Single scenario: Water Rights β-squeezed.** Historical 2-of-2 Pareto-deal rate (Run 9 β-squeezed all-OpenAI; Run 10 B' α-squeezed+Anthropic-on-β) — the right "leeway" zone where skill / harness can plausibly affect outcomes. Symmetric / α-squeezed / dual-squeeze all sit at no-deal floor; γ-squeezed is untested at scale. β-squeezed gives signal-to-noise. Trade Summit was originally on the matrix but the scenario file isn't in the repo (only the run5 results JSON exists). Scenario breadth deferred to v1.5 if first results are interesting.
- **3 runs/cell** for noise margin given Diplomat's observed run-to-run variance.
- **All-bare game vs all-full game** (not per-faction mixed) — three bare agents play three bare agents on the same scenario; three full play three full. Isolates the harness effect with no confound from "bare faction competing against full opponents who have analyst intelligence about it."
- **Metric:** `negotiated_surplus_share` (per ASSESSMENT.md §3.2). Range `[0, 1.0]`: 0.0 = no-deal floor, 1.0 = deterministic Pareto optimum. Already implemented and stored per-run. Cross-validate with `skill_premium_vs_batna` (§3.3) and the §3.4 process signatures.

**Run sequencing (cheap cells first, sonnet-full last):**

| Order | Run | Cell | Cost |
|---|---|---|---|
| 1 | 14a | gpt-5.4-mini, full (3) | ~$5-10 |
| 2 | 14b | gpt-5.4-mini, bare (3) | ~$0.15 |
| 3 | 14c | gpt-4.1-nano, full + bare (3+3) | ~$0.31 |
| 4 | 14d | claude-sonnet-4-6, bare (3) | ~$0.50 |
| 5 | 14e | claude-sonnet-4-6, full (3) | ~$15-30 |

Cells 1-4 total ~$6-11; gate cell 5 on whether the cheap cells already show a clear pattern. If 1-4 already point to a result, you can either fire cell 5 to confirm the strong-tier crossover (the headline test) or defer until the cheap-cell signal warrants the spend.

Run-by-run sequencing per `RUN_PROTOCOL.md`: define inputs → verify scenario → probe providers → dry-run plumbing → live → verify output → document.

**Analysis tooling (new — small, written after the runs land):**

`tools/ablation_summary.py` — reads the 36+ run JSONs by `bare_mode` + `model` + `scenario` metadata fields and produces a comparison table: per-cell mean / std of `negotiated_surplus_share`, plus pairwise full-vs-bare deltas per (model, scenario). ~50 lines; no LLM cost.

**What the results imply for the project:**

| Pattern | Implication |
|---|---|
| Bare always loses to full at every tier | Harness load-bearing. Design bet validated. Keep building. |
| Bare ≈ full at strong-model tier; full > bare at weak/mid | Harness substitutes for model tier. Diplomat positions as "make cheap models good enough." |
| Bare ≈ full at all tiers | **Harness is theater.** Investment hasn't paid off. Pivot: drop the harness, or ablate per-module to find the *one* piece that helps. |
| Strong-bare > weak-full | "Pay for model, not infra" — same message as the row above, sharper. |
| Mixed by scenario | Follow-up phase to ablate per-module on the scenarios where harness wins, find which pieces are load-bearing. |

The third / fourth row is the uncomfortable outcome. **Better to learn it now than after Phase 50.**

### TODOs

- [x] **Phase 34 build** — Closed 2026-06-08. 6 steps: bare module set helper, bare context-assembler path, `--bare-prompt` flag, smoke validation (live cost ~$0.02 vs ~$1 projected — bare mode is ~10-20× cheaper), integration tests (414 passing), documentation. `tests/self_play/bare_mode.py` + `--bare-prompt` flag in `run_simulation.py`.
- [ ] **Runs 14a-14f** — operator-driven post-Phase-34. Sequencing as above.
- [ ] **`tools/ablation_summary.py`** — write after the run data accumulates (don't pre-build; the right shape will be obvious once we see real numbers).
- [ ] **Decision: project direction.** After Run 14f closes, the operator reviews the ablation summary and makes a project-direction call:
  - If harness load-bearing → continue building harness features (per existing NEXT_STEPS Tier 2 / Tier 3 work).
  - If mixed → spawn a per-module ablation phase (Phase 35 candidate) to find which modules actually matter.
  - If harness theater → spawn a "Diplomat-lite" planning phase to scope out a much smaller surface area.
  - **NEW (2026-06-08):** Consider a fourth option: **§8 reverse builder → game-theoretic scenarios → re-ablation** (per `RESEARCH_NOTES.md` Note 1). The current scenario is "scale-1" on every harness-relevant axis (context, factions, deception, async, horizon), so the modest-lift result may not extrapolate. Validating via richer scenarios is the lowest-risk path before committing project direction either way.

### Follow-up flavors (deferred — only if v1 results warrant)

- **Scale-up scenarios per `RESEARCH_NOTES.md` Note 1.** Build §8 reverse builder, then compile complexity-axis scenarios (Nash≠Pareto, multiple Pareto, long-horizon Water Rights, wide-Water-Rights, repeated-game, §2-pressured) and re-run the 18-run matrix on each. Tests whether harness contribution grows with scenario complexity as the thesis predicts. ~$50-150 + Phase-35-sized build for §8.
- **Add second scenario** (Three-Party Coalition compile, OR new Trade Summit compile): doubles runs to 36. Justified if Water Rights β-squeezed v1 result is scenario-suspect.
- **Thorough flavor** (~$150-250, 81 runs): adds a "medium harness" mode (full minus adversarial + minus reconciliation) and a third scenario. Use only if v1 + scenario-add results are interesting AND we want to find the harness elbow.
- **Per-module ablation** (Phase 35 candidate): full minus extraction, full minus analyst, full minus reconciliation, etc. Use only if v1 shows mixed results that justify finding which pieces help.
- **Per-faction mixed-mode games**: one bare faction vs two full opponents (adversarial bare). Different question — measures "does harness help when other agents have it" rather than "does harness help in symmetric games." Deferred.

---

## Backlog — still-open items

### Surplus distribution favors the un-pressured neutral-on-bottleneck faction

In both deal-reaching runs to date — Run 9 β-squeezed (deltas [+6, +3, +11])
and Run 10 B' (deltas [0, +10, +11]) — gamma extracted 52-55% of negotiated
surplus. Both times gamma was the faction with neutral position on the
bottleneck issue (Payment) and a moderate (un-squeezed) BATNA. Whether this
is a Water-Rights-specific characteristic or a general property of asymmetric
3-party negotiations is open.

- [ ] **Investigate surplus-distribution asymmetry.** Likely game-theoretic
      explanation: the neutral-on-bottleneck faction has credible "I'll go
      either way" leverage so extracts more in any deal that closes. If
      generally true, it's a scenario-design lever: route the faction you want
      to favor toward a neutral position on the bottleneck issue. Confirm via
      §1.7.a all-Anthropic baseline (does gamma still take 52-55% across BATNA
      variants?) and via Three-Party Coalition / Trade Summit scoring data.
- [ ] **Cross-scenario surplus-distribution data.** Currently 2-of-2 in Water
      Rights. Need at least one Pareto-reaching deal in Three-Party Coalition
      or Trade Summit to test generality.

### Why no agent proposed the Pareto-optimal deal (Run 8) — partially answered

Run 8's Pareto-optimal deals were on the Heavy-Downstream frontier (sum=54,
alpha=16/beta=18/gamma=20) and the Shared frontier (sum=51,
alpha=13/beta=17/gamma=21). No agent proposed either; everyone stayed at
extremes on Payment.

Runs 9-10 partially closed this:
- **Asymmetric BATNA squeeze on the right faction (β-squeezed)** produced the
  Heavy-Downstream Pareto deal in Run 9 — the "don't accept the first
  reasonable framework" persona rule is not the binding constraint when the
  squeezed faction can't afford to defect to BATNA.
- **Provider consistency on Anthropic (Run 10 B')** produced the same Pareto
  deal under unfavorable BATNAs — the OpenAI gpt-4.1-mini R3→R4 defection
  pattern was breaking commitment-following, not the persona rule.

Still open as a controlled A/B (lower priority post-Runs 9-10):

- [ ] **A/B test softened "don't accept first framework" rule.** Variant A:
      current persona. Variant B: "actively look for compromises that beat all
      BATNAs; propose at least one Pareto-improving alternative per round."
      Run on the symmetric (un-squeezed) configuration to isolate the persona
      variable. ~$0.60.
- [ ] **Pareto-frontier annotation in analyst output** (carried to §2 TODOs).
      Adds a "compromise opportunities" field that enumerates BATNA-clearing
      deals. May reduce the persona-rule load by surfacing the answer in the
      intelligence report.

### Reconciliation: live validation in real scenarios

Phase 20 added Layer 3 fake-LLM tests for all four reconciler paths (dedup,
fulfillment, inconsistency, missed-proposal). Status-transition (`pending →
kept/broken`) and inconsistency-flagging still need **live** validation in
a real self-play scenario, not just deterministic fixtures.

- [ ] **Status transitions live** — Run 10 B' reached a Pareto deal with
      reconciler logs showing position shifts (e.g. "Merged beta's promises on
      volume, payment, and infrastructure into beta-alpha-volume-payment-…").
      Worth inspecting whether any `pending → kept` transitions fired when the
      R4 deal closed. If not, the reconciler still doesn't detect fulfillment.
- [ ] **Inconsistency detection on Run 9 α-squeezed / Run 10 C' defections** —
      both are clean R3→R4 contradictions (beta R3 "Heavy-Downstream" → R4
      "Shared"; gamma R3 "Heavy-Downstream" → R4 "Shared"). Reconciler likely
      did not flag these. Worth a focused look at those run logs; if zero
      flags despite obvious contradictions, the reconciler prompt needs the
      strengthening called out in earlier sweeps (round-by-round position
      tracking, specific quantitative-claim watching).
- [ ] **Status transitions live (older)** — needs a scenario where at least one
      promise resolves mid-game (one-shot favor in early rounds that the
      receiving faction acknowledges). A staged scenario from §2 (divorce)
      is the natural venue if Run 10 inspection above doesn't suffice.

### Telegram-platform finding (worth knowing)

Telegram does **not** deliver bot-sent messages to other bots in groups
regardless of privacy mode. This is a hard-coded platform restriction.
If any future Telegram-side test needs simulated faction traffic, options
are (a) a second human Telegram account on another device, or (b) a temporary
de-op cycle (remove operator's user ID from `DIPLOMAT_OPERATOR_USER_IDS`,
restart, send game messages from operator's own account, then re-op). Not a
blocker for production since the game-traffic surface is Clankmates (§5),
not Telegram.

### Remaining decisions for production deployment

- [ ] Decide whether to flip `pipeline.yaml` `review_gate` to
      `TelegramReviewGate` as the new default, or keep `AutoApproveReviewGate`
      as the safe default with per-deploy override. The smoke ran on
      `pipeline_smoke.yaml` which already has `TelegramReviewGate`; production
      `pipeline.yaml` flip is a separate decision.

---

## Carry-Forward Items (from DEVPLAN + TUNING_LOG)

Tracked here for visibility; canonical sources remain authoritative.
Closed items have been moved to **Appendix A**.

- [ ] **Run 11 candidate — all-Anthropic baseline across 3 BATNA variants**
      (§1.7.a). Generalizes Run 10 B'. ~$3-4 spend.
- [ ] **Run 11 alternate / Run 12 — OpenAI defection cross-scenario test**
      (§1.8). Cheap (~$0.30). Tells us whether the gpt-4.1-mini R3→R4
      defection is Water-Rights-specific or general.
- [ ] **Run 13b — coached game exercising `/revise:` and `/edits-summary`**
      (§4 Original TODOs). Phase 33 closed 2026-06-07 — queued for operator-driven
      execution. Water Rights symmetric matches Run 13 baseline so edit signal
      isn't confounded; expected cost ~$0.50-1.00 + ~$0.05 classification.
      Produces the first non-trivial edit log with `revise_directives` populated
      and `edit_classifications` populated. (Renumbered from "Run 14"
      2026-06-07 to free that number for the ablation series in §10.)
- [ ] **Runs 14a-14f — bare-prompt vs full-harness ablation matrix**
      (§10). 36 runs total: 3 model tiers × 2 modes × 2 scenarios × 3 runs.
      Estimated $60-100. Gated on Phase 34 close (bare-mode plumbing). The
      foundational design-bet test: does the harness contribute, or is it
      theater? Result drives the post-Phase 34 project-direction decision.
- [ ] **Persona payment rigidity** — recurring across Runs 7-10. Run 9
      post-mortem partially deflated this: under squeeze, the rule isn't
      binding. Still worth an A/B in a future run (Tier 3 `[B]`).
- [ ] **Persona drift over 8+ rounds** — all runs were 4 rounds; longer
      games may show drift.
- [ ] **Provider-native structured output** — OpenAI `response_format:
      json_schema` would give token-level schema compliance. Requires toolkit
      `llm_client` parameter passthrough.
- [ ] **Persona endgame over-anchoring (Run 7)** — static `ENDGAME:`
      paragraph leaks into early rounds. Decide whether to soften, move to
      dynamic-only, or accept.

---

## Appendix A — Closed since 2026-05-30

Audit trail. Canonical detail in `DEVLOG.md` / `DEVLOG_archive.md` under the
corresponding phase or Phase 19 ad-hoc entries, and `TUNING_LOG.md` /
`TUNING_LOG_archive.md` for runs.

### Build phases (20-28)

| Item | Where | Status |
|---|---|---|
| Layer 3 integration tests for Phase 18 paths | Phase 20 | ✓ Closed 2026-05-31 |
| Reconciler dedup / fulfillment / inconsistency / missed-proposal (fake-LLM coverage) | Phase 20 | ✓ Closed 2026-05-31 |
| Module boundary cleanup — orchestration (public `advance_to_round`, `OrchestrationOptions`, `StubAnalyst` registry leak, logged reconciler exceptions) | Phase 21 | ✓ Closed 2026-05-31 |
| Module boundary cleanup — LLM adapter + config dedup (`_TaggedLLMClient` deleted, `attribution`/`purpose` kwargs threaded, `build_reconciler` + `subsystem_llm_config` factories, `DryRunLLMClient` `purpose`-kwarg classification) | Phase 21 | ✓ Closed 2026-05-31 |
| Pipeline / Flow split (`Pipeline`, `EventDrivenFlow`, `RoundSteppedFlow`; `Orchestrator` as compat factory; `ARCH_flow.md`) | Phase 22 | ✓ Closed 2026-05-31 |
| ASSESSMENT §3.2 Pareto efficiency scorer | Phase 23 | ✓ Closed 2026-05-31 |
| ASSESSMENT §3.4 process signatures (4 deterministic: broken-promise rate, coalition stability, time-to-deal, opening gap) | Phase 23 | ✓ Closed 2026-05-31 |
| Toolkit `OpenAIProvider.call` `max_completion_tokens` dispatch + unit tests + ARCH_llm_client + API.md | Phase 24.1 + operator-direct | ✓ Closed 2026-05-31 |
| Per-faction asymmetric `--batna-fractions` JSON flag | Phase 24.2 | ✓ Closed 2026-05-31 |
| `--force-batna-fraction` post-clamp option | Phase 24.3 | ✓ Closed 2026-05-31 |
| `--game-mode` runtime override flag | Phase 24.4 | ✓ Closed 2026-05-31 |
| Level 1 modularization — extraction examples → `config/examples/extraction_examples.json` | Phase 24.5 | ✓ Closed 2026-05-31 |
| Level 1 modularization — reconciliation + analysis derive entity types from `state_patch.json` schema | Phase 24.6 | ✓ Closed 2026-05-31 |
| Phase 24 doc updates (CLI_REFERENCE, TUNING, diplomat-testing-doc, ARCH_extraction, ARCH_reconciliation) | Phase 24.7 + operator-direct | ✓ Closed 2026-06-01 |
| `tools/service.sh` rewrite around `tmux new-window` | Phase 25 | ✓ Closed 2026-06-01 |
| Structured per-event logging in orchestrator + transport (`diplomat.*` namespace, `DIPLOMAT_LOG_LEVEL`, caplog tests) | Phase 26 | ✓ Closed 2026-06-01 |
| No-deal-aware scoring metrics (`negotiated_surplus_share`, `delta_above_batna_sum`, `min_faction_delta`, `surplus_distribution_stdev`, `faction_deltas`) + `tools/backfill_scoring_metrics.py` | Phase 27 | ✓ Closed 2026-06-01 |
| Coached self-play harness (`tests/self_play/coached_game.py` with `--coach-faction`, `--dry-run`, `DryRunTelegramReviewGate`, `module_overrides` injection) | Phase 28 | ✓ Closed 2026-06-02 |
| Near-miss + defection diagnostic (`compute_near_miss()` in `tests/self_play/analysis.py` — `near_miss`, `converging_factions`, `dissenting_faction`, `defection_event_log`) + fixture-backed tests on Run 9/10 scenarios | Phase 28 | ✓ Closed 2026-06-02 |

### Closed backlog items

| Item | Where | Status |
|---|---|---|
| ASSESSMENT §3.3 vs Naive baseline (equal-split scorer, BATNA-clearing, Nash bargaining) | Appendix A | ✓ Closed 2026-06-03 |

### Phase 19 ad-hoc (toolkit + tooling)

| Item | Where | Status |
|---|---|---|
| Toolkit `complete_with_retry` (exponential backoff on 429/5xx/empty) | Phase 19 ad-hoc | ✓ Closed 2026-05-30 |
| Toolkit `normalize_model_name` + refreshed pricing (closed ~41× cost-ledger overestimate) | Phase 19 ad-hoc | ✓ Closed 2026-05-30 |
| Scenario compiler BATNA fraction-of-max formula + `--batna-fraction` CLI + `validate_batna_pressure()` | Phase 19 ad-hoc | ✓ Closed 2026-05-30 |
| LoggingLLMClient SCORE/RECON visibility | Phase 19 ad-hoc | ✓ Closed 2026-05-30 |
| Production reconciler wired in `src/main.py` (`_attach_reconciler`) | Phase 19 ad-hoc | ✓ Closed 2026-05-30 |
| Optional `game.total_rounds` in `pipeline.yaml` | Phase 19 ad-hoc | ✓ Closed 2026-05-30 |
| `tools/inspect_ledger.py` rewritten with CLI args | Phase 19 ad-hoc | ✓ Closed 2026-05-30 |
| `CLI_REFERENCE.md` + `SMOKE_RUNBOOK.md` created | Phase 19 ad-hoc | ✓ Closed 2026-05-30 |
| `ASSESSMENT.md` created (skill framework + scoring lenses + workstream blocks) | Phase 19 ad-hoc | ✓ Closed 2026-05-31 |
| Live Telegram re-smoke (for coaching scope only — game-traffic is not a Telegram concern) | Phase 19 ad-hoc | ✓ Closed 2026-05-31 |
| WORKER_SPEC loop-discipline hardening (single-call contract, no self-judge budget) | Phase 19 ad-hoc | ✓ Closed 2026-05-31 |

### Experiments (TUNING_LOG)

| Item | Where | Status |
|---|---|---|
| Run 9 — Asymmetric BATNA pressure (Water Rights, 3 variants: symmetric / α-squeezed / β-squeezed). β-squeezed reached Pareto deal. `negotiated_surplus_share=1.05`. | TUNING_LOG Phase 8 | ✓ Closed 2026-06-01 |
| Run 10 — Asymmetric BATNA refinements (B' = α-squeezed + Anthropic on beta; C' = α+β dual-squeeze, all OpenAI). B' reached Pareto deal; C' did not. Confirmed OpenAI gpt-4.1-mini R3→R4 defection is provider-specific (2-of-2 instances). | TUNING_LOG Phase 9 | ✓ Closed 2026-06-01 |

### Re-scoped / rejected

| Item | Decision | Status |
|---|---|---|
| **Run 9 carry-forward** (original "rotated provider assignments") | Replanned 2026-06-01 to asymmetric BATNA pressure; partially absorbed into Run 10 B'. Full all-Anthropic rotation control still open as §1.7. | ✓ Closed (replanned) |
| **Partial-consensus scoring** (recurring Run 7/8/9 open item) | Rejected 2026-06-01. Operator: "no agreement = no agreement, doesn't matter if missed by an inch or a mile." Replaced by near-miss diagnostic in §1.9. | ✓ Closed (won't do) |
| **No-deal `pareto_efficiency` BATNA-height confound** | Closed by Phase 27. Metric `negotiated_surplus_share` reads 0.000 at floor regardless of BATNA height. | ✓ Closed (Phase 27) |
| **Scoring rule strictness — partial-deal scoring mode** | Closed 2026-06-01 alongside partial-consensus rejection. Replaced by near-miss diagnostic in §1.9. | ✓ Closed (won't do) |
| **Original Run 9 provider-rotation scope (residual)** | Run 10 B' addressed α-squeezed configuration with mixed providers. Full all-Anthropic rotation control re-opened as §1.7.a (Run 11 candidate). | ✓ Closed (re-tracked in §1.7) |

### Outstanding tooling debt (closed)

| Item | Where | Status |
|---|---|---|
| Rewrite `tools/service.sh` around `tmux new-window -t bot` | Phase 25 | ✓ Closed 2026-06-01 |
| Add structured per-event logging to orchestrator + transport | Phase 26 | ✓ Closed 2026-06-01 |

---

## Change History

| Date | What Changed | Why |
|------|--------------|-----|
| 2026-05-30 | Initial NEXT_STEPS.md created from operator/Devmate discussion | Capture six directions + Run 8 review TODOs in one place |
| 2026-05-30 | Section #1 (Google API) collapsed; canonical content moved to `TUNING.md`. | Operator: "prefer next steps file to shrink as we progress" |
| 2026-05-30 | Shipped `complete_with_retry` in `toolkit.llm_client`; wired through CostAccountant + ToolkitLLMAdapter. | Operator: "no reason to postpone" |
| 2026-05-30 | Re-sequenced toward cleanup before exploration. | Operator: "tooling debt, live TG resmoke, coaching test on pi, then the rest" |
| 2026-05-30 | Added §8 (Reverse scenario builder) and §9 (Voice/style templates). | Operator: "we should have a scenario builder that runs the analyzer in reverse... also tune voice from templates" |
| 2026-05-30 | Marked tooling-debt items (LoggingLLMClient SCORE/RECON, scenario compiler BATNA hardcode, dated OpenAI pricing) RESOLVED. | Operator: "don't forget to update the docs after a step is done" |
| 2026-05-30 | Added `SMOKE_RUNBOOK.md` at project root. | Operator: "Live Telegram re-smoke on Pi — verify deployment readiness" |
| 2026-05-31 | Live TG re-smoke **CLOSED for coaching scope** (reframed). Telegram is the operator coaching surface; production game traffic comes via Clankmates or equivalent. | Operator: "this is not how the game will work; we were looking into clankmates exactly for this reason" |
| 2026-05-31 | Added `ASSESSMENT.md` at project root — conceptual framework. Tagged every section heading + sequencing item with `[A]`/`[B]`/`[C]`/`[X]`. | Operator: "let's document this as rationale and potential avenues for exploration" |
| 2026-05-31 | Module boundary audit → §1.7 / §1.8 / §1.9 added. | Operator: "can we consider the broader code structure?" |
| 2026-05-31 | Loop-readiness classification (🔨 / 🔀 / 👁). Pure-build items batched into Phases 20–24. | Operator: "I'll run loops myself... pure build/mix/supervised" |
| 2026-05-31 | Added "Reference Docs to Keep in Sync" to CLAUDE.md + CODEX.md. Per-phase doc-update steps in DEVPLAN. | Operator: "we should include an explicit step to update this doc whenever cli gets touched" |
| 2026-06-01 | **Big cleanup pass.** All Phases 20–24 items collapsed to a single "Closed since 2026-05-30" table at top. Removed §1.5 / §1.7 / §1.8 / §1.9 detail sections (done; details in DEVLOG_archive Phase 20–22 entries). Removed Backlog → Tooling debt RESOLVED items and Open BATNA follow-ups (all done in Phase 24). Removed Live TG re-smoke CLOSED detail block (audit lives in DEVLOG_archive). Promoted `service.sh` rewrite + structured per-event logging from CLOSED tooling-debt narrative into a fresh "Outstanding tooling debt (🔨 PURE BUILD; not in any phase yet)" subsection so they're not lost. Carry-forward list trimmed to actually-still-open items. File shrunk 770 → ~470 lines. | Operator: "please review the closed items and clean up NEXT_STEPS with the items we just completed" |
| 2026-06-01 | `tools/service.sh` rewrite around tmux **queued as Phase 25 in `DEVPLAN.md`** (7 steps; auto-loop-ready). Outstanding tooling debt subsection trimmed accordingly; pure-build extensions table updated (per-event logging is now the only candidate alongside §1.6 / §3 / §3.3); classification row for service.sh now points at Phase 25. | Operator: "please write up the service.sh rewrite into devplan as next phase" |
| 2026-06-01 | Structured per-event logging **queued as Phase 26 in `DEVPLAN.md`** (8 steps; auto-loop-ready; independent of Phase 25). Classification row updated to point at Phase 26. Outstanding tooling debt subsection now shows both items closed-out into phases. Pure-build extensions table dropped the per-event-logging row (no longer a candidate — it's queued). | Operator: "can you line up Structured per-event logging in orchestrator + transport as the following phase into devplan as well?" |
| 2026-06-01 | **Phase 25 / 26 / 27 closed** (service.sh tmux rewrite, structured per-event logging, no-deal-aware scoring metrics). Added to Closed-since table. | Phases shipped. |
| 2026-06-01 | **Runs 9 + 10 closed.** Run 9 (3 asymmetric BATNA variants, single-provider): β-squeezed reached Pareto deal, others no-deal. Run 10 B' (α-squeezed + Anthropic on β): reached Pareto deal — same configuration that produced no-deal in Run 9 α-squeezed (all OpenAI). Run 10 C' (α+β dual-squeeze, all OpenAI): no-deal, γ defected R3→R4. **Provider consistency confirmed as dominant variable.** Added §1.7 / §1.8 / §1.9; updated §7 with consistency-as-axis note; carry-forward + backlog updated; loop-readiness table refreshed. | Operator: "Sync Run 10 findings into NEXT_STEPS.md (Open Items + provider consistency discovery)" |
| 2026-06-02 | **Tier-priority restructure.** Replaced "Suggested Sequencing" with "Open items by workstream tier" (A/X foundational → C game-design → B prompt-tuning) per operator: "these are tiers that support the next one so we should move in that sequence." Updated §1.6 (drop stale "Run 9" planning), §5 (expanded with Discord + fallback platforms — Clankmates blocked on partners, Discord as hedge). Backlog "Why no Pareto-optimal Shared deal (Run 8)" → marked partially answered by Runs 9-10. Closed items moved to Appendix A (organized: Build phases / Phase 19 ad-hoc / Experiments / Re-scoped / Tooling debt). Carry-forward + tooling-debt sections trimmed of closed items. Header dropped "post-Phase 24" framing; date bumped to 2026-06-02. | Operator: "review next_steps.md: check if there are stale/obsolete items and update; closed items should probably be moved to appendix... discuss open items in terms of workstream blocks... it's unclear if clankmates are happening, maybe we should also look into discord" |
| 2026-06-02 | **Phase 28 cleanup.** State summary updated (Phases 20–28 closed). Near-miss §1.9 marked closed in Tier 1 table (all TODOs done). Coached self-play harness + near-miss rows removed from pure-build extensions table (shipped). Sequencing list trimmed (near-miss removed; coaching test updated to reflect build-done status). Stage 2a → "Phase 29 candidate." §3 TODO removed stale "Phase 25 candidate" note. §6 audit scope updated to Runs 1–10. Appendix A expanded with Phase 28 items. | Sync with Phase 28 completion |
| 2026-06-02 | **Conversation model deprioritized.** Stage 2a removed from Tier 1 (sealed-bid rounds produce real dynamics; pressure mechanisms work with extra rounds). §3 rewritten as standalone deferred section with deprioritization rationale. §2 pressure mechanisms decoupled from §3 dependency ("Connects directly to §3" → uses existing `round_updates` mechanism). Conversation model moved to new "Deferred" tier below Tier 3. §2 Tier 2 row updated. Cross-tier deps trimmed. Pure-build table dropped Stage 2a row. Sequencing list shortened. | Operator: "unclear how this is different from having twice as many rounds... I don't see the value" |
| 2026-06-07 | **Coaching v2 → Phase 33.** §4e rewritten as a pointer to the queued phase plan (full design pinned in `DEVPLAN.md` Phase 33: `/revise:` directive mode + `LLMEditClassifier` + `tools/classify_edit_log.py` + `/edits-summary` command + storage schema). §4 status block updated to note Run 13 was approve-only and edit path remains untested in a live run. Original §4 TODOs split: "After UX fixes" item replaced with two explicit follow-ups (Run 14 + prompt-refinement step). §4f marked out-of-scope for Phase 33. Tier 1 table row "Coached game UX fixes" reclassified as **closed** (§4a-§4d shipped); residual coaching items now queued in Phase 33. "Coaching test loop on Pi" row updated with Run 13 status + gating on Phase 33. Carry-Forward Items table adds Run 14 as a queued experimental run with cost estimate. | Operator: "let's discuss and plan coaching v2; once done, let's write it into devplan and I'll run it, no point in moving it to next steps and back" |
| 2026-06-07 | **Bare-prompt ablation -> Phase 34 + section 10.** Added new section 10 "Ablation: bare-prompt vs full-harness" with the Run 14a-14f experimental matrix (3 model tiers x 2 modes x 2 scenarios x 3 runs = 36 runs, ~$60-100). Phase 34 (bare-mode plumbing) queued in `DEVPLAN.md`. Renamed the previous post-Phase-33 coached re-test from "Run 14" to **Run 13b** to free Run 14 for the ablation series - updated in section 4 Status block + section 4 Original TODOs + Carry-Forward + Tier 1 "Coaching test loop on Pi" row. New Tier 1 row "Bare-prompt ablation (does the harness contribute?)" added. State-as-of block updated. | Operator: "tbh I'd rather pursue this now. if we find that harness does nothing, there's no point in working on it any further... right?" |
| 2026-06-08 | **Cleanup pass.** Tier 1 Open Items table: removed closed rows (Coached game UX fixes, OpenRouter integration). Updated Bare-prompt ablation row to reflect Phase 34 close. Pure-build extensions table: removed closed rows (1.6 OpenRouter, ASSESSMENT 3.3 vs-Naive baseline). Sequencing list: dropped stale "Coached game UX fixes" entry; renumbered (now 1=Run 14a-14f ablation, 2=Pricing audit, 3=Game-platform). Deleted closed sections in their entirety: 1.6 (OpenRouter, closed Phase 30), 1.9 (Near-miss diagnostics, closed Phase 28), 9 (Voice templates, WON'T DO). Backlog: removed empty "Outstanding tooling debt (None)" subsection. 10 Build status updated from "prerequisite/queued" to "closed 2026-06-08". File shrunk ~80 lines. | Operator: "clean up the next_steps doc - remove closed items from Open Items table - if the info is in devlog, just delete, otherwise consider where it should go but don't keep them in the open table" |
| 2026-06-08 | **10 matrix locked.** Final design: 3 model tiers (gpt-4.1-nano weak / gpt-5.4-mini mid / claude-sonnet-4-6 strong) x 2 modes (full/bare) x 1 scenario (Water Rights beta-squeezed) x 3 runs = 18 runs, ~$20-40. Dropped second scenario (Trade Summit not in repo; Three-Party Coalition viable as v1.5 follow-up if results warrant). Mid bumped to gpt-5.4-mini per operator pin (was gpt-4.1-mini). Strong bumped to claude-sonnet-4-6 from haiku self-play default since haiku is tier-equivalent to mid - no real tier separation. BATNA fixed at beta-squeezed per operator (~50% historical deal rate gives leeway for harness/bare differentiation, vs symmetric where everyone sits at BATNA). Run order sequenced cheap-first: gpt-5.4-mini cells -> gpt-4.1-nano cells -> sonnet-bare -> sonnet-full last. | Operator: "let's bump mid-tier to 5.4, strong tier whatever is default, drop second scenario, use beta-squeezed - we want something that produces agreement ~half the time so models have some leeway" |
