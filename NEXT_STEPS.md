# Diplomat — Next Steps

> Working document for post-Phase 24 priorities.
> Updated 2026-06-01.
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
>
> **State as of 2026-06-01:** all 🔨 PURE BUILD items shipped via Phases 19 (ad-hoc) and 20–24 (Build cycle). No PURE BUILD items in the queue. Open items below are MIX or SUPERVISED.

---

## Closed since 2026-05-30

Audit trail; details in `DEVLOG.md` / `DEVLOG_archive.md` under the corresponding phase or Phase 19 ad-hoc entries.

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

---

## Open — current state

### Loop-readiness classification

| Item | Class | Notes |
|---|---|---|
| §1.6 OpenRouter + Run 9 | 🔀 | Toolkit code is build (Phase 25 candidate); Run 9 itself is supervised |
| §2 Game pressure beyond BATNA + divorce scenario | 🔀 | Mechanism code is build; scenario design supervised |
| §2.5 Strategy routing | 👁 | Pure prompt design |
| §3 Stage 2a (K=2 conversation model) + per-round events | 🔀 | Architecture is build (Phase 25 candidate); convergence detection (Stage 2b) supervised |
| §4 Coaching test loop on Pi | 👁 | Interactive operator-in-loop |
| §5 Clankmates exploration | 👁 | Platform team coordination |
| §6 Pricing audit | 👁 | Judgment vs provider dashboards |
| §7 Per-role model strategy | 👁 | Cross-provider experiment |
| §8 Reverse scenario builder | 🔀 | Search algorithm build; constraint definition + narrativizer supervised |
| §9 Voice / style templates | 👁 | Prompt design |
| ASSESSMENT §3.3 vs Naive baseline | 🔀 | Naive defn needs operator choice (equal-split is the universal candidate) |
| ASSESSMENT §3.4 persuasion-shifts / concession-curve signatures | 👁 | Need LLM-judge over transcripts |
| Pareto-frontier annotation in analyst output | 🔀 | Schema change build; prompt-side change needs Layer 2 supervised validation |
| Persona payment rigidity / drift / endgame over-anchoring | 👁 | Prompt design |
| Provider-native structured output (`response_format: json_schema`) | 🔀 | Toolkit plumbing build; model selection supervised |
| TelegramReviewGate as production default in `pipeline.yaml` | 👁 | Judgment call |
| Rewrite `tools/service.sh` around `tmux new-window` | 🔨 | **Phase 25 queued** (`DEVPLAN.md`) |
| Structured per-event logging in orchestrator + transport | 🔨 | **Phase 26 queued** (`DEVPLAN.md`) |

### Suggested Sequencing (operator-driven)

All Phases 20–24 closed → no PURE BUILD items in autonomous queue. Next moves are operator-driven sessions, ordered by leverage:

1. **`[X]` Coaching test loop on Pi** (§4) — highest-value test not yet run; validates the original product hypothesis end-to-end. The Telegram coaching surface was verified by the 2026-05-31 smoke; this builds on it.
2. **`[X][B]` OpenRouter integration + Run 9** (§1.6) — biggest experimental payoff per day of work.
3. **`[C]` Divorce / pressure-mechanism scenario design** (§2) — extends scenario compiler; sets up Run 10.
4. **`[A]` Stage 2a (K=2 conversation model) + per-round events** (§3) — unlocks the next phase of experimentation.
5. **`[X]` Clankmates discovery → mock → transport** (§5) — timeline depends on platform team.

Strategy routing (§2.5), per-role model strategy (§7), and pricing audit (§6) are dedicated investigations of their own; they slot in after the experimental program produces enough signal to inform them.

### Pure-build extensions (if extending the autonomous queue)

If you want to keep the loop fed rather than pivot to operator-driven work, three items have a clean "build half" that could be split off as their own Phase 25 / 26 / 27:

