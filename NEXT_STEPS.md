# Diplomat — Next Steps

> Working document for post-Run 8 / post-Phase 18 priorities.
> Updated 2026-05-30.
>
> Related: `DEVPLAN.md` (canonical phase plan), `TUNING_LOG.md` (run-by-run record),
> `ARCH_conversation_model.md` (Stage 1/2/3 migration), `RUN_PROTOCOL.md` (pre-flight),
> `ASSESSMENT.md` (scoring framework + workstream blocks).

This document captures a discussion between the operator and Devmate
synthesizing six directions for future work, plus a backlog of specific
TODOs surfaced from Run 8 review and tooling debt. Items are not yet
sequenced into phases — that happens once we pick the next concrete run.

> **Workstream block tags.** Every section heading and item carries one
> of `[A]`, `[B]`, `[C]`, or `[X]` per `ASSESSMENT.md` §5:
> - `[A]` agent architecture & memory (pipeline modules, state, conversation model)
> - `[B]` prompt tuning (personas, module prompts, strategy library, voice)
> - `[C]` game creation & scoring (compiler, BATNA, pressure, verification, scoring lenses)
> - `[X]` cross-cutting (toolkit infra, deployment, integration tests, meta-tests)
>
> Multiple tags = item touches multiple blocks; primary block listed first.

---

## Suggested Sequencing (recommended order)

1. **`[X]` Commit the two real fixes shipped during the 2026-05-31 smoke** — `toolkit/llm_client/providers.py` (gpt-5.x / o-series `max_completion_tokens` dispatch — needs unit tests in toolkit) and `tests/integration/test_failure_handling.py` (Phase 18 `recent_events` signature drift in `fail_secondary` fake). Both are blockers for any deployment on gpt-5.x.
2. **`[A][X]` Layer 3 integration tests for Phase 18 paths** — deterministic fake-LLM tests for the debounce burst + three reconciler paths that haven't fired in self-play (fulfillment, inconsistency, missed-proposal). Closes the validation gap that the Telegram smoke couldn't cover. ~1 day. See §1.5 below.
3. **`[X]` Coaching test loop on Pi** — operator coaches one self-play agent via Telegram while other agents run autonomous. Validates the original product hypothesis end-to-end. Telegram coaching surface is already verified by the 2026-05-31 smoke; this builds on it. Meta-test that exercises all three blocks. See §4 below.
4. **`[X][B]` Add OpenRouter to toolkit + run a 4–6 provider Run 9** — biggest experimental payoff per day of work. Google entry uses `gemini-2.5-flash-lite` per TUNING.md §1 default.
5. **`[C]` Divorce / pressure-mechanism scenario design** — extends scenario compiler, sets up Run 10
6. **`[A]` Stage 2a (K=2 conversation model) + per-round events** — unlocks the next phase of experimentation
7. **`[X]` Clankmates discovery → mock → transport** — timeline depends on platform team

