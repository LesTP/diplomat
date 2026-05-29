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

### Run 7 — Three-Party Coalition (Scored)
Pending — blocked by network share outage during first attempt.

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
| 7 | Coalition (scored) | TBD | TBD | TBD | Scoring + game mode + broader extraction |

**Total estimated spend across all runs: ~$2.50**

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
- [ ] Promise dedup via reconciliation — built but untested with live LLM
- [ ] Fulfillment detection via reconciliation — built but untested
- [ ] Inconsistency detection via reconciliation — built but untested
- [ ] Promise state transitions (pending -> kept/broken) — reconciler should handle this
- [ ] Persona drift over 8+ rounds not yet tested
- [ ] Real game deployment (Telegram, operator coaching, non-self-play)
- [ ] Provider-native structured output (OpenAI `response_format: json_schema`)
- [ ] Level 1 modularization: config-driven prompts and examples (see DEVPLAN roadmap)