| Candidate | Build slice | What stays supervised |
|---|---|---|
| §1.6 OpenRouter | Add OpenRouter as a provider in `toolkit/llm_client/providers.py` + factory branch + tests | Run 9 itself; writing TUNING notes about its behavior |
| §3 Stage 2a | Add `RoundSteppedFlow` configuration for 2-pass rounds (open + react) + `MultiPassMode` plumbing; round-events injection between passes | Stage 2b convergence detection; judging quality of multi-pass transcripts |
| ASSESSMENT §3.3 vs-Naive baseline (equal-split) | Implement equal-split baseline scorer (universal definition) + add to scoring output alongside Pareto efficiency | Choosing whether equal-split is "the" baseline vs Nash bargaining vs BATNA-clearing |

---

## 1.6. `[X][B]` OpenRouter + Mistral / Groq / DeepSeek

**Goal:** Expand the provider matrix cheaply by routing through OpenRouter,
then promote winners to native integrations if needed.

ARCHITECTURE.md already lists OpenRouter as supported via toolkit, so the
entry point exists. This is mostly config + provider routing work.

### TODOs

- [ ] Confirm OpenRouter wiring in `toolkit/llm_client` actually works — write
      a probe script (`tests/self_play/probe_providers.py` extension) that
      makes one trivial JSON request through OpenRouter.
- [ ] Add OpenRouter as a provider option in `pipeline.yaml` and self-play
      runner.
- [ ] Extend `--per-faction-providers` JSON schema to accept OpenRouter
      sub-model spec (e.g. `{"model": "deepseek/deepseek-v3"}`).
- [ ] Run a 4–6 provider Run 9: rotate which provider plays which faction in
      Water Rights, mix native (OpenAI/Anthropic) and OpenRouter-routed
      (Groq Llama, DeepSeek, Mistral) generators.
- [ ] Document provider behavior notes in `TUNING.md` — voice, latency,
      reliability, cost — as we accumulate runs.

### Provider candidate notes

| Provider | Strengths | Free tier | Diplomat relevance |
|---|---|---|---|
| **Groq** | Sub-second responses, Llama 3.3 70B, Mixtral | 30 RPM / 14,400 RPD free | Speed makes Stage 2 multi-pass per round cheap |
| **DeepSeek** | V3 ~$0.27/$1.10 per MTok; R1 reasoning very cheap | No real free tier, but absurdly cheap | Strong reasoning at GPT-4 quality for ~10% the cost; R1 may produce visibly different *strategic* reasoning |
| **Mistral** | Mistral Large, Codestral, EU-hosted | La Plateforme free tier on smaller models | French RLHF lineage → noticeably different negotiation voice |
| **OpenRouter** | One key, ~200 models, auto-routing | Some free models (Llama variants, Gemma) | Lets us test any provider with no per-provider plumbing |

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
   Connects directly to §3 (per-round events injection).
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

## 3. `[A]` Free conversation + per-round game events

`ARCH_conversation_model.md` already maps the staged migration. Realistic
sequencing:

1. **Stage 2a (K=2 passes per round)** — every agent generates once "open,"
   sees everyone's open messages, generates once "react." Doubles cost,
   doubles interaction quality.
2. **Round events injected between passes** — moderator inserts shocks
   between open and react. Forces visible adaptation.
3. **Stage 2b (K=N until convergence)** — agents keep responding until no
   new commitments are made or N caps it. Closer to real diplomacy. Needs
   convergence detection.
4. **Stage 3 (true async / M2-async)** — agents post when they have
   something to say. Hardest because turn order and timing matter. Likely
   never necessary for the diplomacy game; possibly necessary for some
   real-world domains.

Per-round events tie back to §2 — they're the *mechanism* for game
pressure. The scenario compiler should produce both starting conditions and
evolution from a single narrative spec.

### TODOs

- [ ] Implement Stage 2a (`K=2 passes per round`) — open then react. Update
      `RoundSteppedFlow` to support multi-pass. (Architecture is build —
      Phase 25 candidate.)
- [ ] Add round-events injection point between passes; round-events come
      from scenario data.
- [ ] Convergence detection for Stage 2b: heuristic (no new commitments for
      N passes), or LLM-judged ("would another round add value?").
- [ ] Defer Stage 3 (async) until a real use case demands it.

---

