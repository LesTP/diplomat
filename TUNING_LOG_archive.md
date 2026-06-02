# Diplomat Self-Play Tuning Log — Archive

Archived runs from `TUNING_LOG.md`. Newest archives at the bottom; the live
log keeps only the current experimental arc and the runs immediately
preceding it.

Active log: `TUNING_LOG.md`.

---

## Archived 2026-06-02 — Runs 1-6 (infrastructure, extraction quality, scenario compiler)

These six runs cover the first arc of the project: getting promise extraction
working at all (Runs 1-3), producing strategic / deceptive behavior from
properly-instructed personas (Runs 4-5), and validating the scenario compiler
on a coalition-style game (Run 6). All findings are summarized in the active
log's "Summary of All Changes" Metrics table and in `ASSESSMENT.md`. Detail
preserved below for replay / regression purposes.

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
