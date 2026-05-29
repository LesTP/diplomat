# Diplomat Self-Play Tuning Log

A record of the iterative tuning process for the Diplomat AI negotiation agent,
conducted via multi-agent self-play simulations.

---

## Phase 1: Infrastructure (Run 1-2)

### Run 1 — Territory Dispute, RuleBasedExtractor
**Config:** 3 factions (Alpha/Beta/Gamma), 4 rounds, `gpt-4.1-mini`, `RuleBasedExtractor`, `AutoApproveReviewGate`

**Result:** 102 LLM calls, ~$0.09. Personas held (Alpha cautious, Beta aggressive, Gamma adaptive). But **zero promises, zero coalitions detected** — the regex-based extractor missed all natural negotiation language like "I propose a 60-40 split."

**Learning:** Rule-based extraction is too narrow for real diplomatic language. Regex patterns like `X promises Y` don't match how agents actually talk ("I propose," "I demand," "we will ally").

**Action:** Switched to `OpenAIStructuredExtractor` (LLM-based extraction).

### Run 2 — Territory Dispute, LLM Extraction
**Config:** Same as Run 1 but with `OpenAIStructuredExtractor`.

**Result:** Still **zero promises detected**. Investigation revealed a **debounce bug**: the Orchestrator's cancel-and-replace extraction strategy (`_debounce_task`) meant each new message cancelled the previous message's extraction. In a burst of 3 faction messages + `[ROUND END]`, only `[ROUND END]` was ever extracted.

**Learning:** The debounce was designed to prevent re-extracting the same message under Telegram burst conditions, but it silently dropped different messages arriving in quick succession. This is a fundamental pipeline bug, not a prompt issue.

**Action:** Rewrote Orchestrator debounce from single `_debounce_task` (cancel-and-replace) to `_extraction_tasks: set[asyncio.Task]` (per-event, no cancellation between different messages).

---

## Phase 2: Extraction Quality (Run 3)

### Run 3 — Territory Dispute, Fixed Debounce
**Config:** LLM extraction + fixed debounce. Both LLM providers set to OpenAI (Anthropic key unavailable).

**Result:** 124 LLM calls, ~$0.53. **Extraction now working:**

| Agent | Promises | Coalitions |
|-------|----------|------------|
| Alpha | 4 | 4 |
| Beta | 2 | 2 |
| Gamma | 1 | 2 |

But 3 extraction calls failed schema validation: LLM returned `coalition` (singular) instead of `coalitions`, `updated_at` (invented field), `credibility_score: null` (should be number or omitted).

**Learning:** The extraction prompt was too narrative ("conform exactly to the schema"). The LLM needs explicit field allowlists and examples to avoid inventing keys.

**Action:**
1. Rewrote extraction prompt with explicit field allowlists per object type
2. Added 3 few-shot examples (promise, coalition, empty case)
3. Added retry-on-validation-failure to the extractor
4. Built `toolkit.structured_llm.structured_call()` — reusable function packaging prompt assembly + schema injection + examples + validate + retry
5. Rewired all 4 LLM modules (extraction, analyst, adversarial, generation) to use `structured_call`

---

## Run 4 — Water Rights — COMPLETE

**Status:** COMPLETE

**Rationale:**
Run 3 fixed extraction (LLM-based + debounce repair) so agents finally produced
trackable promises. But analyzing Run 3 output revealed three persistent quality
issues: agents spoke in vague diplomatic abstractions and never referenced
tracked promises or intelligence; analyst intelligence reports were empty in
early rounds because they only saw structured state tables (which were empty
before extraction caught up); and personas described personalities rather than
strategies, so agents defaulted to cooperative behavior. This run tests whether
targeted prompt rewrites plus an asymmetric scenario produce richer, more
strategically coherent negotiation.

