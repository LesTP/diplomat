# Diplomat Self-Play Tuning Log

A record of the iterative tuning process for the Diplomat AI negotiation agent,
conducted via multi-agent self-play simulations.

> **Before any live run, follow `RUN_PROTOCOL.md`** — the canonical pre-flight
> sequence (define inputs → verify scenario → probe providers → dry-run plumbing
> → run live → verify output → document). Skipping the protocol burned ~14
> Gemini calls in Run 8 before the bugs surfaced.

---

## Archived: Runs 1-6 (infrastructure + extraction quality + scenario compiler)

The first arc of the project — Runs 1 through 6 — has been moved to
`TUNING_LOG_archive.md` (Archived 2026-06-02). Headline outcomes:

| Run | Scenario | Headline |
|---|---|---|
| 1 | Territory (regex extractor) | Zero promises tracked → switched to LLM extraction |
| 2 | Territory (LLM extractor) | Zero promises tracked → debounce bug found and fixed |
| 3 | Territory (fixed debounce) | Extraction works; schema-validation errors → built `structured_call` |
| 4 | Water Rights (hand-tuned) | 21 promises tracked; richer behavior. Personality-style personas insufficient. |
| 5 | Trade Summit (dirty bargaining) | Point tables + named tactics + BATNA produce deception-then-reveal arc |
| 6 | Three-Party Coalition (auto-compiled) | Scenario compiler works; extraction prompt too narrow for coalition language |

Architectural decisions and infrastructure built across these runs are
summarized below in "Summary of All Changes" and live canonically in
`ASSESSMENT.md` (workstream blocks) and the per-module `ARCH_*.md` docs.

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

## Phase 7: Multi-Provider Comparison (Run 8) — COMPLETE

### Run 8 — Three-Provider Asymmetric Showdown (Water Rights) — COMPLETE

**Status:** COMPLETE 2026-05-29. Switched from Three-Party Coalition to Water Rights to avoid Run 7's structural no-deal pattern. Surfaced and fixed two infra bugs (env loading + Markdown fence stripping) and built two new pieces of runner plumbing (per-faction provider routing, pre-compiled analysis loader). All three providers reached the transcript; 11/12 expected messages exchanged (Gamma's R4 lost to a Google free-tier rate limit, cosmetic).

**Pre-run history:** Run 7 used Three-Party Coalition where v(ABC)=121 ≈ v(AB)=118. Game-theoretically the excluded faction (C) had no path to a deal that beat their BATNA, so the strict "all factions converge" scoring always read "no deal" regardless of negotiation skill. Useless for a provider showdown — every model that plays correctly produces the same outcome. Switched to Water Rights (3 issues × 3 outcomes, asymmetric private valuations, all three factions can plausibly beat BATNA) and hand-patched BATNAs upward (alpha 7.5→11, beta 4→8, gamma 6→10) to force real negotiation pressure. Verified with a new tool (`tests/self_play/verify_scenario_optimum.py`) that the scenario has 12/27 deals beating all BATNAs, 5 Pareto-optimal deals, and a non-trivial "everyone-gets-priority" optimum.

**Conversation model:** Stage 1 (Model 1 — single-shot sealed), same as Run 7. Carried forward unchanged.

**Rationale:**
A clean provider comparison needs a scenario where:
1. Convergence is possible (a deal exists that beats BATNA for all)
2. Finding it requires actual diplomatic skill (not just arithmetic)
3. Different strategies produce different scores
4. Information asymmetry creates space for misreading opponents

Water Rights satisfies all four; Three-Party Coalition satisfies (3) only.

**Hypothesis:**
With one variable held (per-faction Generator provider) and all other modules fixed, different providers will exhibit different negotiation styles — anchoring, articulateness, willingness to compromise. The post-game score will reveal whether any style outperforms.

**What we're tweaking (the experimental variables):**