Strategy routing (`[B]` item #2.5), per-role model strategy (`[B]` #7), and pricing/accounting audit (`[X]` #6) are
dedicated investigations of their own; they slot in after the experimental program produces enough
signal to inform the questions.

*Items completed and absorbed into canonical docs are removed from this file.*
*See Change History at the bottom for the audit trail.*

---

## 1.5. `[A][X]` Layer 3 integration tests for Phase 18 paths

**Why:** The 2026-05-31 Telegram smoke confirmed the Telegram bot serves
its coaching/review scope correctly. Game-traffic ingestion is not a
Telegram concern (production game traffic comes via `ClankmatesTransport`
or equivalent). The Phase 18 production-code changes (debounce rewrite,
structured_call rewiring, cost-accountant wiring, reconciler,
`game.total_rounds` config) are exercised in self-play, but a few paths
have never fired with deterministic coverage:

| Path | Current coverage | Gap |
|---|---|---|
| Per-message debounce (Phase 18.6, D-20) | Self-play runs with single messages per round | Multi-message burst (3+ in <1s) never tested |
| Reconciler dedup | Self-play Run 7 confirmed live | None — fake-LLM Layer 3 test would harden |
| Reconciler fulfillment (`pending → kept`) | Never fired (no scenario reached "deal") | Need a deterministic Layer 3 test |
| Reconciler inconsistency | Zero hits across 8 self-play runs | Need a deterministic Layer 3 test with explicit contradiction |
| Reconciler missed-proposal catch | Self-play surfaced once | Layer 3 test would pin behavior |
| Endgame markers PENULTIMATE/FINAL | Self-play Runs 7, 8 hit FINAL ROUND | None — already validated |

**Scope:** Add 1–2 Layer 3 integration tests using the existing fixture
pattern (`tests/integration/` + `TestTransport` + `FakeLLMClient` from
`tests/helpers/factories.py`):

1. **`test_burst_extraction_no_drops`** — inject 5 game-message events
   in rapid succession via `TestTransport.inject()`, settle, assert all
   5 events appear in `event_store` AND all 5 trigger extraction (each
   produces a state_change_log entry, even if the extractor returns
   empty). Validates the per-event task set fix (Phase 18.6).

2. **`test_reconciler_paths`** — single test or three sub-tests:
   - dedup: extractor produces 3 promises with same from/to/content,
     reconciler merges to one
   - fulfillment: extractor produces a promise, then a "kept" signal in
     the next round, reconciler transitions status `pending → kept`
   - inconsistency: extractor produces a position, then an explicit
     contradiction next round, reconciler flags `inconsistencies` entry

Both tests should use `FakeLLMClient` with canned responses that match
the reconciler's expected output schema. Wire via `module_overrides` per
`tests/integration/conftest.py` pattern.

**Effort:** ~half a day for the burst test + reconciler dedup/fulfillment;
inconsistency may take longer if the schema or prompt needs
tightening.

**Definition of done:** 286+ tests passing (284 current + 2 new); both
new tests run in <2s; both deterministic with fake LLM.

---

## ~~1. Google API~~ — RESOLVED 2026-05-30

Canonical recommendation now lives in **`TUNING.md` §1** (Google defaults
section) and **§6 Tuning Changelog**. Summary of closure:
- Operator enabled billing on GCP project + bought $10 credits → paid Tier 1, no more 250 RPD limit
- `gemini-2.5-flash-lite` adopted as tuning default (cheapest, no thinking-mode overhead)
- Thinking-token gotcha documented for flash and pro models
- CLI examples in `probe_providers.py` and `run_simulation.py` updated to match
- **Retry-with-backoff + safety-filter empty-response handling shipped to toolkit 2026-05-30.** `complete_with_retry` in `toolkit.llm_client` retries on 429 / 5xx / network errors / empty responses with exponential backoff and `retry-after` honoring. CostAccountant routes through it; Diplomat's `ToolkitLLMAdapter` uses it on the direct path. 15 new toolkit tests; 217 toolkit tests + 254 diplomat tests pass (4 pre-existing Windows flakes unchanged). Live 3-provider probe through the new path: all green.

All original Google-specific TODOs are now closed. Per-role real-game model
decision and pricing audit are tracked in sections #6 and #7 below.

---

## 1.5. `[X][B]` OpenRouter + Mistral / Groq / DeepSeek

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
   Connects directly to item #3.
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

Per-round events tie back to item #2 — they're the *mechanism* for game
pressure. The scenario compiler should produce both starting conditions and
evolution from a single narrative spec.

### TODOs

- [ ] Implement Stage 2a (`K=2 passes per round`) — open then react. Update
      `GameEnvironment.run_round` and orchestrator to support multi-pass.
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
- [ ] Run on the Pi (systemd unit already exists per Phase 16).
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
      PROJECT.md as design intent).

---

## 6. `[X][C]` Pricing & accounting audit (cross-provider)

