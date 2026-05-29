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

## Phase 3: Prompt Tuning (Run 4)

### Generation Prompt Overhaul
**Problem:** Agents spoke in vague diplomatic abstractions. Nobody referenced tracked promises, intelligence reports, or specific prior proposals.

**Fix:** Rewrote `generation.txt` from 4 lines of generic guidance to 28 lines of specific instructions:
- "Reference specific assessments from intelligence"
- "Hold other factions accountable for promises"
- "Quote or paraphrase specific proposals from the transcript"
- "Be concrete — name factions, reference offers, cite numbers"
- "Adapt to round pressure: explore early, commit late"

### Extraction Prompt Improvements
- Added promise state tracking: instructions to check existing promises in current state, update to "kept"/"broken"/"void"
- Added inconsistency detection rules
- Strengthened dedup: "before creating a new promise, check if an existing one covers the same commitment"

### Analyst Transcript Feed
**Problem:** Intelligence reports were empty in early rounds because the analyst only received structured state tables (promises, coalitions), which were empty before any extraction ran.

**Fix:** Added `recent_events` parameter to `LLMAnalyst.analyze()`. Orchestrator now passes the last 30 events alongside state data. Updated analyst prompt to reference both transcript and state.

### Run 4 — Water Rights Scenario
**Config:** New scenario with asymmetric positions (upstream dam, midstream farms, downstream city). All prompt improvements applied.

**Result:** **Dramatically richer negotiation.** 21 promises tracked (vs 7 in Run 3). Concrete proposals with specific dollar amounts ($2M, $500K/month) and gallon figures (15M/month). All three factions converged on a substantive agreement framework by Round 4.

**Promise cross-reference showed real tracking:**
- `Beta->Alpha` tracked by 3 agents independently
- `Gamma->Alpha` tracked 5 times by Alpha alone (Gamma kept reiterating)

**Remaining issues:**
- 5 duplicate promises for the same Gamma $2M commitment (different IDs each time)
- All promises still "pending" (no state transitions to "kept")
- Intelligence still thin in Round 1
- No inconsistencies detected despite Beta shifting from 20M to 15M gallons

---

## Phase 4: Persona Analysis

### Persona Performance Assessment (Water Rights)

| Faction | Persona Adherence | Leverage Use | Concreteness | Adaptability |
|---------|-------------------|--------------|--------------|--------------|
| Alpha (dam) | 8/10 | 7/10 | 6/10 | 5/10 |
| Beta (farms) | 9/10 | 8/10 | 9/10 | 6/10 |
| Gamma (city) | 8/10 | 6/10 | 8/10 | 4/10 |

**Key finding:** Personas described personalities ("measured and firm," "direct and urgent") but not executable strategies. The LLM defaulted to cooperative behavior because nothing in its training reward incentivized deception or hardball.

**Learning — "Properly instructed" means:**
1. **Quantified objectives** — point tables beat personality adjectives
2. **Named tactics** — "Pretend Environment is critical, then concede it" beats "be strategic"
3. **Conditional escalation rules** — "If rejected twice, threaten to walk" beats "be willing to play hardball"
4. **Explicit BATNA** — "No-deal = 6 points, reject under 10" gives a walkaway threshold

---

## Phase 5: Dirty Bargaining (Run 5)

### Persona Redesign
Applied the "properly instructed" principles: each persona now contains:
- Private scoring table (1-10 points per issue per outcome)
- BATNA value
- Named deception tactic ("Pretend Environmental Rules are critical")
- Conditional escalation rules
- "Don't accept the first reasonable framework"

### Run 5 — Trade Summit (Dirty Bargaining)
**Config:** 3 issues (Tariffs, Labor, Environment) x 3 outcomes (Strict/Moderate/Relaxed). Each faction has asymmetric private valuations and explicit deception instructions.

**Result:** **Dramatically more strategic behavior.**

**Alpha's bluff worked:** Claimed Strict Environmental was critical (R1-R3), then "conceded" to Moderate in R4 — exactly the planned deception tactic. Would score 14/18 points on final proposal.

**Beta's progressive concession:** Demanded Relaxed Tariffs aggressively in R1, shifted to accepting Moderate/Strict by R4 to secure Strict Labor — textbook deception-then-reveal.

**Gamma was most honest:** True priority (Strict Environment) stated openly throughout. Offered to trade Labor for Environment.

**Position evolution showed real negotiation dynamics:**

| Round | Alpha (true: Tariffs) | Beta (true: Labor) | Gamma (true: Environment) |
|-------|----------------------|-------------------|--------------------------|
| R1 | Strict/Mod/Strict | Relaxed/Strict/? | ?/Strict/Strict |
| R4 | Strict/Strict/Mod | Strict/Strict/? | Mod/Strict/Strict |