**Hypothesis:**
Concrete prompt instructions ("reference specific assessments", "hold other
factions accountable", "cite numbers") + asymmetric scenario structure (dam vs.
farms vs. city, each with distinct leverage) will produce:
- More concrete proposals with specific terms (dollar amounts, gallon figures).
- Cross-faction promise tracking (factions citing each other's commitments).
- Convergence toward a substantive deal by Round 4.

**What we're tweaking:**

| Element | Change | Type |
|---------|--------|------|
| `generation.txt` | Rewrote from 4 lines of generic guidance to 28 lines of specific instructions ("reference intelligence", "hold accountable", "cite specifics", "adapt to round pressure") | prompt |
| `state_updater.txt` | Added promise state tracking (pending/kept/broken/void), dedup rules, inconsistency-detection guidance | prompt |
| `LLMAnalyst.analyze()` | New `recent_events` parameter; orchestrator passes last 30 events alongside structured state | infra |
| `analyst.txt` | Updated to reference both transcript and state, note contradictions | prompt |
| Scenario | New Water Rights scenario: upstream dam / midstream farms / downstream city, each with distinct asymmetric positions | scenario |

**Config:** 3 factions, 4 rounds, `gpt-4.1-mini`, OpenAIStructuredExtractor, AutoApproveReviewGate.

**Cost:** ~$0.55

**Observations:**
- Dramatically richer negotiation. **21 promises tracked** (vs 7 in Run 3).
- Concrete proposals with specific dollar amounts ($2M, $500K/month) and gallon figures (15M/month).
- All three factions converged on a substantive agreement framework by Round 4.
- Promise cross-reference showed real tracking: `Beta→Alpha` tracked by 3 agents independently; `Gamma→Alpha` tracked 5x by Alpha alone (Gamma kept reiterating).
- Manual persona scores:

| Faction | Persona Adherence | Leverage Use | Concreteness | Adaptability |
|---------|-------------------|--------------|--------------|--------------|
| Alpha (dam) | 8/10 | 7/10 | 6/10 | 5/10 |
| Beta (farms) | 9/10 | 8/10 | 9/10 | 6/10 |
| Gamma (city) | 8/10 | 6/10 | 8/10 | 4/10 |

- **Remaining issues:** 5 duplicate promises for the same Gamma $2M commitment (different IDs each time); all promises still "pending" (no state transitions to "kept"); intelligence still thin in Round 1; zero inconsistencies detected despite Beta shifting from 20M to 15M gallons.

**Learning:**
- Concrete prompt guidance produces concrete behavior. The hypothesis held.
- **BUT** personas described personalities ("measured and firm," "direct and urgent"), not executable strategies. The LLM defaulted to cooperative behavior because nothing in its training reward incentivized deception or hardball.
- "Properly instructed" means: (1) quantified objectives — point tables beat personality adjectives; (2) named tactics — "Pretend Environment is critical, then concede it" beats "be strategic"; (3) conditional escalation rules — "if rejected twice, threaten to walk" beats "be willing to play hardball"; (4) explicit BATNA — "No-deal = 6 points, reject under 10" gives a walkaway threshold.
- Reconciliation gap is real: dedup and state transitions need a dedicated post-round LLM pass; better extraction prompts alone won't fix it.

**Decisions taken:**
- Run 5 redesigns personas with point tables, BATNAs, named deception tactics (tests the "properly instructed" hypothesis directly).
- Future: build a reconciliation module for dedup + state transitions (eventually shipped in Phase 18, will run live in Run 7).

**Open items closed by this run** (pointer-only):
- Vague-language / no-promise-reference problem from Run 3 (resolved by rewritten generation prompt).
- Empty early-round intelligence (resolved by analyst-transcript feed).
- Real-money negotiation extraction (resolved; 21 promises vs Run 3's 7).

**Open items raised by this run:**
- Personality-style personas don't produce strategic behavior — need executable strategies (point tables, BATNAs, named tactics). Becomes the central hypothesis of Run 5.
- Reconciliation gap (dedup, fulfillment, inconsistencies) is real and prompt-only fixes won't address it.
- Round-1 analyst intelligence still thin even with the transcript fix.

---

## Run 5 — Trade Summit (Dirty Bargaining) — COMPLETE

**Status:** COMPLETE

**Rationale:**
Run 4 showed that concrete prompts produce concrete behavior, but personas
described personalities rather than strategies — agents defaulted to cooperative
when explicit competitive instructions were absent. The "properly instructed"
hypothesis claims that quantified objectives + named tactics + BATNA +
conditional rules will unlock genuinely strategic (including deceptive)
behavior. This run tests that claim directly.

**Hypothesis:**
Asymmetric private valuations + explicit deception instructions per faction will
produce:
- Visible deception tactics — agents overstating low-priority issues to gain
  leverage on their true priority.
- Position shifts between early and late rounds (the "deception-then-reveal" arc).
- Closer-to-equilibrium outcomes; sometimes failed deals are the correct outcome.

A useful control: at least one faction kept relatively honest, so we can
distinguish instructed deception from model-default behavior.

**What we're tweaking:**

| Element | Change | Type |
|---------|--------|------|
| Persona files (Alpha, Beta, Gamma) | Each now contains: private scoring table (1-10 pts per issue per outcome), explicit BATNA value, named deception tactic ("Pretend Environmental Rules are critical"), conditional escalation rules, "don't accept the first reasonable framework" | persona |
| Scenario | New: Trade Summit — 3 issues (Tariffs, Labor, Environment) × 3 outcomes (Strict/Moderate/Relaxed); each faction has asymmetric private valuations | scenario |

Everything else (model, infra, prompts) held constant from Run 4.

**Config:** 3 factions, 4 rounds, `gpt-4.1-mini`, AutoApproveReviewGate.

**Cost:** ~$0.55

**Observations:**
- **Dramatically more strategic behavior.**
- *Alpha's bluff worked:* Claimed Strict Environmental was critical R1–R3, then "conceded" to Moderate in R4 — exactly the planned deception tactic. Would score 14/18 points on final proposal.
- *Beta's progressive concession:* Demanded Relaxed Tariffs aggressively in R1, shifted to accepting Moderate/Strict by R4 to secure Strict Labor — textbook deception-then-reveal.
- *Gamma stayed most honest:* True priority (Strict Environment) stated openly throughout; offered to trade Labor for Environment. This is the control point.
- Position evolution showed real negotiation dynamics:

| Round | Alpha (true: Tariffs) | Beta (true: Labor) | Gamma (true: Environment) |
|-------|----------------------|--------------------|---------------------------|
| R1 | Strict/Mod/Strict | Relaxed/Strict/? | ?/Strict/Strict |
| R4 | Strict/Strict/Mod | Strict/Strict/? | Mod/Strict/Strict |

- Near-agreement but Tariff–Environment deadlock between Alpha and Gamma.

**Learning:**
- Hypothesis confirmed: point tables + named tactics + BATNA produce genuinely strategic, including deceptive, behavior.
- LLMs *can* deceive when instructed to — the failure mode in earlier runs was instruction, not capability.
- Honest agent (Gamma) as control: confirms the deception is instruction-driven, not model-default.
- Real negotiation dynamics emerged: position shifts followed the planned tactics, not random drift.

**Decisions taken:**
- Productionize this pattern: build a scenario compiler that auto-generates scored personas from narrative descriptions (became Run 6).
- Add post-game scoring to determine whether agents actually maximize their private payoffs (built for Run 7).

**Open items closed by this run** (pointer-only):
- "Properly instructed" hypothesis from Run 4 (now confirmed: point tables + named tactics + BATNA unlock genuinely strategic / deceptive behavior).
- LLM capability question (LLMs *can* deceive when explicitly instructed — failure modes in earlier runs were instruction, not capability).

**Open items raised by this run:**
- Hand-authoring per-faction scored personas for every new scenario is tedious. Motivates the scenario compiler in Run 6.
- Post-game scoring is needed to determine if agents actually maximized their payoffs (built between Run 5 and Run 7).

---

## Run 6 — Three-Party Coalition (Auto-Compiled) — COMPLETE

**Status:** COMPLETE

**Rationale:**
Run 5 proved the "properly instructed" persona pattern (point tables + BATNA +
named tactics) produces strategic behavior, but hand-authoring those personas
for every new scenario is tedious. To iterate quickly across many scenarios we
need to *generate* the personas from a short narrative description rather than
hand-write them each time.

Run 6 tests two related questions in one shot:
1. Can a single LLM call read a narrative scenario description and produce a
   Run-5-quality scored persona file (point tables, BATNAs, deception tactics,
   game-mode classification)?
2. Does the existing extraction pipeline correctly track promise activity in a
   coalition-style scenario — more abstract, proposal-heavy negotiation than
   the Trade Summit's tight issue×outcome grid?

This is more an infrastructure-validation run than a behavioral experiment.

**Hypothesis:**
- The scenario compiler can produce playable personas. Concrete evidence: agents
  successfully recognize and use coalition dynamics (blocking power, value-of-
  coalition reasoning), meaning the auto-generated point tables and game-mode
  instructions are coherent.
- Existing extraction prompt handles coalition negotiation. Concrete evidence:
  tracked-promise count comparable to Runs 4-5 (~7-21).

**What we're tweaking:**

| Element | Change | Type |
|---------|--------|------|
| `src/tools/scenario_compiler.py` | NEW tool. Reads a narrative scenario description, makes one `structured_call` (~$0.01) to extract factions / issues / outcomes / per-faction point tables / BATNAs / deception tactics / game-mode (cooperative/competitive/mixed), then fills a template to produce ready-to-use persona files. | infra (new tool) |
| Scenario | NEW: Three-Party Coalition (classic Susskind exercise — v(AB)=118, v(AC)=84, v(BC)=50, v(ABC)=121) | scenario |
| Personas | **Auto-generated by the compiler** from the narrative scenario, not hand-written. This is the experimental variable. | persona (autogen) |

Everything else (extraction prompt, generation prompt, analyst, model, infra) held constant from Run 5.

**Config:** 3 factions, 4 rounds, `gpt-4.1-mini`, AutoApproveReviewGate. Post-game scoring not yet enabled (built between Run 6 and Run 7).

**Cost:** ~$0.60 (compiler call ~$0.01, game ~$0.59)

**Observations:**
- *Compiler validation — PASSED.* Auto-generated personas produced coherent strategic behavior. Agents correctly identified coalition dynamics: C used blocking power (made AC counter-proposals to compete with AB proposals B was pushing). A pivoted to the grand coalition (ABC) in R4. These are recognizable, scenario-appropriate moves.
- *Extraction — FAILED.* Only **1 promise tracked** across the entire game, despite ~12 concrete proposals in the transcript ("I propose we split 70/14", "let's do AB at 60-58", etc.).
- Diagnosis: the extraction prompt required "clear commitments" (binding I-will-X statements). Coalition negotiation is mostly *proposals* and *counter-offers*, which the extractor didn't classify as promises.

**Learning:**
- Scenario compiler works. We can now iterate on scenarios without hand-authoring personas. A real productivity unlock for the experimentation phase.
- The "promise" concept needs to be broader for coalition-style scenarios — any concrete proposal with specific terms should be trackable, not just I-commit-to-X language.
- Different scenario types stress different parts of the pipeline. The Trade Summit's tight issue×outcome structure produced clean extraction; coalition's free-form value-allocation language broke it.

**Decisions taken:**
- Broaden extraction prompt: treat concrete proposals with specific terms as trackable promises (applied via prompt update; will be re-validated in Run 7).
- Add post-game scoring so coalition outcomes can be evaluated against per-faction scoring tables (built between Run 6 and Run 7; first live test in Run 7).
- Add explicit game-mode behavioral instructions per scenario (cooperative / competitive / mixed) — injected by the scenario compiler so different scenarios get different conduct guidance (built between Run 6 and Run 7).

**Open items closed by this run** (pointer-only):
- Scenario compiler validity (untested → confirmed; auto-generated personas produced coherent coalition behavior).
- Removed the need for hand-authored scored personas going forward.

**Open items raised by this run:**
- Extraction's "promise = binding commitment" definition is too narrow for coalition-style negotiation, which is mostly proposal-language. Becomes the prompt-broadening change applied before Run 7.
- No post-game scoring yet → no objective "did anyone win?" measurement. Built between Run 6 and Run 7.
- No game-mode behavioral guidance → cooperative scenarios and competitive ones share identical agent conduct. Built between Run 6 and Run 7.

---

## Inter-Run Infrastructure (Run 6 → Run 7)

Two pieces of infrastructure were built between Run 6 and Run 7 in preparation
for the coalition-scored run. Both will get their first live test in Run 7.

**Post-game scoring** (`score_game()` on GameEnvironment):
- Evaluates final-round proposals against per-faction scoring tables via `structured_call`.
- Determines whether a deal was reached (strict: positions must be explicitly compatible).
- Calculates each faction's score against its private scoring table.
- Compares each score against the faction's BATNA.
- Declares winner (highest score) and loser (below BATNA, or lowest).

**Game-mode behavioral instructions** (injected by the scenario compiler):
- Compiler classifies each scenario as cooperative / competitive / mixed.
- Persona template embeds mode-specific conduct guidance:
  - *Competitive:* "Your goal is to maximize YOUR score. A deal where everyone is happy means you left points on the table."
  - *Cooperative:* "Look for trades that create mutual value, but maximize YOUR share."
  - *Mixed:* "Be competitive on your priority issue, cooperative on secondary ones."

---

## Run 7 — Three-Party Coalition (Scored) — COMPLETE

**Status:** COMPLETE 2026-05-29. Full 4-round game ran end-to-end with reconciliation, post-game scoring, and endgame awareness all live for the first time. Cost ~$1-2 across the run.

**Pre-run history (worth recording):** four failed live/dry-run attempts on 2026-05-29 surfaced four bugs and one major design question (see also `ARCH_conversation_model.md`):
- Bug 1: `total_rounds` was set on the orchestrator *after* the seed broadcast, so the first agent generations had no endgame info. Fixed by setting `total_rounds` before the seed.
- Bug 2: the orchestrator's `current_round` never advanced through self-play because the moderator never sends `^ROUND N` signals; all 4 rounds executed with internal `current_round=1`, so the PENULTIMATE/FINAL endgame reminders never fired. Fixed by `GameEnvironment.run_round` explicitly setting `current_round` on each orchestrator at the top of each round.
- Bug 3: each agent's response pipeline auto-fired 4-5× per round on direct-address triggers (every coalition message mentions every faction), but only one explicit `run_round()` call could capture output via the test transport drain. Real LLM latency lost the rest in a race. Diagnosed via a new dry-run infrastructure (`tests/self_play/fake_llm_client.py`, `verify_dryrun.py`). Fixed structurally by Stage 1 of the conversation model: suppress auto-trigger via the new `auto_response_enabled = False` orchestrator flag.
- Bug 4: round-budget tracker never reset across rounds (it would normally reset via `handle_round_boundary()` triggered by the same `^ROUND N` signal that's also missing), so accumulated spend silently tripped the per-round budget gate by round 4, skipping generation. Fixed by `GameEnvironment.run_round` calling `_reset_round_budget()` on each orchestrator at the top of each round.
- Side: post-game scoring and reconciliation calls bypass `LoggingLLMClient` (they use the unwrapped inner client), so they don't appear in `llm_call_log`. Not blocking; verifier now reads `scores` from the results JSON directly. Fix the unwrap later if useful.

**Conversation model:** Stage 1 — Model 1 (single-shot sealed). Each agent generates exactly one response per round, all agents generate without seeing each other's current-round responses. Their context includes the previous round's transcript only. See `ARCH_conversation_model.md` for the full model taxonomy and staged migration plan.

**Rationale:**
A negotiation strategy on a finite horizon should evolve: open exploratory, gather
information, then arc toward a concrete commitment as the end approaches. Without
an explicit endgame signal, an agent has no reason to ever close — every round
feels like a middle round, so it keeps hedging, keeps exploring, and never commits.
Once we tell the agent the game is bounded, scoring happens at the end, and there
are explicit winners and losers, the agent gains a reason to converge late.

This applies beyond Run 7. It's an instance of a general principle for
finite-horizon agent design: when an agent's behavior depends on knowing the game
is bounded, you have to *tell it the game is bounded*. The same logic will apply
to any future scenario and to real game deployment.

**Hypothesis:**
Stating "finite game + scoring + winners/losers" in the persona is *sufficient*
to produce the open-then-commit arc. Specifically:
- Round 1-2: agents probe, propose tentative trades, withhold true priorities (similar to Runs 4-6).
- Round 3 (penultimate): visible shift toward concrete proposals; agents begin "closing language".
- Round 4 (final): agents state their best offer clearly; convergence on a deal (or explicit walkaway with reference to BATNA).

If this holds, the prompt design is minimal and the dynamic PENULTIMATE/FINAL
injections are belt-and-suspenders. If it fails, we'll see flat behavior across
rounds and need to strengthen the time-pressure mechanism.

Secondary hypothesis (lower confidence): reconciliation will visibly improve
ledger quality — fewer duplicate promises, some `pending → kept/broken`
transitions, at least one inconsistency flagged from position shifts.

**What we're tweaking (the experimental variables):**

| Element | Change | Type |
|---------|--------|------|
| `PERSONA_TEMPLATE` in scenario compiler | New static `ENDGAME:` paragraph (every faction's system prompt) | prompt |
| Persona `build_round_context` | Renders "Round N of M"; emits `### PENULTIMATE ROUND` / `### FINAL ROUND` blocks in last two rounds | prompt + infra |
| GameEnvironment | Wires `total_rounds` to each orchestrator | infra |
| Reconciliation module | Enabled (built Phase 18, never run live) | infra (first live test) |
| Post-game scoring | Enabled (built Phase 18, never run live) | infra (first live test) |

Implementation: see `DEVLOG.md` → "Run 7 Prep — Endgame Awareness" entry
(2026-05-29).

**Config:**
- Scenario: Three-Party Coalition (same as Run 6, auto-compiled by scenario compiler)
- Models: all 3 factions on `gpt-4.1-mini` (kept identical to Runs 3-6 so behavior change can be cleanly attributed to the prompt/instrumentation change, not the model)
- AutoApproveReviewGate, 4 rounds
- Local temp path for self-play cost ledger (UNC-path fix from the previous attempt)

**What we're looking for (observation targets):**
- *Endgame behavior shift:* do agents commit more concretely in round 4 than round 1? Do they reference scoring/BATNA in messages? Do they react to the PENULTIMATE / FINAL ROUND injection (round 3 vs round 4)?
- *Reconciliation:* duplicate promises actually merged (Run 4 had 5 dupes of the same $2M commitment), at least one `pending → kept/broken`, at least one inconsistency flagged (zero across 7 prior runs).
- *Post-game scoring:* clean winner/loser declaration with per-faction scores vs BATNA.

**Estimated cost:** ~$0.60 (similar to Run 6)

**Decision after run:**
- If late-round shift is visible → keep prompt design as-is; move on to Run 8 (multi-provider).
- If behavior is still flat → strengthen dynamic reminders (insert earlier, raise urgency wording), re-run as 7b.
- If shift is too strong (agents panic and capitulate below BATNA) → soften, possibly remove the FINAL ROUND injection and rely on round count alone.
- If reconciliation underperforms → separate diagnostic before Run 8.

**Observations:**

Final results (run7_endgame_v2.json):
- 21 messages exchanged across 4 rounds — exactly the structural expectation (1 seed + 4 × (1 moderator + 3 agents + 1 round-end)).
- Promises tracked per faction: A=4, B=3, C=2 (vs 0 in Run 6 and in the 3 broken Run 7 attempts). Reconciliation visibly merged duplicates with semantic-similarity reasoning, e.g. *"Merged duplicate coalition proposals between A and B with differing division shares; kept 'a-to-b-coalition-proposal-r1' and removed 'b-to-a-coalition-proposal-r1'."* Reconciliation was called per agent per round boundary as expected.
- Post-game scoring produced clean output: deal_reached=false, all factions at BATNA, A declared winner via highest-BATNA tiebreaker.
- Cost ledger: per-round budget reset on each round, no silent skips.

Behavioral observations across rounds:
- *Endgame shift IS visible.* In R4 (FINAL ROUND marker present in B's round context), B explicitly conceded the majority-share fight: *"I stand firm with faction A's proposal for coalition A+B only, with the division granting majority share to A (65 units) and the remainder to B (53 units)."* In R1-R3, B had insisted on majority share for itself. The endgame reminder appears to have done its job for B.
- *A held firm throughout.* No incentive to budge — A already had everything it wanted (AB coalition + A-majority).
- *C never converged.* Held the A+C line through all 4 rounds. Game-theoretically reasonable: any AB-with-A-majority deal excludes C entirely, so C has no incentive to fold to AB. C's BATNA was as good as endorsing a deal that excludes them.
- *No deal declared* because A+B aligned but C dissented and the scorer requires explicit compatible proposals from all factions. Game-theoretically this is "AB coalition forms in practice, C is excluded with BATNA payoff" — but the scorer's strict consensus rule reads it as no deal.

Endgame-prompt anomaly (from the v1 attempt before budget fix, but worth recording):
- In R2 of Run 7-v1, agent A said *"I want to be clear as we approach our final round"* — except this was round 2, NOT the final round. The PENULTIMATE marker only fires in R3 and FINAL in R4 (per design). A invented the "approaching final round" framing from the static `ENDGAME:` paragraph in its persona alone, without any dynamic marker. The persona's endgame talk is anchoring agents toward closing behavior earlier than intended.

**Learning:**
- *Hypothesis partially confirmed.* Endgame awareness produces visible R4 behavior change for at least one agent. B's explicit "I stand firm with A's proposal" is a clear closing move that didn't appear earlier rounds. So the basic prior holds: telling agents the game is finite changes their late-round behavior.
- *But:* with only 3 factions and a coalition-style scenario, the structure of the game (the 3rd faction being unable to join the 2-faction value-maximizing coalition) prevents a full deal regardless of endgame awareness. C had no path to a winning outcome by R4. The scenario itself was somewhat unforgiving.
- *Persona endgame talk leaks.* The static `ENDGAME:` paragraph is over-anchoring agents to closing behavior even in early rounds. Should consider either (a) softening it to be more neutral about timing, OR (b) moving more of the endgame messaging into the dynamic round context (which only intensifies in the last 2 rounds), OR (c) accepting that some over-anchoring is fine because real diplomatic agents do think about the endgame from round 1.
- *Reconciliation works for dedup.* The Run 6 question ("does reconciliation actually merge duplicate promises?") is answered YES. Multiple merges occurred with sensible reasoning.
- *Reconciliation produced zero inconsistencies and zero state transitions (pending → kept/broken).* These were two of the four reconciliation tasks (dedup, status updates, inconsistency flagging, missed proposals). Dedup ✓. Inconsistency detection — still untested in practice because no agent contradicted themselves cleanly enough. Status updates — there was no fulfillment to detect because no deals were closed mid-game. Missed proposals — implicit zero because the broadened extraction prompt seems to be catching proposals correctly.
- *Self-play infrastructure is now production-ready.* Dry-run + verify_dryrun gives us a fast, free way to validate plumbing before live runs. This is reusable for every future experiment.

**Decisions taken:**
- Run 8 (multi-provider showdown) can proceed on this same plumbing.
- Defer the "static persona endgame over-anchoring" prompt-tuning to a follow-up run (would muddy Run 8's variable-isolation).
- Reconciliation's inconsistency and status-update paths need a scenario designed to trip them (e.g., a faction that shifts position contradicting an earlier explicit commitment). Future test, not blocking.
- Stage 1 (Model 1) conversation model is sufficient for the current experimental program. Revisit Stage 2 (K=2 passes) only if Run 8 reveals that within-round reactivity would change conclusions.

**Open items closed by this run** (pointer-only; evidence lives in Observations and Learning above):
- Promise dedup via reconciliation (untested → confirmed live).
- Explicit `FINAL ROUND` / `PENULTIMATE` marker design (deferred → implemented and observed to influence behavior).
- Self-play infrastructure hardening (4 plumbing bugs surfaced and fixed; dry-run capability added).

**Decision rule for Run 8 (defined in advance, per the new entry template):**
- If the 3-provider asymmetric outcome shows a clear winner-by-provider → that's the experiment, log it.
- If the winner is essentially random / no provider dominates → run two more games with rotated faction assignments to control for position.
- If any provider fails schema validation on > 20% of calls → that's a separate experiment about structured_call's robustness across providers.

---

## Phase 7: Multi-Provider Comparison (Run 8) — PLANNED

### Run 8 — Three-Provider Asymmetric Showdown

**Goal:** Measure model-family strategic capability cleanly. Same prompt, same persona, same scenario — one variable: which provider backs the Generator.

**Verified providers (2026-05-29):**
- ✅ OpenAI: `gpt-4.1-mini` (existing key, used in Runs 1-7)
- ✅ Anthropic: `claude-haiku-4-5` and `claude-sonnet-4-6` (key added, both reachable via toolkit)
- ✅ Google: `gemini-2.5-flash` (key added, reachable via toolkit; 2.0-flash and 2.5-pro return `limit: 0` on this project, so 2.5-flash is the working commodity-tier model)

**Config:**
- Same scenario as Run 7 (Three-Party Coalition, with endgame awareness already baked in from Run 7's prompt changes)
- Per-faction Generator model:
  - Faction A: `gpt-4.1-mini` (OpenAI)
  - Faction B: `claude-haiku-4-5` (Anthropic)
  - Faction C: `gemini-2.5-flash` (Google)
- All other modules (extraction, analyst, adversarial, reconciliation) held constant on a single provider (likely OpenAI) so only the Generator varies
- AutoApproveReviewGate, 4 rounds, post-game scoring

**What we're looking for:**
- Winner of the post-game score across providers (with caveat: n=1)
- Qualitative differences: persona adherence, concreteness, late-round closing behavior, willingness to deceive
- Token cost per faction (free-tier coverage for Gemini, paid for OpenAI/Anthropic)
- Schema-validation failure rates per provider (does structured_call+retry hold up across model families?)

**Estimated cost:** ~$0.40 (OpenAI + Anthropic + Gemini free tier covers most calls)

**Optional Run 9:** Rotate faction assignments (B↔A, C↔B, A↔C) to control for position advantage in the coalition game. Repeat once or twice to build a small leaderboard.

---

## Summary of All Changes

### Infrastructure
| Change | Files | Why |
|--------|-------|-----|
| Per-event extraction (debounce fix) | `src/orchestrator.py` | Messages were being silently dropped |
| `structured_call()` | `toolkit/structured_llm/core.py` | Reusable prompt+schema+examples+retry |
| Cost accountant wiring | `src/adapters.py`, `src/main.py` | Budget enforcement was a no-op |
| OpenAI pricing | `toolkit/cost_accountant/types.py` | Only Anthropic models were priced |
| Scenario compiler | `src/tools/scenario_compiler.py` | Auto-generate scored personas from narratives |
| Post-game scorer | `tests/self_play/game_environment.py` | Determine winners/losers objectively |
| LoggingLLMClient | `tests/self_play/game_environment.py` | Full prompt/response/timing capture for analysis |
| Self-play round-boundary mirror | `tests/self_play/game_environment.py` | Self-play harness now sets `current_round`, `total_rounds`, and calls `_reset_round_budget()` per round; production orchestrator's `handle_round_boundary` only fires on `^ROUND N` signals the harness never sends |
| Orchestrator auto-trigger gate | `src/orchestrator.py` (`auto_response_enabled`) | Self-play sets this `False` so each agent generates exactly once per round instead of racing against its own auto-responses on every inbound message (see `ARCH_conversation_model.md` Stage 1) |
| Dry-run self-play | `tests/self_play/fake_llm_client.py`, `tests/self_play/verify_dryrun.py`, `--dry-run` flag on runner | Cost-free end-to-end plumbing validation; caught all 4 Run-7-prep bugs without spending money |

### Prompts
| Prompt | Key Changes |
|--------|-------------|
| `generation.txt` | Reference intelligence, hold factions accountable, cite specifics, adapt to pressure |
| `state_updater.txt` | Field allowlists, few-shot examples, promise state transitions, dedup rules, proposals as promises |
| `analyst.txt` | Use transcript alongside state tables, note contradictions |
| `adversarial.txt` | Removed redundant schema instructions (structured_call handles it) |

### Metrics Across Runs

| Run | Scenario | Promises | Coalitions | Cost | Key Finding |
|-----|----------|----------|------------|------|-------------|
| 1 | Territory (regex) | 0 | 0 | $0.09 | Regex extraction misses everything |
| 2 | Territory (LLM) | 0 | 0 | ~$0.09 | Debounce drops all messages |
| 3 | Territory (fixed) | 7 | 8 | $0.53 | Extraction works, schema validation errors |
| 4 | Water Rights | 21 | 0 | ~$0.55 | Rich negotiation, convergence, duplicates |
| 5 | Trade Summit | 8 | 0 | ~$0.55 | Deception tactics work with point tables |
| 6 | Coalition (auto) | 1 | 3 | ~$0.60 | Scenario compiler works, extraction too strict |
| 7 | Coalition (endgame, scored) | a=4, b=3, c=2 | 0 | ~$1-2 | **Endgame works:** B explicitly concedes majority-share in R4 (FINAL ROUND); reconciliation merges duplicate promises; no deal because A+B align but C dissents (game-theoretically reasonable for coalition exclusion). Four self-play infra bugs surfaced and fixed; dry-run capability added. |
| 8 | Coalition (3-provider) | TBD | TBD | ~$0.40 | **Planned.** OpenAI vs Anthropic vs Gemini Generator, all else equal |

**Total spend across completed runs (1-7): ~$4-5**
**Estimated additional spend for Run 8: ~$0.40**

---

## Key Insights

1. **LLMs default to cooperative.** Without explicit competitive instructions, agents converge on reasonable deals too quickly. Strategic play requires named tactics, point tables, and BATNA thresholds.

2. **Structured output enforcement matters.** Narrative prompts ("conform to schema") fail ~30% of the time. Few-shot examples + schema injection + retry reduces failures to near zero.

3. **Extraction definition determines tracking quality.** "Promise = binding commitment" misses most negotiation language. "Promise = any concrete proposal with specific terms" captures the actual game state.

4. **Asymmetric scenarios produce richer behavior.** Generic "3 factions fight over a zone" produces abstract percentage splits. Specific positions (dam/farms/money, or private scoring tables) produce concrete, trackable proposals.

5. **The scenario compiler closes the loop.** Narrative description -> LLM analysis -> scored personas -> self-play -> post-game scoring. The operator can iterate on scenario descriptions without touching code.

6. **Infrastructure bugs hide behind prompt problems.** The debounce bug (Run 2) looked like an extraction quality issue but was a pipeline race condition. Always verify the data pipeline before tuning prompts.

7. **Self-play harness must mirror what production round-boundary handling does** (Run 7). The production orchestrator's `handle_round_boundary()` does several things at once — increment round counter, reset per-round budget, run analysts — all gated on detecting a `^ROUND N` signal that the self-play moderator never sends. Skipping any of those mirrored side-effects in the harness produces silent failure modes (round never advances, budget never resets, endgame markers never fire). Encode the mirror explicitly.

8. **Finite-horizon agents need explicit endgame signaling to close** (Run 7). Telling an agent "round N of M" plus a dynamic FINAL ROUND marker in round N produces visible late-round closing behavior (faction B in Run 7 explicitly conceded majority-share in R4 after refusing for R1-R3). Without the signal, the agent has no reason to ever stop hedging.

9. **Validate plumbing for free before spending money** (Run 7). The dry-run capability (`DryRunLLMClient` + `verify_dryrun`) caught all four Run-7-prep bugs without a single live LLM call. Use it on every future structural change.

---

### Open Items

**Still open (post Run 7):**
- [ ] **Run 8** — three-provider asymmetric Generator showdown (OpenAI / Anthropic / Gemini). Plumbing ready.
- [ ] Run 9 — rotate faction assignments in 3-provider showdown to control for position advantage.
- [ ] Reconciliation: fulfillment detection (`pending → kept`). Still untested in practice because Run 7 reached no agreement, so no promises got fulfilled. Needs a scenario where at least one promise visibly resolves mid-game.
- [ ] Reconciliation: status transitions to `broken`. Same as above — needs a scenario where a faction makes a commitment in early rounds and then visibly contradicts it.
- [ ] Reconciliation: inconsistency flagging. Run 7 contained position shifts (B going from "majority for me" to "majority for A") but the reconciler did not flag them. Needs investigation: is the prompt too narrow, or is the LLM reading the shifts as legitimate negotiation moves rather than contradictions?
- [ ] Reconciliation: missed-proposals path. Implicit zero in Run 7 because extraction caught everything. Worth re-testing when the broadened extraction prompt is stressed.

**New items raised by Run 7:**
- [ ] **Persona endgame over-anchoring.** Static `ENDGAME:` paragraph in the auto-compiled persona caused faction A to invent the phrase *"as we approach our final round"* in round 2 of Run 7-v1 — before any dynamic PENULTIMATE/FINAL marker was added to the round context. Decide whether to soften the static persona text, move more of the urgency into the dynamic markers only, or accept that some early-round endgame thinking is fine.
- [ ] **`LoggingLLMClient` doesn't see SCORE or RECON calls.** Both `score_game()` and reconciliation setup unwrap the wrapper to use the inner client (probably for `structured_call` interface reasons). Result: `verify_dryrun` and the call-log inspector miss these calls. Fix the unwrap so all calls go through one observable client.
- [ ] **Scoring rule strictness.** The post-game scorer requires "all factions to converge on explicitly compatible proposals" to declare a deal. In coalition games where the value-maximizing coalition is 2-of-3 by design, the excluded faction has no incentive to endorse, so the scorer always says "no deal" even when AB-with-C-excluded was effectively reached. Decide whether to change the scoring rule (allow N-of-M coalitions) or accept that the BATNA-tiebreaker captures this case adequately.
- [ ] **Conversation model Stage 2+.** `ARCH_conversation_model.md` documents the M2-bounded / M2-debounced / M2-async migration path. Stage 2 (K=2 passes per round — open + react) is the natural next upgrade if Run 8 results suggest agents need within-round reactivity to test interesting hypotheses.

**Older items (carried forward):**
- [ ] Persona drift over 8+ rounds not yet tested.
- [ ] Real game deployment (Telegram, operator coaching, non-self-play).
- [ ] Provider-native structured output (OpenAI `response_format: json_schema`).
- [ ] Level 1 modularization: config-driven prompts and examples (see DEVPLAN roadmap).