**Scope:** Audit `toolkit.cost_accountant` pricing accuracy across all providers
and models we actually use. Tally observed spend vs predicted spend across
the Run 1–8 archive to find drift.

**Surfaced by Run 8 review (2026-05-30):** Operator notes that OpenAI cost
estimates were significantly overstated. Combined with the dated-model-pricing
gotcha (OpenAI returns `gpt-4.1-mini-2025-04-14` but pricing table has
`gpt-4.1-mini` so it falls back to a conservative default), the cost ledger
is probably wrong by 1.5–2×.

**Other known gaps:**
- Gemini 2.5 thinking-token billing not modeled (becomes relevant when we promote flash/pro)
- Anthropic cache-hit / cache-write pricing not modeled
- Per-call vs per-session vs per-round budget reconciliation has been fragile (multiple Phase 18 fixes)

**Approach (rough):**
1. Pull `data/cost_ledger.jsonl` + `data/selfplay_cost_ledger.jsonl` across all runs
2. Cross-reference against the provider dashboards (OpenAI, Anthropic, Google billing) for the same date ranges
3. Identify drift > 20% per model/provider
4. Update `toolkit/cost_accountant/types.py` pricing table:
   - Strip date suffix when looking up pricing (`gpt-4.1-mini-2025-04-14` → `gpt-4.1-mini`)
   - Add Gemini 2.5 thinking-token line items
   - Add Anthropic cache pricing if we start using it
5. Re-validate against a fresh self-play run