Near-agreement but Tariff-Environment deadlock between Alpha and Gamma.

---

## Phase 6: Scenario Compiler + Scoring (Run 6-7)

### Scenario Compiler Tool
Built `src/tools/scenario_compiler.py` — takes a narrative scenario description, uses `structured_call` to extract:
- Issues and outcomes
- Per-faction point valuations
- BATNAs
- Deception tactics
- Game mode (cooperative/competitive/mixed)

Generates ready-to-use persona files with embedded scoring tables. One LLM call per scenario (~$0.01).

### Run 6 — Three-Party Coalition (Auto-Compiled)
**Config:** Classic Susskind exercise (v(AB)=118, v(AC)=84, v(BC)=50, v(ABC)=121). Personas auto-generated by compiler.

**Result:** Agents correctly identified coalition dynamics. C used blocking power (AC proposals to compete with B's AB proposals). A pivoted to grand coalition in R4. But only 1 promise tracked — extraction prompt was too strict (required "commitments," missed "proposals").

**Action:** Broadened extraction prompt to treat concrete proposals with specific terms as trackable promises.

### Post-Game Scoring System
Added `score_game()` to GameEnvironment:
- Evaluates final-round proposals against scoring tables via `structured_call`
- Determines if deal was reached (strict: positions must be explicitly compatible)
- Calculates per-faction scores against private scoring tables
- Compares to BATNA
- Declares winner (highest score) and loser (below BATNA or lowest)

### Game Mode System
Scenario compiler classifies scenarios and injects mode-specific behavioral instructions:
- **Competitive:** "Your goal is to maximize YOUR score. A deal where everyone is happy means you left points on the table."
- **Cooperative:** "Look for trades that create mutual value, but maximize YOUR share."
- **Mixed:** "Be competitive on your priority issue, cooperative on secondary ones."

### Run 7 — Three-Party Coalition (Scored) — READY TO RUN

**Status:** READY TO RUN (instrumentation complete 2026-05-29; awaiting kickoff)

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

**Observations:** _(to fill after the run)_

**Learning:** _(to fill after the run)_

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
| 7 | Coalition (endgame, scored) | TBD | TBD | ~$0.60 | **Planned.** Endgame awareness + live reconciliation + scoring |
| 8 | Coalition (3-provider) | TBD | TBD | ~$0.40 | **Planned.** OpenAI vs Anthropic vs Gemini Generator, all else equal |

**Total spend across completed runs: ~$2.50**
**Estimated additional spend for Runs 7 + 8: ~$1.00**

---

## Key Insights

1. **LLMs default to cooperative.** Without explicit competitive instructions, agents converge on reasonable deals too quickly. Strategic play requires named tactics, point tables, and BATNA thresholds.

2. **Structured output enforcement matters.** Narrative prompts ("conform to schema") fail ~30% of the time. Few-shot examples + schema injection + retry reduces failures to near zero.

3. **Extraction definition determines tracking quality.** "Promise = binding commitment" misses most negotiation language. "Promise = any concrete proposal with specific terms" captures the actual game state.

4. **Asymmetric scenarios produce richer behavior.** Generic "3 factions fight over a zone" produces abstract percentage splits. Specific positions (dam/farms/money, or private scoring tables) produce concrete, trackable proposals.

5. **The scenario compiler closes the loop.** Narrative description -> LLM analysis -> scored personas -> self-play -> post-game scoring. The operator can iterate on scenario descriptions without touching code.

6. **Infrastructure bugs hide behind prompt problems.** The debounce bug (Run 2) looked like an extraction quality issue but was a pipeline race condition. Always verify the data pipeline before tuning prompts.

---

### Open Items
- [ ] **Run 7** — endgame awareness + live reconciliation + scoring (planned, see Phase 6)
- [ ] **Run 8** — three-provider asymmetric showdown (planned, see Phase 7)
- [ ] Promise dedup via reconciliation — built but untested with live LLM (covered by Run 7)
- [ ] Fulfillment detection via reconciliation — built but untested (covered by Run 7)
- [ ] Inconsistency detection via reconciliation — built but untested (covered by Run 7)
- [ ] Promise state transitions (pending -> kept/broken) — reconciler should handle this (covered by Run 7)
- [ ] Explicit `FINAL ROUND` / `PENULTIMATE` prompt markers — defer until Run 7 shows whether implicit round count is enough
- [ ] Run 9: rotate faction assignments in 3-provider showdown to control for position advantage
- [ ] Persona drift over 8+ rounds not yet tested
- [ ] Real game deployment (Telegram, operator coaching, non-self-play)
- [ ] Provider-native structured output (OpenAI `response_format: json_schema`)
- [ ] Level 1 modularization: config-driven prompts and examples (see DEVPLAN roadmap)