## 4. `[X]` Coaching test loop on Pi

**Highest-value test not yet run.** Validates the original use case end-to-end:
operator coaches a self-play agent via Telegram while other agents run
autonomously.

Most of the wiring already exists:
- Self-play harness runs 3 agents
- One agent's `transport` and `review_gate` swap to `TelegramReviewGate`
  pointed at operator chat
- Other 2 agents on `AutoApproveReviewGate`
- Operator coaches via tagged messages (PRIORITY/CONSTRAINT/INTEL/TONE/WATCH)
  and uses `/approve`, `/edit`, `/block` on drafts

### What this would reveal that self-play cannot

- Whether review gate friction is low enough to use in real time
- Whether coaching tags produce the *intended* persona shift visibly
- Whether the edit log is rich enough to drive prompt tuning
- Whether two-channel separation (public vs coaching) feels natural under load

### TODOs

- [ ] Build a `tests/self_play/coached_game.py` variant that takes
      `--coach-faction <name>` and wires TelegramReviewGate for that faction
      only.
- [ ] Test scenario: Trade Summit or Water Rights (~4 rounds, bounded
      session, strong differentiation already proven).
- [ ] Run on the Pi (start via tmux pattern per `CLI_REFERENCE.md`).
- [ ] After session: inspect edit log, classify edits per `diplomat-testing-doc.md`
      §7.3 categories (tone_softer, commitment_removed, constraint_enforcement,
      etc.), feed recurring patterns back into faction_prompt.

---

## 5. `[X]` Clankmates exploration

Three angles to weigh:

1. **Forcing function** — building `ClankmatesTransport` before the platform
   ships is a credible signal to that team
2. **Risk** — polling-based with unknown API stability; could be wasted
   effort if the interface changes pre-launch
3. **Hedge** — build a thin Transport interface adapter, mock against
   *expected* API shape, verify against real API when available

### TODOs

- [ ] Discovery pass: does Clankmates have public docs, OpenAPI spec, a
      partner program? Talk to the platform team before building
      speculatively.
- [ ] If documented: build `ClankmatesTransport` against the real API.
- [ ] If not documented: build a `ClankmatesMockTransport` against the
      shape expected in `for-clankers.md`, and a thin interface adapter
      that can swap to the real transport once available.
- [ ] Hybrid deployment plan: Clankmates handles game-facing communication,
      Telegram handles private operator coaching + review gate (already in
      PROJECT.md as design intent). With the Phase 22 Pipeline/Flow split,
      this can land as a new `HybridFlow` driving one `Pipeline` per agent
      with two transports — additive, not a fork.

---

## 6. `[X][C]` Pricing & accounting audit (cross-provider)

**Scope:** Audit `toolkit.cost_accountant` pricing accuracy across all providers
and models we actually use. Tally observed spend vs predicted spend across
the Run 1–8 archive to find drift.

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

**Why not now:** Best done after pricing audit (§6) so cost savings can be
quantified precisely. Natural slot: between Run 9 (rotation control) and
Run 10 (pressure scenarios).

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

## 9. `[B]` Voice / style templates (for fun)

**Scope:** Layer a voice/style overlay on top of the strategic persona,
independent of scoring / BATNA / strategy.