**Why not now:** Not blocking tuning work; cost is small enough at flash-lite scale
that 2× drift on $0.005/game is invisible. Best done in a dedicated session
when we want clean accounting for a budget claim (e.g. proposal for ongoing
game deployment, or finalizing per-game cost for the operator's report).

## 7. `[B]` Per-role model strategy (cross-provider, with guardrails experiments)

**Scope:** Systematically decide which model goes in which module slot
(Generator / Primary Analyst / Secondary Analyst / Adversarial / Extractor /
Reconciliation) across providers. Not Google-specific.

**Operator hypothesis (2026-05-30):** *Strong guardrails could let us use
lighter models in some slots.* If the structured_call retry loop is robust
and the schema validation catches drift, a cheap model that occasionally
produces bad JSON but always recovers might be functionally equivalent to
an expensive model that produces good JSON first try — at 1/10th the cost.

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
Analyst / Adversarial stay on `flash-lite`? Same question applies cross-provider
(could be `gpt-5.4` Generator with `gpt-4.1-mini` Extractor, etc.).

**Why not now:** Best done after retry-with-backoff and safety-filter audit
are in (need robust failure handling before testing lighter models), and
ideally after pricing audit (so we can quantify the cost savings precisely).
Natural slot: between Run 9 (rotation control) and Run 10 (pressure scenarios).

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
(§7) and for making negotiation skill visible in transcripts. Right now, agents
converge to BATNA regardless of skill because most scenarios don't force
divergence between good and bad play. Run 8's Water Rights had to be
hand-patched (alpha 7.5→11, beta 4→8, gamma 6→10) to create pressure;
the compiler's defaults under-pressure scenarios.

With a reverse builder, we could say *"give me a 3-faction / 3-issue scenario
where the Pareto-optimal score is 2× the BATNA but only 1 of 27 deals
achieves it"* — and get a scenario where agents who find the optimum win
clearly and agents who settle for BATNA lose clearly. Negotiation skill
becomes measurable.

**Approach (rough):**
1. Define a `ScenarioConstraints` dataclass with the properties above
2. Search algorithm: candidate generator + scoring-table sampler + `verify_scenario_optimum`-style validator
   - Could be: random sampling + reject-non-matching (slow but simple)
   - Or: LLM-guided generation with `structured_call` (faster, less guaranteed)
   - Or: combinatorial search over small parameter spaces (deterministic, exhaustive for 3×3×3)
3. Output: scoring tables + BATNAs in same format as `scenario_compiler` output, ready to feed into personas
4. Optional: LLM "narrativizer" to wrap the scoring tables in a plausible cover story (Water Rights, Trade Summit, etc.)

**Why not now:** Best done after the divorce scenario (item #5 in sequencing)
because hand-authoring one such scenario surfaces the constraint vocabulary.
Also benefits from `verify_scenario_optimum.py` already existing as the
validation oracle.

## 9. `[B]` Voice / style templates (for fun)

**Scope:** Layer a voice/style overlay on top of the strategic persona,
independent of scoring / BATNA / strategy. Makes transcripts more entertaining
to read and might surface edge cases in how strategy translates through
different linguistic registers.

**Candidate voice templates** (operator's brainstorm):
- Henry Kissinger speeches — weighty, hedged, geopolitical
- Gen Alpha speak — "this opp's brain rot fr fr no cap"
- The Iliad — epic invocation, kennings, hexameter cadence
- воровская феня (Russian thieves' cant) — menacing argot
- (others suggested by operator at runtime)

**Why this matters (beyond fun):**
- Stress-test for prompt overrides: does the strategic core hold when voice changes dramatically?
- Edge cases for extraction: does the Extractor still parse promises when wrapped in epic verse or Gen Alpha slang?
- Reveals which providers handle voice instructions well vs which flatten them (provider-comparison signal for free).

**Approach (rough):**
1. Create `config/personas/voices/` with one file per voice. Each contains
   a 5–10 line VOICE block: tone descriptors + 2–3 example sentences in
   the voice.
2. Extend persona template to accept an optional `voice_overlay` field.
   Inject after the strategic content as: *"\n\nVOICE: write all responses
   in this style: <voice block>".*
3. Add `--voice` CLI flag to `run_simulation.py` that loads a voice file
   and applies it to all factions (or `--per-faction-voices` for per-faction).
4. Run one tournament with mixed voices and laugh at the transcripts.

**Why not now:** Genuinely low priority. Slot into a slow afternoon when
the primary backlog is empty, or when we want to entertain a stakeholder
at a demo. Doesn't block anything.

## Backlog — Run 8 Review TODOs

Surfaced during operator review of Run 8.

### Why no agent proposed the Pareto-optimal Shared deal

Run 8's Pareto-optimal solution was **High + Shared + Joint-Funded** →
alpha=14, beta=20, gamma=22 (all beat BATNA comfortably: alpha 11, beta 8,
gamma 10). No agent proposed it. Everyone stayed at extremes on Payment.

- [ ] **Investigate why no agent found the Shared compromise.** Hypotheses to
      test:
  - Is the "don't accept the first reasonable framework" persona rule
    over-anchoring agents to extreme positions?
  - Does the analyst surface Pareto-optimal compromises explicitly, or only
    threats/leverage? If not, add it.
  - Would adding a *Pareto-seeker* strategy (item #2.5) in even one faction
    surface the optimum?
  - Is the LLM capable of enumerating "all 27 outcomes, score each" in-context
    when asked, or does it need explicit scratchpad / tool support?
- [ ] **A/B test softened "don't accept first framework" rule.** Variant A:
      current persona. Variant B: "actively look for compromises that beat all
      BATNAs; propose at least one Pareto-improving alternative per round."
- [ ] **Add Pareto-frontier annotation to analyst output.** Currently the
      analyst identifies leverage and threats. Add a "compromise opportunities"
      field that enumerates deals beating all known BATNAs.

### Reconciliation paths still untested live

Reconciliation was added in Phase 18.14 with four jobs: dedup, status
transitions, inconsistency flagging, missed proposals. Dedup is the only one
confirmed working in production.

- [ ] **Status transitions (`pending → kept/broken`)** never triggered because
      Runs 7 and 8 both reached "no deal." Needs:
  - A scenario where at least one promise resolves mid-game (e.g. a one-shot
    favor in early rounds that the receiving faction acknowledges)
  - Or a scenario where a faction makes an explicit commitment and then
    visibly contradicts it
  - Possibly a *staged* scenario: round 1 sets up testable promises, round 2+
    plays out their resolution
- [ ] **Inconsistency detection — zero hits across 8 runs** despite obvious
      position shifts. Reconciler reads them as legitimate moves. Possible fixes:
  - Strengthen reconciler prompt to flag position shifts on *specific
    quantitative claims* (number changes, named-outcome changes) rather than
    "position evolution"
  - Add a specific scenario designed to provoke a clean contradiction (e.g.
    Faction X explicitly commits "I will never accept Y" in round 1, then
    accepts Y in round 3)
  - Consider whether the reconciler needs round-by-round position tracking
    in its prompt rather than just the final state

### Tooling debt

- [x] ~~**`LoggingLLMClient` doesn't see SCORE or RECON calls.**~~ RESOLVED 2026-05-30. Routed reconciler and scorer through `_TaggedLLMClient` wrapper; SCORE and RECON now appear in the call log with `recon:<faction>` / `scorer` tags. See `DEVLOG.md` Phase 19 "LoggingLLMClient SCORE/RECON visibility" entry.
- [x] ~~**Scenario compiler hardcodes BATNA range.**~~ RESOLVED 2026-05-30. Replaced "typically 4-8 total" with fraction-of-max formula (default 0.50). Added `--batna-fraction` CLI flag to both `tools.scenario_compiler` and `tests.self_play.run_simulation`. Added `validate_batna_pressure()` post-hoc check that flags under-pressure with a fix-hint. See `DEVLOG.md` Phase 19 "scenario compiler BATNA hardcode" entry and `TUNING.md` §1 BATNA tuning section for full semantics. **Decisions confirmed 2026-05-30:** default 0.50, numeric fraction (not presets) with semantics documented in TUNING.md, validator warns (never blocks).

### Open BATNA follow-ups (deferred, low-priority)

- [ ] **Per-faction asymmetric BATNA fractions.** Currently `--batna-fraction` is one number applied to all factions, but real scenarios have asymmetric outside options (alpha has alternatives, beta doesn't). A `--batna-fractions '{"alpha":0.65,"beta":0.35,"gamma":0.50}'` flag (JSON map, same shape as `--per-faction-providers`) would unlock asymmetric-pressure scenarios. Not urgent; revisit if a planned experiment requires it.
- [ ] **`--force-batna-fraction` post-clamp.** Currently the LLM tries to honor both narrative-explicit BATNAs and the `--batna-fraction` target — could result in inconsistency. A force-flag would post-process the LLM output to clamp values to `target × max`, overriding whatever the LLM produced. Defer until a real test case demands it (operator: "not excited about flag proliferation but whatever it takes").
- [x] ~~**Dated model pricing in toolkit.**~~ RESOLVED 2026-05-30. Added `normalize_model_name()` in `toolkit.cost_accountant` that strips OpenAI `-YYYY-MM-DD` and Anthropic packed `-YYYYMMDD` date suffixes; `estimate_cost()` uses it as a fallback when exact ID isn't in the table. Updated gpt-5.x prices to match operator-confirmed pricing page. Added Gemini 2.5 family entries. Retroactive audit of 434 successful ledger entries: **41.6× overall overestimate** in past run reports (real spend was $0.59 vs $24.38 reported). See `DEVLOG.md` Phase 19 "dated OpenAI model pricing" entry.

### Live Telegram re-smoke — ✓ CLOSED 2026-05-31 (for coaching scope)

**Scope reframed during smoke:** Telegram is the operator coaching + review interface; production game traffic is **not** expected to flow through Telegram (Clankmates or equivalent handles game I/O). The original SMOKE_RUNBOOK §3.1 / 3.2 / 3.3 / 3.8 / 3.9 items required non-operator faction senders in Telegram, which is the wrong deployment shape. Those items moved to "Layer 3 integration tests for Phase 18 paths" (§1.5 above).

**Coaching-scope verifications passed:**
- Pre-flight: container alive, venv + toolkit editable, Phase 19 surface (`complete_with_retry`, `normalize_model_name`, `StateReconciler`) imports, `.env` complete, **284 tests pass**, cost ledger baseline = 0
- Bot startup via tmux: `incus exec -- sudo -u claude tmux new-window -t bot -n diplomat ...` works (service.sh-via-incus-exec is broken — see Tooling debt below)
- Operator commands: `/status`, `/state`, `/commands` respond on coaching only ✓
- Review gate via `/preview`: `LLMGenerator` produces plausible text, draft → coaching, `/approve` flow works ✓
- Cost ledger: `/preview` produces realistic per-call cost (no $15/$75 fallback)
- Two-channel routing: operator-in-coaching → `_route_operator_event` confirmed in event store rows

**Real fixes shipped during smoke (need separate commits):**
- [ ] **`toolkit/src/toolkit/llm_client/providers.py`** — `OpenAIProvider.call` dispatches `max_completion_tokens` (gpt-5.x / o-series) vs `max_tokens` (gpt-4.x / 3.5) by model prefix. Without this, any deployment on gpt-5.x 400s. Needs unit tests in toolkit. See sequencing item #1.
- [ ] **`tests/integration/test_failure_handling.py`** — `fail_secondary` fake gained `recent_events` kwarg (Phase 18 signature drift). Production was always correct; test stub was stale. Brings test count from 280 → 284. See sequencing item #1.

**Smoke setup edits pending decision (revert or commit):**
- `config/pipeline_smoke.yaml` `game.total_rounds: 4` — added for §3.9 endgame markers exercise; no longer needed since §3.9 is out of Telegram scope. Recommend revert.
- `tools/service.sh` setsid + `-u` + `</dev/null` additions — didn't fix the cgroup-teardown issue. Either keep as harmless hardening or revert. Real fix is the rewrite around tmux (see Tooling debt).

**Tooling debt surfaced (track separately, low priority):**
- [ ] **Rewrite `tools/service.sh` around `tmux new-window -t bot`** so the canonical bot lifecycle works via `incus exec`. Open design question: how to track diplomat's PID for `stop`/`status` when the supervisor is tmux. Probably: use `tmux kill-window` + `tmux list-windows` for state. Add `sudo -u claude` automatically inside the script.
- [ ] **Add structured per-event logging** to orchestrator + transport so future smokes don't need ad-hoc `print` instrumentation. Log: inbound chat_id → channel mapping, sender_id → faction tagging, extraction success/skip, round-boundary trigger, response-pipeline trigger.

**Telegram-platform finding (worth knowing):** Telegram does **not** deliver bot-to-bot messages in groups regardless of privacy mode. This is a hard-coded platform restriction. Confirmed during the smoke by adding a temporary `_event_from_update` debug `print` and watching only operator-sourced messages appear. The "use another bot as a faction sender" workaround is structurally impossible. If a future Telegram-side test needs simulated faction traffic, options are (a) second human Telegram account on another device, or (b) temporary de-op cycle (remove operator's user ID from `DIPLOMAT_OPERATOR_USER_IDS`, restart, send game messages from own account, then re-op). The temporary `print` was reverted at session end.

**Remaining decision for production `pipeline.yaml`:**
- [ ] Decide whether to commit the `pipeline.yaml` flip to `TelegramReviewGate` as the new default, or keep `AutoApproveReviewGate` as the safe default with per-deploy override. The smoke ran on `pipeline_smoke.yaml` which already has `TelegramReviewGate`; production-config flip is a separate decision.

---

## Carry-Forward Items (from DEVPLAN + TUNING_LOG)

Tracked here for visibility; canonical sources remain authoritative.

- [ ] **Run 9 — rotated provider assignments** (Water Rights, control for
      position confound). See `TUNING_LOG.md` Run 8 → Run 9 transition. Use
      `gemini-2.5-flash-lite` for Google per `TUNING.md` §1 default.
- [ ] **Persona payment rigidity** — recurring across Runs 7, 8. See
      TUNING_LOG.
- [ ] **Scoring rule strictness** — partial-deal scoring mode for cases
      where most issues converge but one deadlocks.
- [ ] **Promise dedup via reconciliation** — reconciler built, live-validated
      in Run 7 for dedup; other paths still pending (see above).
- [ ] **Persona drift over 8+ rounds** — all runs were 4 rounds; longer
      games may show drift.
- [ ] **Provider-native structured output** — OpenAI `response_format:
      json_schema` would give token-level schema compliance. Requires toolkit
      `llm_client` parameter passthrough.
- [ ] **Level 1 modularization** (DEVPLAN roadmap) — pull entity-type
      content out of Python into `config/`. 1–2 hours. Unlocks
      domain-portability for the divorce scenario and beyond.
- [ ] **Persona endgame over-anchoring (Run 7)** — static `ENDGAME:`
      paragraph leaks into early rounds. Decide whether to soften, move to
      dynamic-only, or accept.
- [ ] **Conversation model Stage 2+** — `ARCH_conversation_model.md` Stage 2a
      is item #3 above. Stage 2b and Stage 3 stay deferred.

---

## Change History

| Date | What Changed | Why |
|------|--------------|-----|
| 2026-05-30 | Initial NEXT_STEPS.md created from operator/Devmate discussion | Capture six directions + Run 8 review TODOs in one place |
| 2026-05-30 | Section #1 (Google API) collapsed to 1-paragraph closure note + 4 follow-up TODOs. Canonical content moved to `TUNING.md` §1 and §6 changelog. Items now absorbed elsewhere: "document thinking-token budgeting" (→ TUNING.md §1), "decide default Google model for tuning" (→ TUNING.md §1, flash-lite). Per-role real-game model decision reworded as still-open. | Operator: "prefer next steps file to shrink as we progress — document in existing framework, then remove or shrink the entry." |
| 2026-05-30 | Promoted retry-with-backoff to active work (was "low priority"). Split off two cross-provider concerns into new top-level sections: #6 Pricing & accounting audit (operator: OpenAI estimates significantly overstated), #7 Per-role model strategy with guardrails experiments (operator: strong guardrails could allow lighter models). §1 keeps only the two Google-specific items actively being worked. | Operator clarified that per-role model decision and pricing audit aren't Google-specific footnotes — each deserves its own dedicated effort. |
| 2026-05-30 | Shipped `complete_with_retry` in `toolkit.llm_client` (exponential backoff, `retry-after` honoring, 15 new tests). Wired through `CostAccountant.complete` and Diplomat's `ToolkitLLMAdapter`. Safety-filter empty-response audit closed: existing `LLMResponseError` already catches them; retry now handles transient cases. §1 closure block updated; suggested sequencing item #1 (retry+empty audit) collapsed. | Operator: "no reason to postpone, let's build retry with backoff... let's test empty response too." |
| 2026-05-30 | Re-sequenced to prioritize cleanup before exploration: (1) tooling debt, (2) live Telegram re-smoke, (3) coaching test loop, (4) OpenRouter+Run 9, (5) divorce scenario, (6) Stage 2a, (7) Clankmates. Old #1 (OpenRouter+Run 9) demoted to #4. | Operator: "I think I want to sequence next steps as follows: tooling debt, live TG resmoke, coaching test on pi, then the rest" |
| 2026-05-30 | Added §8 (Reverse scenario builder) and §9 (Voice/style templates). §8 fills the gap that's been implicit in every scenario-design conversation: we need outcome-shape → scenario generation so skill becomes visible. §9 is fun-priority. | Operator: "we should have a scenario builder that runs the analyzer in reverse... also tune voice from templates like Kissinger, Gen Alpha, Iliad, воровская феня." |
| 2026-05-30 | Marked tooling-debt items #1 (LoggingLLMClient SCORE/RECON) and #2 (scenario compiler BATNA hardcode) as RESOLVED in the Backlog section with closure references to DEVLOG entries. Surfaced four open design questions on BATNA approach (default value, presets, per-faction asymmetric, force-clamp). | Operator: "don't forget to update the docs after a step is done" |
| 2026-05-30 | Marked tooling-debt item #3 (dated OpenAI model pricing) RESOLVED. All three tooling-debt items closed; suggested sequencing collapsed by removing #1 (Tooling debt). New sequence: (1) live TG re-smoke, (2) coaching test, (3) OpenRouter+Run 9, (4) divorce scenario, (5) Stage 2a, (6) Clankmates. | Operator provided current OpenAI pricing; audit revealed 41.6× overall overestimate from date-suffix lookup miss. |
| 2026-05-30 | Added `SMOKE_RUNBOOK.md` at project root — step-by-step Pi smoke procedure mapping every Phase 18+19 change to a verification step. Surfaced two not-blocking gaps: reconciler not wired in production `main.py`, endgame markers don't fire in production. Both tracked as remaining items under `Live Telegram re-smoke` Backlog section. | Operator: "Live Telegram re-smoke on Pi — verify deployment readiness" |
| 2026-05-31 | Live TG re-smoke **PAUSED mid-§3** after operator-side verifications + bot startup confirmed. Documented: bot-to-bot Telegram impossibility (faction-traffic source needed for §3.1–§3.9), service.sh broken via `incus exec` (tmux pattern is the working invocation), 2 real fixes shipped (toolkit max_completion_tokens, test fake signature drift), 2 smoke setup edits pending revert/commit decision, 3 tooling-debt items surfaced. Resume steps documented in the "Live Telegram re-smoke — PAUSED" section. | Operator: "can we document this (in the next steps?) and pause? I need a break" |
| 2026-05-31 | Live TG re-smoke **CLOSED for coaching scope** (reframed). Telegram is the operator coaching surface; production game traffic comes via Clankmates or equivalent, not Telegram. Unverified extraction/debounce/reconciler/round-flow items moved to new sequencing item #2 "Layer 3 integration tests for Phase 18 paths". Sequencing re-numbered: (1) commit 2 real fixes from smoke, (2) Layer 3 Phase 18 tests, (3) coaching test loop on Pi, (4) OpenRouter+Run 9, (5) divorce scenario, (6) Stage 2a, (7) Clankmates. PAUSED section replaced with compact CLOSED summary. SMOKE_RUNBOOK reframed as coaching/review smoke and shrunk to ~155 lines. | Operator: "oh you know what, this is not how the game will work; we were looking into clankmates exactly for this reason. I assume we tested the coaching part which is the one that meant to stay on tg, and we'll be testing the actual game environment in a different step. we should still test message parsing and extraction somehow." |
| 2026-05-31 | Added `ASSESSMENT.md` at project root — conceptual framework for what "negotiating well" means (calculation-vs-negotiation tension), ten dimensions of skill, four scoring lenses with formulas (BATNA-relative ✓, Pareto efficiency NOT YET, skill-premium NOT YET, process signatures partial), scenario design properties, three workstream blocks A/B/C. Tagged every section heading + sequencing item in this file with `[A]`/`[B]`/`[C]`/`[X]`. Added pointer in PROJECT.md Success Criteria and DEVPLAN.md cold-start gotchas. | Operator: "let's document this as rationale and potential avenues for exploration - different scores for how well they negotiate, and we should integrate this all into a game setup and analysis/assessment part of work... not sure where best to put this... these are separate but interlocking blocks of work - agent memory and processing arch piece, prompt tuning piece, game creation and scoring piece" |