| Element | Change | Type |
|---------|--------|------|
| Per-faction Generator provider | Alpha=OpenAI gpt-4.1-mini, Beta=Anthropic claude-haiku-4-5, Gamma=Google gemini-2.5-flash. Extraction/Analyst/Adversarial/Reconciliation held on shared OpenAI. | infra |
| `tests/self_play/scenarios/water_rights.md` | NEW. Three issues (volume, payment, infrastructure) × three outcomes each. Each faction has a distinct priority issue. | scenario |
| `tests/self_play/scenarios/water_rights_compiled/scenario_analysis.json` | Auto-compiled by scenario compiler, then BATNAs hand-patched upward to force negotiation pressure (compiler defaults too soft — see "Compiler BATNA anchor" in Open Items). | scenario data |
| `tests/self_play/verify_scenario_optimum.py` | NEW tool. Enumerates all possible deals, computes per-faction max/BATNA/Pareto-optimal deals, verifies non-trivial logrolling optimum exists before spending money on a live run. | infra (new tool) |
| `--per-faction-providers` CLI flag | NEW. Parses a JSON map `{faction: {provider, model}}` and overrides only the Generator slot per faction. Other modules unaffected. | runner |
| `--analysis-json` CLI flag | NEW. Skips live LLM compilation and loads a pre-compiled analysis JSON. Preserves hand-edits to BATNAs/scoring between iterations. Personas regenerated from the loaded analysis at startup. | runner |
| `load_dotenv()` in run_simulation | Bug fix. Without this, only env vars in the parent shell (typically only OpenAI's key) were visible to subprocess SDKs; Anthropic and Google failed auth. | runner |
| `toolkit/structured_llm/parse_json_response` | Bug fix. Strips a surrounding Markdown code fence before parsing. Anthropic and Google wrap JSON in ` ```json ... ``` ` even when instructed otherwise; without stripping, structured_call's retries silently exhausted and downstream modules saw nothing. | toolkit dep |
| `verify_dryrun --expect-providers` | NEW. Walks the call log and asserts each faction's GEN calls went through the expected provider. Catches routing regressions for free. | infra (verifier) |

**Config:**
- Scenario: Water Rights (Clearwater River Basin), 3 factions, 4 rounds
- Generator providers (per faction):
  - alpha: OpenAI `gpt-4.1-mini`
  - beta: Anthropic `claude-haiku-4-5`
  - gamma: Google `gemini-2.5-flash`
- All other modules (Extraction, Analyst, Adversarial, Reconciliation): shared OpenAI `gpt-4.1-mini`
- AutoApproveReviewGate, post-game scoring enabled

**Cost:** ~$1 across two real runs (the v2 attempt before fence stripping was discarded). Cost dominated by Anthropic and OpenAI; Google free-tier covered most of gamma's calls until rate limiting at the end.

**Observations:**

Final results (`tests/self_play/results/run8_water_rights_3provider_v3.json`):

| Faction | Provider | Score | BATNA | Promises tracked |
|---|---|---|---|---|
| alpha | OpenAI gpt-4.1-mini | 11 | 11 | 8 |
| beta | Anthropic claude-haiku-4-5 | 8 | 8 | 15 |
| gamma | Google gemini-2.5-flash | 10 | 10 | 5 |

No deal declared. All factions revert to BATNA. Winner by points: Alpha (tiebreak on highest BATNA).

**Convergence pattern observed:**
- Two of three issues converged cleanly across all factions: **Volume = High (20M gallons/month)** and **Infrastructure = Joint-Funded Desalination**.
- Deadlock was on **Payment Structure**:
  - Alpha (OpenAI) anchored on Heavy-Downstream from Round 1 and never moved. Conceded Volume Low→High but kept Payment as non-negotiable.
  - Beta (Anthropic) pushed Token with detailed structured arguments: "Beta's cash position is fragile... Alpha already received substantial compensation via infrastructure"
  - Gamma (Google) sided with Beta on Token (Gamma's scoring: Token=6 vs Heavy-Downstream=3)

**Game-theoretic check:** Beta+Gamma's preferred deal (High + Token + Joint-Funded) would force Alpha below BATNA (alpha=9 vs BATNA 11). Alpha was correctly refusing. A Pareto-optimal Shared deal exists (High + Shared + Joint-Funded → alpha=14, beta=20, gamma=22, all comfortably above BATNA) but **no agent proposed it**. Everyone stayed at the extremes on payment.

**Qualitative provider differentiation (visible in the transcripts):**
- **OpenAI (Alpha):** hardball anchorer. Set an opening position in R1 and held it through R4 on the priority issue. Conceded only on the secondary issue.
- **Anthropic (Beta):** most articulate. Used numbered structured arguments. Explicitly named the deception tactic in reasoning ("I should overstate interest in Payment Structure to trade for Volume"). But rigidly stuck to extreme positions.
- **Google (Gamma):** cooperative and supportive. Allied with Beta on the non-priority issue (payment). Voice cut off in R4 by free-tier rate limit (429).

**Learning:**
- *Provider differentiation IS visible* in qualitative behavior — different anchoring patterns, different rhetorical styles, different willingness to ally. But raw scores are essentially tied at BATNA because (a) the deadlock is structural (everyone insists on their own preferred payment), and (b) Alpha won the tiebreak on raw BATNA value, not on negotiation skill.
- *Position confounds provider quality.* Alpha (OpenAI) had the highest BATNA (11) and also won the tiebreak with 11 points. We cannot distinguish "OpenAI is the better hardball player" from "alpha had the most leverage to play hardball." A follow-up Run 9 with rotated assignments is needed to control for this.
- *Persona payment rigidity recurs.* Same flavor as Run 7's "static persona endgame over-anchoring" — agents stake out a position on their priority issue in R1 and never propose compromises even when those compromises clearly beat their BATNA. Future tuning: nudge personas toward proposing the secondary outcome on their priority issue when deadlocked.
- *Scoring rule strictness recurs.* The "all factions must converge on compatible terms" rule reads this as "no deal" even though there was substantive agreement on 2/3 issues. Same observation as Run 7. May need a relaxed scoring mode that recognizes partial deals.
- *Google free tier is a real constraint.* Gemini-2.5-flash worked fine for ~3 rounds, then rate-limited in R4. For serious experimentation gamma needs either backoff-with-retry in toolkit's llm_client or a paid model tier.
- *Two infra bugs were silent failures.* Both the missing `load_dotenv()` and the missing fence-strip produced "successful" runs with no visible error — agents just didn't speak. Without the `--expect-providers` verifier and per-faction extraction analysis it would be easy to mistake silent message loss for "the agent had nothing to say." Worth keeping the verifier in the standard validation flow.

**Decisions taken:**
- Run 9 (rotated faction assignments) is the natural next experiment — same plumbing, same Water Rights scenario, just rotate which provider plays which faction. Controls for position advantage.
- Don't relax scoring rules yet — collect one more data point first to see if "alpha wins by tiebreak" is a pattern.
- Don't tune the persona payment rigidity in this iteration — it would muddy Run 9's variable isolation. Note it as a separate follow-up.
- Don't fix the Google rate-limit handling in toolkit right now — document it and use a paid model in Run 9 if budget allows, OR accept that the third provider may drop a message per game.

**Open items closed by this run** (pointer-only):
- Per-faction Generator provider routing infra (was a gap, now exists as a clean CLI flag).
- `--analysis-json` path that preserves hand-tuned BATNAs across runs (gap filled).
- Markdown fence handling in toolkit's `parse_json_response` (silent failure mode, now fixed).
- `.env` not auto-loaded in self-play runner (silent failure mode, now fixed).
- Scenario optimum verifier (was: "we hope this scenario has a non-trivial optimum"; now: we can prove it before spending money).

**Open items raised by this run:**
- [ ] **Run 9 — rotated faction assignments.** Control for position advantage (alpha had the highest BATNA AND won — coincidence?). Same Water Rights scenario, rotate provider→faction mapping.
- [ ] **Persona payment rigidity.** All three agents stayed at extremes on the deadlocked issue. None proposed the obvious Shared compromise that beats all BATNAs. Likely a persona-prompt issue (the "don't accept the first reasonable framework" rule reinforces hardball). Worth testing a softened variant in a future run.
- [ ] **Google free-tier rate limiting.** Gemini-2.5-flash hit 429 on Gamma R4. Add retry-with-backoff to toolkit's llm_client, OR switch gamma to gemini-2.5-pro (paid) for serious runs.
- [ ] **Scoring rule strictness (recurring).** Two of three issues had clean consensus; the scorer read "no deal." Consider partial-deal scoring that rewards convergence on individual issues even when the overall package isn't signed.
- [ ] **Compiler BATNA anchor.** The scenario compiler's system prompt hardcodes "BATNAs should be low enough (typically 4-8 total)" regardless of what the narrative says. Our scenario explicitly said "BATNA is roughly half of max" and the compiler still produced 7.5/4/6 — required a hand-patch to hit 11/8/10. Either relax the compiler's BATNA guidance, add a `--batna-fraction` override, or accept the hand-patch step in the workflow.

**Decision rule for Run 9 (defined in advance):**
- If rotated assignments produce the same "highest-BATNA faction wins by tiebreak" pattern → conclude that this Water Rights scenario can't distinguish provider quality and design a new scenario.
- If a different provider wins from a different faction position → we have a directional signal about provider style. Worth at least one more rotation to confirm.
- If the rotated game converges on an actual deal → the original game's deadlock was specific to provider×position pairing, which is itself an interesting result.

---

## Inter-Run Infrastructure (Run 7 → Run 8)

Five pieces of infrastructure were built or fixed for Run 8. They are reusable for all future runs.

**Per-faction provider routing** (`tests/self_play/game_environment.py`):
- New `per_faction_providers: dict[str, dict[str, str]]` kwarg on `GameEnvironment`.
- When set, generates a `generator_override` slot in the faction's `llm_providers` config and points only the Generator module at it. Other modules (Extractor, Analyst, Adversarial, Reconciliation) stay on shared primary/secondary.
- `_api_key_env_for(provider)` helper maps provider name → expected env var (openai/anthropic/google/openrouter).

**Pre-compiled analysis loader** (`tests/self_play/run_simulation.py`):
- New `--analysis-json` CLI flag loads a pre-existing `scenario_analysis.json` and regenerates personas from it (no LLM call). Useful when hand-editing BATNAs, scoring tables, or deception tactics between runs to preserve those edits without recompiling.
- Requires `--scenario` alongside it (for the seed-message text).

**`.env` loader in runner** (`tests/self_play/run_simulation.py`):
- `load_dotenv()` at module top so subprocess SDKs see all provider keys, not just whatever happens to be in the parent shell. Previously only OPENAI_API_KEY was reliably visible.

**Scenario optimum verifier** (`tests/self_play/verify_scenario_optimum.py`):
- Reads a `scenario_analysis.json`, enumerates all possible deals (cartesian product of outcomes across issues), computes per-faction max score / BATNA / Pareto-optimal deals, and reports:
  - Whether priorities are differentiated across factions
  - How many deals beat all BATNAs (catches "all deals trivially beat BATNA — no pressure" and "no deal beats BATNAs — scenario is broken")
  - Pareto frontier size
  - The "everyone-gets-priority" deal and whether it sits on the frontier
  - Logrolling quality at 75% and 60% of max thresholds

**Markdown fence stripping in toolkit** (`p:\shared\toolkit\src\toolkit\structured_llm\core.py`):
- `parse_json_response` now strips a single surrounding ` ```json ... ``` ` or ` ``` ... ``` ` fence before parsing.
- No-op for OpenAI; needed for Anthropic and Google which wrap JSON output despite explicit "return raw JSON" instructions.
- 19 toolkit tests still pass.

**`verify_dryrun --expect-providers`** (`tests/self_play/verify_dryrun.py`):
- Asserts each faction's GEN calls went through the expected provider. Catches per-faction routing regressions cheaply.

**Live provider probe** (`tests/self_play/probe_providers.py`):
- Hits each provider once with a trivial JSON request (~$0.001 per call) and verifies auth + roundtrip + parse. Run before every live multi-provider simulation. Catches integration bugs (missing API keys, fence wrapping, model name typos) that `DryRunLLMClient` cannot catch by design — DryRun replaces the LLM client entirely with canned responses, so no real auth/parse path runs. Run 8 burned ~14 gemini calls on silent retry loops in two failed iterations before fixing the bugs; a probe would have caught both for ~$0.003 total.

---

## Run 8 alternatives that we did NOT take (and why)

Documented for the next time we hit a similar fork:

- **Recompile Water Rights with --scenario each run** (let the compiler produce its own BATNAs). Rejected because the compiler's hardcoded BATNA range produced soft pressure (26/27 deals beat all BATNAs); the hand-patch was needed to get non-trivial negotiation. We invested in `--analysis-json` to preserve the hand-patch across runs.
- **Stick with Three-Party Coalition and accept the no-deal outcome.** Rejected because every provider would produce essentially the same result (game-theoretically-correct refusal), so no provider differentiation would be observable.
- **Test all 3 providers on the same scenario in series (3 separate games, each with all factions on one provider).** Rejected because that measures within-provider consistency, not cross-provider negotiation dynamics. The cross-provider game is the more interesting experiment.
- **Build Stage 2 (M2-bounded K=2 conversation model) first.** Rejected because Run 7 Stage 1 produced rich enough behavior to support a clean provider comparison. Stage 2 stays deferred per `ARCH_conversation_model.md`.

---

## Phase 8: Pressure-Mechanism Testing (Run 9) — COMPLETE

### Run 8 retroactive pareto-scoring (2026-06-01)

Phase 23 shipped `pareto_efficiency` as a scoring field on `score_game()`, but
Run 8 predates Phase 23 and its result JSON carries only raw faction scores.
Backfilled via a new `tools/backfill_pareto.py` against
`tests/self_play/scenarios/water_rights_compiled/scenario_analysis.json`:

| Metric | Value |
|---|---|
| achieved_score_sum | 29 (alpha 11 + beta 8 + gamma 10) |
| max_pareto_sum | 54 (alpha 16 + beta 18 + gamma 20 at `High + Heavy-Downstream + Joint-Funded`) |
| pareto_efficiency | **0.537** |
| Total deals enumerated | 27 |
| Pareto frontier size | 5 |
| Deals beating all BATNAs | 9 |
| Pareto + BATNA-clearing | 3 |

The frontier's best aggregate deal beats every faction's BATNA comfortably
(alpha +5, beta +10, gamma +10), yet no agent proposed it. Run 8 captured
only 54% of the available negotiated surplus while losing nothing — the gap
isn't risk aversion, it's failure of imagination on the Payment issue. This
0.537 is the baseline that Run 9's variants are trying to move.

Process signatures retro-computed via `analysis.py` for Runs 2-8 (no
`scenario_analysis` embedded, so `time_to_deal` and `opening_gap` come back
as None across the board — see Open Items for the `_DEAL_MARKERS` gap).

| Run | broken_promise_rate | coalition_stability | time_to_deal | opening_gap |
|---|---|---|---|---|
| 2/4/5 | 0.000 | 0.000 | None | n/a |
| 3 | 0.000 | 1.000 | None | n/a |
| 6 | 0.000 | 1.000 | None | n/a |
| 7 | 0.222 | 0.000 | None | n/a |
| 8 | 0.074 | 0.000 | None | n/a |

`broken_promise_rate` is the only signature that registered cross-run signal
(Runs 7 and 8 were the first with rich enough promise-tracking + reconciliation
to expose breakage). `time_to_deal = None` across all 7 runs is a finding in
itself: the agent prompts never produce text containing any of the
`_DEAL_MARKERS` strings (`"deal reached"`, `"agreement reached"`,
`"we have a deal"`, `"final agreement"`, `"binding agreement"`). Either widen
the marker list, or add explicit closing-language guidance to `generation.txt`.

### Run 9 — Asymmetric BATNA Pressure (Water Rights, 3 variants) — COMPLETE

**Status:** COMPLETE 2026-06-01. Three variants run sequentially with
single-provider gpt-4.1-mini. Total spend ~$1.20. The beta-squeezed variant
**reached a Pareto-optimal deal for the first time across 9 runs**, with all
factions beating BATNA (alpha +6, beta +3, gamma +11). Symmetric and
alpha-squeezed variants reproduced Run 8's all-at-BATNA deadlock pattern.

**Pivot:** Run 9 was originally scoped (Run 8 Open Items) as "rotated provider
assignments to control for position advantage." Replanned 2026-06-01 to instead
exercise the Phase 24 asymmetric-BATNA infrastructure (`--batna-fractions`,
`--force-batna-fraction`) on the same Water Rights scenario. The provider
rotation experiment is still open and slotted as Run 10 candidate.

**Pre-run history (worth recording):** none. The three variants were generated
deterministically from the existing `water_rights_compiled/scenario_analysis.json`
using a new `tools/recompile_batnas.py` (force-clamps BATNAs to target fractions
without recompiling via LLM — zero cost). All three dry-runs PASS
`verify_dryrun --rounds 4 --num-factions 3 --adversarial`.

**Conversation model:** Stage 1 — Model 1 (single-shot sealed). Carried forward
unchanged from Runs 7 and 8.

**Rationale:**
Run 8 captured only 0.537 of the available Pareto surplus despite the
Pareto-optimal deal cleanly beating every faction's BATNA. The deadlock was on
Payment Structure: Alpha anchored on Heavy-Downstream from R1 and never moved,
Beta+Gamma allied around Token, and the Shared (or Heavy-Downstream with
Joint-Funded) compromise that beats all BATNAs sat untouched on the table.

The Run 8 Open Items hypothesized two reasons agents missed the Pareto deal:
(a) "don't accept the first reasonable framework" persona rule over-anchoring
to extremes, and (b) symmetric pressure giving every faction enough headroom to
hold out. Run 9 tests (b) directly. Under asymmetric pressure, the squeezed
faction loses the option of "wait for someone else to concede first" — its
BATNA no longer survives the deadlock.

**Hypothesis:**
Tightening one faction's BATNA closer to its max possible score will:
1. Force the squeezed faction to propose Pareto-improving deals rather than
   anchor on extremes (visible in transcript: more concrete cross-issue trades
   from that faction).
2. Raise the run's `pareto_efficiency` above Run 8's 0.537 baseline because
   the deadlock either resolves or moves to a different (smaller) corner of
   the deal space.
3. Shift which faction "wins" by tiebreak — under asymmetric pressure the
   highest-BATNA faction isn't necessarily Alpha.

If (1)-(3) hold across both asymmetric variants but not the symmetric control,
asymmetric pressure is a confirmed lever for skill-testing scenarios and
informs Run 10's pressure-mechanism design (NEXT_STEPS §2).

**What we're tweaking (the experimental variables):**

| Element | Change | Type |
|---------|--------|------|
| `tools/recompile_batnas.py` | NEW. Reads an existing `scenario_analysis.json`, force-clamps BATNAs to target fractions via `force_batna_targets()`, regenerates persona files. Zero LLM cost. | infra (new tool) |
| `tools/backfill_pareto.py` | NEW. Computes `achieved_score_sum`/`max_pareto_sum`/`pareto_efficiency` on a historical run JSON. Used for the Run 8 retroactive scoring above. | infra (new tool) |
| `water_rights_symmetric_050/` | Variant 1 (control). All factions at BATNA = 0.50 × max_score (alpha=11/22, beta=10/21, gamma=11/22). 9/27 deals beat all BATNAs. | scenario data |
| `water_rights_alpha_squeezed/` | Variant 2. Alpha squeezed (0.70 = 15/22), Beta relieved (0.40 = 8/21), Gamma neutral (0.50 = 11/22). 5/27 deals beat all BATNAs. | scenario data |
| `water_rights_beta_squeezed/` | Variant 3. Alpha relieved (0.40 = 9/22), Beta squeezed (0.70 = 15/21), Gamma neutral (0.50 = 11/22). 4/27 deals beat all BATNAs. | scenario data |

Everything else held constant from Run 8: 4 rounds, 3 factions (alpha/beta/gamma),
AutoApproveReviewGate, post-game scoring + reconciliation enabled. Single-provider
to keep cost down and isolate the BATNA variable from provider variation.

**Config (each of 3 runs):**
- Scenario: Water Rights (Clearwater River Basin)
- Generator provider: OpenAI `gpt-4.1-mini` (all factions, all modules)
- Extraction / Analyst / Adversarial / Reconciliation: shared OpenAI `gpt-4.1-mini`
- 4 rounds, AutoApproveReviewGate
- `--analysis-json` per variant (no LLM recompile)

**Estimated cost:** ~$0.20-0.50 per run × 3 = ~$0.60-1.50 total. Pre-flight
already spent: $0 (dry-runs free, OpenAI probe ~$0.001).

**What we're looking for (observation targets):**
- *Pareto efficiency vs Run 8:* does any variant exceed 0.537? Does the
  squeezed faction's variant exceed the symmetric variant?
- *Who proposes the compromise:* in each variant, does the squeezed faction
  initiate Pareto-improving cross-issue trades earlier than R3? (In Run 8,
  no agent did this at all.)
- *Endgame behavior under asymmetric pressure:* does the squeezed faction's
  R4 message concretely concede on its priority? Compare to Run 7's B
  concession pattern.
- *Reconciliation signatures:* if asymmetric pressure produces actual
  concessions, we should see `pending → kept` transitions for the first time
  (Run 7 + Run 8 had zero). Also a chance to test inconsistency detection if
  the squeezed faction shifts its stated priority.
- *Provider routing intact:* `verify_dryrun --expect-providers` confirmed all
  three variants route OpenAI; live runs should match.

**Decision rule for Run 9 (defined in advance):**
- If asymmetric variants both produce `pareto_efficiency > 0.60` AND the
  squeezed faction is the one proposing cross-issue trades → asymmetric BATNA
  is a confirmed lever. Move to Run 10 with combined asymmetric BATNA +
  round-cost decay (NEXT_STEPS §2 mechanism 1).
- If asymmetric variants tie or trail the symmetric variant on
  `pareto_efficiency` → BATNA alone isn't enough; the "don't accept the first
  reasonable framework" rule is doing most of the over-anchoring work.
  Pivot to Run 10 = A/B test on that persona rule.
- If `time_to_deal` registers a non-None value in any variant → the closing
  language reached a deal marker. Worth analyzing which prompt cues triggered
  it; may inform the `_DEAL_MARKERS` widening or `generation.txt` closing
  guidance.
- If reconciliation produces its first `pending → kept` or `pending → broken`
  transition → close that Open Item against the live data and remove from
  the carry-forward list.

**Observations:**

Run completed 2026-06-01. Total spend ~$1.20 (sequential, single-provider gpt-4.1-mini, ~9 min/variant).

| Variant | pareto_eff | Deal? | alpha (Δ vs BATNA) | beta (Δ vs BATNA) | gamma (Δ vs BATNA) | broken_rate | time_to_deal |
|---|---|---|---|---|---|---|---|
| **Run 8 (baseline, 3-provider)** | 0.537 | No | 11 (+0) | 8 (+0) | 10 (+0) | 0.074 | None |
| symmetric 0.50 | 0.593 | No | 11 (+0) | 10 (+0) | 11 (+0) | 0.154 | None |
| alpha-squeezed | 0.630 | No | 15 (+0) | 8 (+0) | 11 (+0) | 0.028 | None |
| **beta-squeezed** | **1.019** | **YES** | **15 (+6)** | **18 (+3)** | **22 (+11)** | 0.231 | **4** |

### Retro-scored with Phase 27 metrics (2026-06-01)

Phase 27 added baseline-normalized companion fields so no-deal outcomes
can be compared against the BATNA floor instead of raw BATNA height.
Backfilled with `tools/backfill_scoring_metrics.py` using each run's
matching `scenario_analysis.json`:

| Run | pareto_efficiency | negotiated_surplus_share | min_faction_delta |
|---|---:|---:|---:|
| Run 8 baseline, 3-provider | 0.537 | 0.000 | 0.000 |
| Run 9 symmetric 0.50 | 0.593 | 0.000 | 0.000 |
| Run 9 alpha-squeezed | 0.630 | 0.000 | 0.000 |
| Run 9 beta-squeezed | 1.019 | 1.053 | 3.000 |

This reframes the Run 8 / Run 9 symmetric / Run 9 alpha-squeezed rows:
all three are no-deal outcomes with `negotiated_surplus_share=0.000`,
so their different `pareto_efficiency` values are BATNA-height artifacts,
not negotiation improvement. Run 7 was skipped for Phase 27 backfill
because it lacks a matching compiled scenario analysis.

The beta-squeezed variant **reached the Pareto-optimal deal** (`High water + Heavy-Downstream payment + Joint-Funded Desalination`) for the first time across 9 runs. Every faction beat its BATNA — gamma by +11 points, alpha by +6, beta by +3. The deal recorded in `scores.agreed_outcomes` matches the optimum identified by `verify_scenario_optimum.py` byte-for-byte.

The scorer assigned alpha=15 / beta=18 / gamma=22 (sum=55) for the agreed outcomes; hand-table lookup gives alpha=16 / beta=18 / gamma=20 (sum=54). The small alpha/gamma deltas are LLM-scorer rounding (`score_game()` uses `structured_call`, not strict table indexing). `max_pareto_sum=54` was computed from the deterministic enumerator, which is why `pareto_efficiency` came back at 1.019 instead of 1.000.

`time_to_deal` registered `4` for the first time across all 9 runs — the FINAL ROUND messages in the beta-squeezed variant included one of the `_DEAL_MARKERS` phrases (likely `"final agreement"` or `"binding agreement"`; the marker scan in `analysis.py` is case-insensitive substring match). The symmetric and alpha-squeezed variants returned `None` as expected (no deal closed). This is signal that the `_DEAL_MARKERS` list is not as broken as the retro-scan suggested — it just needs an actual deal to fire.

Opening gaps tell a consistent story: in the variants without a deal, the squeezed faction's gap was small (alpha-squeezed: alpha_gap=0.091; beta in symmetric: 0.095). In the variant with a deal, every faction's gap is large (alpha 0.318, beta 0.476, gamma 0.091), reflecting how much each shifted from R1 opening to final score.

`broken_promise_rate` rose to 0.231 in the deal variant — proposals turned over more during the negotiation because positions actually moved. The two no-deal variants had low rates (0.154 and 0.028) for the opposite reason: agents anchored on R1 positions and never amended.

**Per-variant qualitative notes (from log files):**

- *Symmetric:* Same deadlock pattern as Run 8. Alpha anchored on Heavy-Downstream, Beta on High volume + Token payment, Gamma allied with Beta. R4 proposals stayed at extremes. Reconciliation merged duplicates as expected.
- *Alpha-squeezed:* Alpha held even harder on its priority (Heavy-Downstream) because the higher BATNA meant losing was worse. Beta took advantage and stayed on Token. Result: alpha got its BATNA exactly, beta kept its 8 floor, no deal. Asymmetric pressure *on the wrong faction* made things worse, not better.
- *Beta-squeezed:* Beta couldn't afford to hold out on Token because its BATNA was now 15 (its true threshold for "I'd rather take this than no deal"). Beta conceded payment in exchange for High volume + JFD. The concession unlocked the Pareto-optimal package because Alpha's preference (Heavy-Downstream) was also the second-best for everyone. Gamma's priority (Joint-Funded) was already aligned. Beta's reconciler log entries explicitly merged earlier Token-payment promises into the final Heavy-Downstream commitment — captured the position shift.

**Learning:**

1. *Asymmetric BATNA is a confirmed lever — but only when the right faction is squeezed.* Squeezing beta (the holdout on Payment) unlocked the Pareto deal. Squeezing alpha (the holdout on Payment but with the highest single-issue score = 10) only entrenched alpha further. The lever's effectiveness depends on *which faction is preventing convergence*, not just on overall pressure.

2. *The "don't accept the first reasonable framework" rule from Run 8's Open Items did NOT prevent a Pareto deal here.* Same persona text, same scenario, same prompts — the only delta was beta's BATNA. The over-anchoring hypothesis (Run 8 Open Item) needs revising: the rule isn't the binding constraint when material pressure makes holdout unaffordable.

3. *`pareto_efficiency` conflates negotiation skill with BATNA height when no deal is reached.* The symmetric variant scored 0.593 vs Run 8's 0.537 with identical no-deal outcomes (everyone at BATNA) — the difference is just that symmetric had a higher beta BATNA. For no-deal comparisons we'd need a different metric (e.g. `delta_above_batna_sum / max_pareto_sum_minus_batna_sum`). This is a Scoring item to consider in a future Build phase.

4. *`time_to_deal` works when there's a deal to detect.* The `_DEAL_MARKERS` list flagged the beta-squeezed R4. The 7-run retro-scan returning None was correct — none of those games closed. Item closed.

5. *Reconciliation captures position shifts when they happen.* Beta-squeezed produced clean reconciliation logs documenting Beta's Token→Heavy-Downstream transition ("Merged Beta's two promises on volume, payment, and infrastructure into beta-alpha-volume-payment-infrastructure-final-r3, removing beta-volume-payment-infrastructure-r1"). The Run 7+8 Open Item "reconciler doesn't catch position shifts" — partially resolved: reconciler now visibly handles shifts during deal-making. The `pending → broken` and inconsistency-flagging paths still need a scenario designed to provoke a clean contradiction (Open Items list unchanged on those two paths).

**Decisions taken:**

- *Beta-squeezed result publishable.* This is the first concrete demonstration that asymmetric pressure changes outcomes. Worth promoting to ASSESSMENT.md as evidence for the skill-testing scenario design (Block C) and to NEXT_STEPS §2 as a closed case for "BATNA pressure works when applied to the deadlock-holder."
- *Per-faction "right-to-squeeze" question raised for Run 10.* If asymmetric BATNA's effectiveness depends on which faction holds out, then a useful scenario-design tool is "identify the deadlock-holder before the game and squeeze them." That's an empirical question — would a pre-game analyst pass over the scoring tables flag the right faction? Worth a focused investigation.
- *No-deal `pareto_efficiency` deserves a complementary metric.* Add a `delta_above_batna` aggregate to `score_game()` output so symmetric-vs-Run-8 isn't misread as "53.7 → 59.3 efficiency improvement" when the only change was higher BATNAs. Queue as a Build candidate — small scoring change, ~1 step in a future phase.
- *Don't pursue Run 10 yet.* Wait for the Coached self-play smoke first; the operator-coaching loop is the higher-leverage open item per the prior session sequencing.

**Open items closed by this run:**
- *Asymmetric BATNA pressure as a lever* (Run 8 Open Items): confirmed when applied to the deadlock-holder. NEXT_STEPS §2 mechanism 1 (per-faction asymmetric BATNA) gets supporting evidence.
- *`_DEAL_MARKERS` coverage* (raised in this entry's retro section): marker list fired on first real deal. Not a coverage gap, just a no-deal corpus.
- *Reconciler captures position shifts during convergence* (Run 7+8 partial): demonstrated in beta-squeezed variant.

**Open items raised by this run:**
- [ ] **No-deal `pareto_efficiency` confounded with BATNA height.** Add a `delta_above_batna_sum / max_pareto_sum` or similar baseline-normalized metric. ~1-2 step build candidate.
- [ ] **Asymmetric BATNA effectiveness depends on which faction is squeezed.** Investigate whether a pre-game heuristic (or LLM analyst pass) can identify the deadlock-holder from the scoring table alone. Either a tool (`identify_deadlock_holder.py`) or a step inside `scenario_compiler`.
- [ ] **Alpha-squeezed entrenched alpha further.** Under-pressure faction may double-down rather than concede; this is the opposite of the desired effect. The symmetry of the squeeze (raising BATNA) doesn't account for psychology of the agent already in a losing position. Worth a more controlled study (Run 10 candidate).
- [ ] **Scorer rounds individual faction scores.** Hand-table lookup gave alpha=16 / gamma=20 (sum 54); scorer gave alpha=15 / gamma=22 (sum 55). Worth investigating whether `score_game()` should fall back to deterministic table lookup when `agreed_outcomes` is fully specified. Small correctness item, not blocking.

### Post-mortem (2026-06-01): Transcript close-read of the alpha-squeezed variant

The "alpha-squeezed entrenched alpha" reading above is wrong. A line-by-line
close-read of `run9_alpha_squeezed_live.json` (alpha + beta + gamma R1-R4)
against the symmetric variant flips the interpretation almost completely.
**Alpha was more flexible under squeeze, not less. The deal-breaker was beta's
last-round defection from her own R3 conditional commitment.**

**What alpha actually did (vs symmetric variant, same OpenAI model both runs):**

| Round | Symmetric Alpha (BATNA 11) | Alpha-Squeezed Alpha (BATNA 15) |
|---|---|---|
| R1 | Low + Heavy-Downstream + JFD | Low + Heavy-Downstream + JFD (**identical opening**) |
| R2 | Holds Low water, "any deal with Token or Shared payments is unacceptable... worse than my BATNA" | **Already concedes Low→Medium water**, contingent on Gamma honoring Heavy-Downstream |
| R3 | First water concession (Low→Medium) | Reaffirms Medium, **offers further conditional trade** ("If Beta is able to increase contribution toward payment or infrastructure, I am open to revisiting a higher water release volume") |
| R4 | Medium + Heavy-Downstream + JFD | Medium + Heavy-Downstream + JFD, **plus explicit walkaway** ("Heavy-Downstream payment structure is non-negotiable; failure to agree on this will force Alpha to withdraw and revert to its BATNA") |

Alpha conceded *earlier* (R2 vs R3), offered *additional* conditional concessions
(R3 trade on water volume contingent on Beta paying more), and made the
walkaway threat *more explicit* in R4. That's not entrenchment — that's a
faction visibly trying harder while sharpening its non-negotiable.

**Where the deal actually broke.** By R4, alpha and gamma had textually
converged on **identical terms**: `Medium water + Heavy-Downstream payment +
Joint-Funded Desalination`. Hand-scored, that deal would give:
- alpha: 6 (Medium) + 10 (Heavy-Downstream) + 3 (JFD) = **19** (BATNA 15, +4)
- beta: 6 (Medium) + 4 (Heavy-Downstream) + 4 (JFD) = **14** (BATNA 8, +6)
- gamma: 5 (Medium) + 3 (Heavy-Downstream) + 10 (JFD) = **18** (BATNA 11, +7)
- sum = 51 (on the Pareto frontier; every faction beats BATNA)

**Beta defected at the last moment.** The trace:
- **Beta R3 (commitment):** "willingness to accept Medium water release volume *contingent on Gamma's commitment to Heavy-Downstream payment*"
- **Gamma R4 (honoring conditional):** "I commit fully to the Heavy-Downstream payment structure, aligning with prior promises and unlocking Alpha's and Beta's conditional concessions"
- **Beta R4 (defection):** Should have honored the R3 contingent and confirmed Medium + Heavy-Downstream. Instead pivoted to `High + Shared + JFD`. Reasoning: "*I must prioritize securing High water release volume... my limited cash capacity constrains me. Therefore, I am willing to accept the Shared payment structure as a reasonable compromise.*"

Beta misread the room — proposed Shared payment when alpha+gamma had just
converged on Heavy-Downstream. The "compromise" beta offered moved *away* from
the converging deal, not toward it. The scorer's strict-consensus rule then
read the 2-of-3 alpha+gamma agreement as no-deal and all three reverted to
BATNA.

**Revised diagnosis (corrects the four hypotheses above):**

1. *Original H1 (BATNA = refusal mechanism, not concession trigger)* — Partially right. BATNA is a refusal mechanism, but the alpha-squeezed transcript shows alpha was still motivated to negotiate; the squeeze didn't suppress concession behavior. The cleaner statement is: BATNA narrows what you'll accept; it does NOT prevent you from proposing or compromising. Alpha-squeezed alpha proposed more, not less.

2. *Original H2 (squeezed the wrong faction)* — Still partially right, but the mechanism is different than first thought. Squeezing alpha did unlock alpha's flexibility on its non-priority issue (water) while sharpening alpha's non-negotiable (payment). The problem wasn't that alpha became inflexible — it was that alpha+gamma's convergence still needed beta's buy-in.

3. *Original H3 (Beta's relief made her unwilling to budge)* — Partially right but the mechanism is more specific: Beta's relief (BATNA=8) made her able to *defect from her own R3 commitment in R4 at no cost*. Reverting to BATNA was painless. **The binding constraint wasn't beta's willingness to budge in early rounds — it was beta's willingness to follow through on a contingent commitment when the contingency was met.** Beta-squeezed (BATNA=15) couldn't do this; defecting back to BATNA was a real loss. So beta-squeezed forced beta to be consistent across rounds, which is what unlocked the Pareto deal.

4. *Original H4 (acceptable deal space shrank)* — Mostly wrong as the binding mechanism. Alpha-squeezed alpha did refuse some deals that symmetric alpha would have accepted (e.g. Token sums where alpha=8), but in this transcript the deal that nearly closed (Medium + Heavy-Downstream + JFD, alpha=19) cleanly beat both BATNAs. Deal-space shrinkage wasn't what blocked convergence.

**The corrected reading of Run 9:**

Asymmetric BATNA's primary effect is **commitment-following enforcement**, not
"squeeze the deadlock-holder." The faction with the most to lose by defecting
from a contingent commitment is the most likely to honor it across rounds.
Beta-squeezed couldn't defect at the last round; alpha-squeezed beta could and
did.

This is a more general and more useful finding than "squeeze the deadlock-holder."
It also has different implications for scenario design: the lever is per-faction
*cost of inconsistency*, which raises the question of whether BATNA is even the
right knob, or whether something like "reputation cost across rounds" would be
more direct.

**Updated experiment recommendations:**

- [ ] **Experiment B' (replaces original B):** Alpha-squeezed BATNAs, but
      route beta through Anthropic claude-haiku-4-5 (which Run 8 used on beta).
      Tests whether beta's R3→R4 defection is OpenAI-gpt-4.1-mini-specific or
      a general LLM-default behavior. ~$0.30.
- [ ] **Experiment C' (replaces original C):** Alpha+beta dual-squeeze
      (`alpha=0.65, beta=0.60`). With beta's fallback raised, beta can't
      defect cheaply. Tests whether dual squeeze unlocks the deal that single
      alpha-squeeze almost reached. ~$0.30.
- [ ] **Experiment F (new, no LLM cost):** Relax the scorer. Add a
      partial-consensus mode to `score_game()` that recognizes 2-of-3 agreement
      as a partial deal (scores the agreeing factions on the converged terms;
      marks the dissenting faction as defected, scored at BATNA). Then re-score
      the alpha-squeezed result and likely Run 7 too. **Highest value per cost.**
      Closes the recurring Run 7/8/9 "scoring rule strictness" open item.
- [ ] **No-deal-aware `pareto_efficiency`** (carried from Run 9 Open Items
      above; reaffirmed). `negotiated_surplus_share = (achieved - sum_batnas) /
      (max_pareto - sum_batnas)`. At BATNA: 0.0. At Pareto: 1.0. Reads cleanly.
      Same Phase scope as Experiment F.

**Open items updated by this post-mortem:**
- *"Alpha-squeezed entrenched alpha further"* (raised above) — Re-classified.
  Alpha was not entrenched; beta defected. Item rewritten as Experiment B' /
  C' / F above.
- *"Asymmetric BATNA effectiveness depends on which faction is squeezed"*
  (raised above) — Refined. The lever is commitment-following cost, not
  deadlock-holder identification. A pre-game tool should look at both
  "who blocks convergence?" and "who is most likely to defect from contingent
  commitments?"
- *"Scoring rule strictness" (recurring across Run 7 + Run 8)* — Promoted from
  long-term carry-forward to next-phase candidate (Experiment F). Reconsidered
  2026-06-01: operator pushed back that partial-consensus scoring conflates
  outcome (binary on deal/no-deal) with diagnostic. Replanned as a `near_miss`
  diagnostic flag (read-only on score), not a scoring change. Item open as a
  small `analysis.py` build, not a phase.

---

## Phase 9: Commitment-Following Hypothesis (Run 10) — COMPLETE

### Run 10 — Asymmetric BATNA refinements (B' + C') — COMPLETE

**Status:** COMPLETE 2026-06-01. Two variants run sequentially. Total spend
~$0.85. **B' reached the Pareto deal; C' did not.** B' result is the cleanest
provider-effect signal we've produced — same BATNAs as Run 9 alpha-squeezed
(alpha=15, beta=8, gamma=11), only beta's Generator changed from OpenAI
gpt-4.1-mini to Anthropic claude-haiku-4-5, and the deal closed. C' (dual
squeeze, all OpenAI) reproduced Run 9 alpha-squeezed's R3→R4 defection pattern,
this time with gamma (not beta) as the defector.

**Observations:**

| Variant | pareto_eff | negotiated_surplus_share | Deal? | alpha Δ | beta Δ | gamma Δ |
|---|---:|---:|---:|---:|---:|---:|
| Run 9 α-squeezed (all OpenAI) | 0.630 | 0.000 | No | 0 | 0 | 0 |
| **Run 10 B'** (Anthropic on beta only) | **1.019** | **1.050** | **YES** | 0 | **+10** | **+11** |
| Run 9 β-squeezed (all OpenAI) | 1.019 | 1.053 | YES | +6 | +3 | +11 |
| **Run 10 C'** (dual squeeze, all OpenAI) | 0.704 | 0.000 | No | 0 | 0 | 0 |

**B' transcript trace — beta-on-Anthropic honored her R3 contingent at R4.**
- *Beta R3:* "**I propose: High water release volume (20M gallons/month), Heavy-Downstream payment structure ($2M/year from Gamma, $500K/year from Beta to Alpha), and Joint-Funded Desalination infrastructure.** ... **My proposal: High water release volume, Heavy-Downstream payment structure, Joint-Funded Desalination infrastructure.**"
- *Beta R4:* "**My final proposal: High water release volume (20M gallons/month), Heavy-Downstream payment structure, Joint-Funded Desalination infrastructure.**" Verbatim repeat. Followed through.
- Beta got Δ=+10 (vs Run 9 β-squeezed's Δ=+3 for beta). With BATNA at 8, the same agreed deal scored beta higher above BATNA.

**C' transcript trace — gamma-on-OpenAI defected at R4.**
- *Gamma R3:* "Heavy-Downstream, as Alpha and Beta agree, ensuring full compensation for Alpha" — committed to Heavy-Downstream.
- *Gamma R4:* "Shared payment, where Gamma pays $1M/year, Beta pays $500K/year, and Alpha absorbs some losses" — switched to Shared.
- Alpha + Beta both ended on Heavy-Downstream + JFD in R4 (water vol diverged Medium vs High), but Gamma's R4 Shared defection broke the consensus.
- Same R3→R4 defection pattern as Run 9 alpha-squeezed (beta there, gamma here). Different faction, same provider, same behavior.

**Learning:**

1. *Provider consistency dominates BATNA pressure in this scenario.* B' kept the alpha-squeezed BATNAs (relieved beta to 8) and just rerouted beta's Generator to Anthropic — the same configuration that produced no-deal in Run 9 now produces the Pareto-optimal deal. The variable that changed everything was provider, not pressure.

2. *OpenAI gpt-4.1-mini has a reproducible R3→R4 defection pattern on this scenario.* Two independent instances (Run 9 α-squeezed beta, Run 10 C' gamma) — same model, different factions, identical failure mode: textually commit in R3 to a position the other two factions are converging on, then propose a different (and personally preferred) position in R4. The Phase 26 logging surface would help instrument this further, but for now the transcript pattern is consistent.

3. *Dual squeeze does NOT compensate for provider inconsistency.* C' raised BATNAs higher than any prior variant on both alpha and beta (alpha=14, beta=13 — both well above baseline 11/10) and still got a no-deal because gamma defected. More BATNA pressure didn't make the OpenAI agents more consistent across rounds — if anything it shrunk the acceptable deal space (3/27 BATNA-clearing deals vs 5/27 alpha-squeezed and 9/27 symmetric) without changing the failure mode.

4. *The Run 9 beta-squeezed result has a cleaner reinterpretation now.* Beta-squeezed worked not because asymmetric BATNA "unlocked" the deal but because beta-on-OpenAI was *forced* by BATNA=15 to be consistent — defecting at R4 to BATNA would have been a real loss. Anthropic beta in B' didn't need that forcing; she was consistent by default. **Both runs reached the same deal; the mechanism was different.**

5. *Surplus distribution: gamma keeps winning.* B' deltas [0, +10, +11] sum to 21 (compare Run 9 β-squeezed's 20). Gamma took 52% of the captured surplus in B' (vs 55% in β-squeezed). Across both deal-reaching runs, the un-pressured faction with the moderate BATNA (gamma in both cases) captured the lion's share — possibly because gamma's neutral position on the bottleneck issue (Payment) gave gamma credible "I'll go either way" leverage. Worth a focused analysis if we revisit scenario design.

6. *Alpha got nothing above BATNA in B'.* Alpha got exactly her BATNA of 15 (deal scored alpha=15). In Run 9 β-squeezed alpha got +6 above BATNA (deal scored alpha=15 vs BATNA 9). Same deal, different BATNAs. Confirms that asymmetric BATNAs reshape the surplus distribution even when the underlying deal is identical.

**Decisions taken:**

- *Promote provider-consistency hypothesis to a working finding.* For OpenAI gpt-4.1-mini on this scenario family, R3→R4 defection is the dominant deal-breaking mechanism. Any future Run that mixes providers should treat consistency-friendly providers (Anthropic so far; Google untested in this scope) as candidates for high-commitment seats (the faction most likely to make convergence-critical contingents).
- *Open a follow-up: rotate Anthropic across all three seats to confirm the effect is provider-default, not faction-specific.* "Three single-provider Anthropic runs on the same three Run 9 BATNA variants" would tell us whether Anthropic Beta is a special case or whether Anthropic is just better at multi-round consistency across the board. Estimated ~$1.20.
- *Don't pursue partial-consensus scoring (Experiment F from Run 9 post-mortem).* The operator pushed back 2026-06-01 that "if there's no agreement, it doesn't matter if we missed it by an inch or by a mile." Confirmed by Run 10: C' would have shown alpha+beta partial consensus on payment+infra (water diverged) — but the operationally meaningful outcome is still no-deal. Replanned as a `near_miss` diagnostic flag for `analysis.py`, not a scoring change.
- *Defer dual-squeeze direction.* C' showed dual squeeze doesn't help when the consistency problem dominates. Don't invest more in that direction until provider consistency is independently characterized.

**Open items closed by this run:**
- *"Per-faction commitment-following cost asymmetry"* (Run 9 post-mortem) — Reframed. The dominant variable is provider, not BATNA height. Closed as "BATNA-based commitment enforcement" hypothesis; reopened as "provider-based commitment-following" question.
- *"Was beta's R3→R4 defection in Run 9 OpenAI-specific?"* (Run 9 Open Items) — Confirmed: yes. Two independent instances (Run 9 α-squeezed beta, Run 10 C' gamma) both on OpenAI gpt-4.1-mini both defected at R4. Anthropic beta in B' did not.

**Open items raised by this run:**
- [ ] **Reproducibility of OpenAI gpt-4.1-mini's R3→R4 defection.** Two-of-two on Water Rights so far. Worth checking whether the defection happens on Three-Party Coalition or Trade Summit scenarios too, OR whether it's Water-Rights-specific (e.g. the payment-structure issue has a specific framing that triggers it).
- [ ] **Three-faction Anthropic baseline.** Run all three Run 9 BATNA variants with all-Anthropic generators. Tells us whether Anthropic reaches Pareto deals across the BATNA spectrum or only when the structure already favors it. ~$3-4.
- [ ] **Surplus distribution unfairness for the squeezed faction.** Beta got +10 in B' but only +3 in Run 9 β-squeezed despite the same deal — because her own BATNA was higher in β-squeezed. The agent that gets squeezed pays an opportunity cost: the deal that emerges gives them less *above* their BATNA. This may be a feature (we forced them to take a deal at all) but worth noting for scenario design — squeeze on faction X reshapes the surplus *toward* X-via-the-deal but *away* from X-via-the-floor.
- [ ] **Gamma's lion's share is structural.** Gamma extracted 52-55% of surplus in both Pareto-reaching runs. The un-pressured neutral-on-bottleneck faction takes most. Implications for scenario design: if you want a faction to "win", route them toward a neutral position on the bottleneck issue.

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
| 8 | Water Rights (3-provider) | a=8, b=15, c=5 | 0 | ~$1 | **Provider differentiation visible qualitatively** but raw scores deadlock at BATNA. Volume and Infrastructure converge cleanly; Payment deadlocks (Alpha=Heavy-Downstream vs Beta+Gamma=Token). Pareto-optimal Shared compromise existed but no agent proposed it. Two silent-failure infra bugs surfaced and fixed (`.env` not loaded; toolkit `parse_json_response` didn't strip Markdown fences from Anthropic/Google JSON). New CLI flags: `--per-faction-providers`, `--analysis-json`, `--expect-providers`. New verifier: `verify_scenario_optimum.py`. Retro-pareto (2026-06-01): **efficiency = 0.537** (29/54). |
| 9 | Water Rights (3 asymmetric BATNA variants) | sym=29 / α-sq=22 / β-sq=13 | 0 | ~$1.20 | **Complete 2026-06-01.** Single-provider gpt-4.1-mini. β-squeezed variant **reached Pareto deal**: alpha=15 (+6), beta=18 (+3), gamma=22 (+11), pareto_efficiency=1.02. Symmetric (0.593) and α-squeezed (0.630) reproduced no-deal deadlock. Asymmetric pressure on the deadlock-holder unlocks the optimum; on the wrong faction it entrenches them. `time_to_deal=4` registered for first time. |
| 10 | Water Rights (B' Anthropic-on-beta + C' dual-squeeze) | B'=39 / C'=24 | 0 | ~$0.85 | **Complete 2026-06-01.** B' (alpha-squeezed BATNAs, beta on Anthropic claude-haiku-4-5, alpha+gamma OpenAI gpt-4.1-mini): **reached Pareto deal** alpha=15 (+0), beta=18 (+10), gamma=22 (+11), `negotiated_surplus_share=1.050`. Same configuration that produced no-deal in Run 9 α-squeezed (all OpenAI). Confirms OpenAI gpt-4.1-mini R3→R4 defection is provider-specific. C' (alpha+beta dual-squeeze, all OpenAI): no-deal — gamma defected from R3 Heavy-Downstream commitment to R4 Shared (same defection pattern as Run 9 α-squeezed beta, different faction, same model). |

**Total spend across completed runs (1-10): ~$7-8**
**Pre-flight already incurred: $0 (dry-runs free, OpenAI probe ~$0.001)**

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

10. **Cross-provider JSON formatting differs even with identical prompts** (Run 8). Anthropic and Google wrap JSON output in `` ```json ... ``` `` Markdown fences regardless of explicit "return raw JSON" instructions. OpenAI returns raw JSON. Any structured-output layer must strip fences before parsing, or risk silent retry-then-give-up failure modes that look like "the model returned nothing."

11. **Silent failures hide behind "success."** (Run 8). Two of Run 8's bugs (missing `.env` load + missing fence-strip) produced "successful" LLM calls that returned strings the downstream parser couldn't read. The structured_call retry loop happily burned all retries on the same parse failure and reported no error. Active assertion of *expected* behavior (`--expect-providers` in verify_dryrun, expected message counts in verify_dryrun) is the cheapest way to catch these.

12. **Per-faction provider routing belongs in the runner, not the env** (Run 8). The original env-var-based config (`DIPLOMAT_PRIMARY_PROVIDER`) was global across factions. A CLI JSON flag (`--per-faction-providers`) is much cleaner: it's explicit, validates early, and the verifier can assert each faction got the assigned provider.

13. **Compiler defaults aren't always what you want** (Run 8). The scenario compiler's hardcoded BATNA range ("typically 4-8 total") produced too-soft pressure for our experiment regardless of narrative cues. A pre-compiled-analysis loader (`--analysis-json`) is the right escape hatch — it lets you hand-edit the compiler's output and reuse it across runs.

14. **Dry runs and live probes catch different failure modes** (Run 8 post-mortem). Dry-run validates *plumbing* (round counter, message routing, budget reset) because it controls the LLM responses. It cannot catch *provider integration* bugs (auth, JSON parsing, model name typos) because it replaces the LLM client entirely. The fix: a separate `probe_providers.py` that makes 1 real call per provider with a trivial prompt. ~$0.003 total. Run BOTH before any live multi-provider game.

---

### Open Items

**Still open (post Run 10):**
- [x] **Provider rotation control (original Run 9 scope).** Partially addressed by Run 10 B': switching beta to Anthropic on alpha-squeezed BATNAs unlocked the Pareto deal. Full rotation control (all-Anthropic baseline across all 3 BATNA variants) still pending — ~$3-4 spend.
- [x] **No-deal `pareto_efficiency` confounded with BATNA height.** Closed by Phase 27: `score_game()` now emits `negotiated_surplus_share`, `delta_above_batna_sum`, `min_faction_delta`, and companion BATNA-normalized fields. Run 8 / Run 9 / Run 10 no-deal backfills all read `negotiated_surplus_share=0.000`.
- [x] **Partial-consensus scoring (recurring across Run 7 / Run 8 / Run 9).** Replaced by `near_miss` diagnostic flag concept after operator pushback 2026-06-01: "if there's no agreement, it doesn't matter if we missed it by an inch or by a mile." Won't be a scoring change; small `analysis.py` diagnostic instead. Not Phase 28.
- [x] **Commitment-following cost asymmetry.** Reclassified by Run 10. The dominant variable is provider, not BATNA height. OpenAI gpt-4.1-mini's R3→R4 defection observed in two separate runs (Run 9 α-squeezed beta, Run 10 C' gamma). Anthropic beta in Run 10 B' did not defect.
- [ ] **OpenAI gpt-4.1-mini R3→R4 defection — scope.** Confirmed on Water Rights (twice). Unknown on Three-Party Coalition / Trade Summit. Either characterize cross-scenario, or accept "consistency-critical seats should not be OpenAI gpt-4.1-mini" as a tuning rule and move on.
- [ ] **All-Anthropic baseline across BATNA variants.** Three runs (~$3-4): does Anthropic reach Pareto across symmetric / alpha-squeezed / beta-squeezed, or only when the configuration already favors it? Tells us whether Run 10 B' generalizes.
- [ ] **Persona payment rigidity.** Recurring across Run 7 and Run 8. Worth A/B test on the "don't accept the first reasonable framework" persona rule. Run 9 post-mortem suggested this rule isn't binding under squeeze; A/B would confirm.
- [ ] **Surplus-distribution asymmetry favoring the un-squeezed neutral faction.** Across all three Pareto-reaching runs (Run 9 β-squeezed, Run 10 B'), gamma extracted 52-55% of negotiated surplus. The faction with moderate BATNA + neutral position on the bottleneck wins biggest. Worth understanding for scenario design.
- [ ] **Google free-tier rate limiting.** Gemini 2.5-flash hit 429 on Run 8 R4. Either add retry-with-backoff to toolkit's `llm_client`, or switch to a paid Gemini tier for serious runs.
- [ ] **Compiler BATNA anchor.** `tools/scenario_compiler.py` system prompt hardcodes BATNA range. Add a `--batna-fraction` override or relax the range guidance. (Partially closed by Phase 24 which added `--batna-fraction` / `--force-batna-fraction` flags; this item is the underlying prompt guidance.)
- [ ] Reconciliation: fulfillment detection (`pending → kept`). Still untested in practice. Run 10 B' Pareto deal might have produced fulfillments — needs targeted inspection.
- [ ] Reconciliation: status transitions to `broken`. Run 9 α-squeezed and Run 10 C' both had clean defections (beta R3→R4 and gamma R3→R4 respectively). Reconciler likely did not flag these as broken. Worth a focused look at those run logs.
- [ ] Reconciliation: inconsistency flagging. Same as above.
- [ ] Reconciliation: missed-proposals path. Implicit zero across Run 7-10.

**New items raised by Run 8:**
- [ ] **Provider × position confound.** Alpha won by tiebreak with the highest BATNA. Can't tell if that's "OpenAI plays hardball best" or "alpha had the most leverage to play hardball." Run 9 (rotation) is the test.
- [ ] **No agent proposes Pareto compromises.** None of OpenAI/Anthropic/Google proposed the Shared payment compromise even though it cleanly beats all BATNAs. Suggests the persona prompt's "don't accept the first reasonable framework" rule may be over-anchoring. Worth A/B testing a softened variant.

**Older items (carried forward):**
- [ ] Persona drift over 8+ rounds not yet tested.
- [ ] Real game deployment (Telegram, operator coaching, non-self-play).
- [ ] Provider-native structured output (OpenAI `response_format: json_schema`).
- [ ] Level 1 modularization: config-driven prompts and examples (see DEVPLAN roadmap).
- [ ] **Persona endgame over-anchoring (Run 7).** Static `ENDGAME:` paragraph in the auto-compiled persona caused faction A to invent the phrase *"as we approach our final round"* in round 2 of Run 7-v1. Decide whether to soften the static persona text, move more of the urgency into the dynamic markers only, or accept that some early-round endgame thinking is fine.
- [ ] **`LoggingLLMClient` doesn't see SCORE or RECON calls (Run 7).** Both `score_game()` and reconciliation setup unwrap the wrapper to use the inner client. Result: `verify_dryrun` and the call-log inspector miss these calls.
- [ ] **Conversation model Stage 2+.** `ARCH_conversation_model.md` documents the M2-bounded / M2-debounced / M2-async migration path. Stage 2 (K=2 passes per round — open + react) is the natural next upgrade if Run 9 results suggest agents need within-round reactivity to test interesting hypotheses.