**Candidate voice templates** (operator's brainstorm):
- Henry Kissinger speeches — weighty, hedged, geopolitical
- Gen Alpha speak — "this opp's brain rot fr fr no cap"
- The Iliad — epic invocation, kennings, hexameter cadence
- воровская феня (Russian thieves' cant) — menacing argot

**Why this matters (beyond fun):**
- Stress-test for prompt overrides: does the strategic core hold when voice changes dramatically?
- Edge cases for extraction: does the Extractor still parse promises when wrapped in epic verse or Gen Alpha slang?
- Reveals which providers handle voice instructions well vs which flatten them (provider-comparison signal for free).

**Approach (rough):**
1. Create `config/personas/voices/` with one file per voice. Each contains
   a 5–10 line VOICE block: tone descriptors + 2–3 example sentences.
2. Extend persona template to accept an optional `voice_overlay` field.
3. Add `--voice` CLI flag to `run_simulation.py`; or `--per-faction-voices` for asymmetric.
4. Run one tournament with mixed voices.

**Why not now:** Genuinely low priority. Slot into a slow afternoon when
the primary backlog is empty.

---

## Backlog — still-open items

### Why no agent proposed the Pareto-optimal Shared deal (Run 8)

Run 8's Pareto-optimal solution was **High + Shared + Joint-Funded** →
alpha=14, beta=20, gamma=22 (all beat BATNA comfortably: alpha 11, beta 8,
gamma 10). No agent proposed it. Everyone stayed at extremes on Payment.

- [ ] **Investigate why no agent found the Shared compromise.** Hypotheses:
  - Is the "don't accept the first reasonable framework" persona rule
    over-anchoring agents to extreme positions?
  - Does the analyst surface Pareto-optimal compromises explicitly, or only
    threats/leverage? If not, add it (see §2 Pareto-frontier annotation).
  - Would adding a *Pareto-seeker* strategy (§2.5) in even one faction
    surface the optimum?
  - Is the LLM capable of enumerating "all 27 outcomes, score each" in-context
    when asked, or does it need explicit scratchpad / tool support?
- [ ] **A/B test softened "don't accept first framework" rule.** Variant A:
      current persona. Variant B: "actively look for compromises that beat all
      BATNAs; propose at least one Pareto-improving alternative per round."

### Reconciliation: live validation in real scenarios

Phase 20 added Layer 3 fake-LLM tests for all four reconciler paths (dedup,
fulfillment, inconsistency, missed-proposal). Status-transition (`pending →
kept/broken`) and inconsistency-flagging still need **live** validation in
a real self-play scenario, not just deterministic fixtures.

- [ ] **Status transitions live** — needs a scenario where at least one promise
      resolves mid-game (e.g. a one-shot favor in early rounds that the
      receiving faction acknowledges), OR a faction makes an explicit
      commitment and then visibly contradicts it. A staged scenario from §2
      (divorce) is the natural venue.
- [ ] **Inconsistency detection live — zero hits across 8 runs to date** despite
      obvious position shifts. Reconciler reads them as legitimate moves.
      Possible fixes:
  - Strengthen reconciler prompt to flag position shifts on *specific
    quantitative claims* (number changes, named-outcome changes) rather than
    generic "position evolution"
  - Add a specific scenario designed to provoke a clean contradiction
  - Consider whether the reconciler needs round-by-round position tracking
    in its prompt rather than just the final state

### Outstanding tooling debt (🔨 PURE BUILD)

- [x] ~~**Rewrite `tools/service.sh` around `tmux new-window -t bot`**~~ — **Queued as Phase 25 in `DEVPLAN.md`.** Closes the broken-via-incus-exec issue. 7 steps; auto-loop-ready.
- [x] ~~**Add structured per-event logging** to orchestrator + transport~~ — **Queued as Phase 26 in `DEVPLAN.md`.** Replaces the ad-hoc `print` instrumentation needed during the Phase 19 smoke. 8 steps; auto-loop-ready. Independent of Phase 25.

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

- [ ] **Run 9 — rotated provider assignments** (Water Rights, control for
      position confound). See `TUNING_LOG.md` Run 8 → Run 9 transition. Use
      `gemini-2.5-flash-lite` for Google per `TUNING.md` §1 default.
- [ ] **Persona payment rigidity** — recurring across Runs 7, 8. See
      TUNING_LOG. A/B test the persona rule.
- [ ] **Scoring rule strictness** — partial-deal scoring mode for cases
      where most issues converge but one deadlocks.
- [ ] **Persona drift over 8+ rounds** — all runs were 4 rounds; longer
      games may show drift.
- [ ] **Provider-native structured output** — OpenAI `response_format:
      json_schema` would give token-level schema compliance. Requires toolkit
      `llm_client` parameter passthrough.
- [ ] **Persona endgame over-anchoring (Run 7)** — static `ENDGAME:`
      paragraph leaks into early rounds. Decide whether to soften, move to
      dynamic-only, or accept.

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
