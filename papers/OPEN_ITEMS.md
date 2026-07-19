# Diplomat — Open Items (living index)

> **Purpose.** One durable, grouped index of open work + resolved items across
> Diplomat, so status isn't stranded in chat or scattered across docs. This is an
> **index**, not a spec — it points into the docs that *own* each area rather than
> duplicating them.
>
> **Ownership / where the detail lives:**
> - **Paper order** → `papers/WORK_SEQUENCING.md` (§9 execution sequence).
> - **Paper spec** (contributions, experiment ledger, hygiene) → `papers/PAPER_PLAN.md`.
> - **Offering / product** → `papers/OFFERING.md` (claims ledger, TODOs T1–T9, tiers).
> - **Customer-tactic library + A/B metric** → `papers/TACTIC_LIBRARY.md`.
> - **Decisions** → `DECISIONS.md`; **history** → `DEVLOG.md`.
>
> **Status legend:** ✅ resolved · 🟡 open · ⏸ parked/deferred · ↩ retracted (was
> flagged, turned out not to be an issue) · → owned elsewhere (pointer only).
>
> **Work regime + autonomy** (GOVERNANCE §"Work Regimes", keyed on *evaluability*;
> run-lanes match `WORK_SEQUENCING`):
> - **Build 🔨** — AI-evaluable (tests / type-checks / objective criteria) →
>   **autonomous-loopable** (the loop can self-verify).
> - **Refine 👁** — needs human perception/judgment → supervised.
> - **Explore 👁** — goal is a *decision* → supervised (time-boxed).
> - **Mixed 🔀** — a Build core behind an Explore/Refine gate (loopable *after* the
>   gate is closed).
> - Non-dev: **Run 👁** (experiment execution), **Authoring 👁** (prose/figures),
>   **Decision** (open choice).
>
> **Last updated:** 2026-07-01.

---

## 1. Technical debt (code correctness / hygiene / drift)

- ✅ **Build 🔨 (done).** **Brittle text-matching analytics (near-miss / defection in
  `analysis.py`).** Token-subsequence position inference (`_response_matches_outcome`
  et al.) fed only `compute_near_miss` / `defection_event_log`, which were never
  persisted and had no downstream consumer. **Deleted 2026-07-01** as dead code (+
  removed `tests/test_self_play_near_miss.py`); `compute_process_signatures` kept.
  Verified: compiles, analysis tests pass, no remaining references. Real-dialogue
  position extraction is a *forward* need → **offering T5** + the **paper mechanism
  classifier** (§4.1) — not a retrofit of the deleted heuristic.
- ↩ **Build 🔨 (residual, small).** **`event_store` "empty module / doc↔code drift".**
  **Retracted** — false alarm. `SQLiteEventStore` is fully implemented, wired
  (required Orchestrator module, both self-play + coaching), spec-accurate. *Optional
  follow-up:* self-play keeps the raw log in a throwaway per-faction temp `.db` (the
  persisted transcript is `channel_log`); a durable product audit trail would have
  `collect_results()` also dump `event_store`. Cleanly testable. Tracked in
  `OFFERING.md` §1.
- 🟡 **Mixed 🔀** (Explore: *enforce* vs. *drop the claim* → then Build).
  **Cosmetic pressure metadata.** `round_cost_decay` / clocks / `penalty_floor`
  render into prompts but are **not applied in scoring** — time-pressure dynamics
  aren't enforced. Overlaps ⏸ Phase 39 (exogenous events).
- 🟡 **Mixed 🔀** (Explore: continuous-modeling vs. discretize → then Build).
  **Discrete-only optimum.** Scoring enumerates a small discrete deal space; hard
  ceiling for continuous economic variables. Same work as **offering T3**.
- 🟡 **Build 🔨.** **3-party center of gravity.** Default factions auto-truncate to
  `[:3]`; N=2 analytics (coalition) degenerate. Same work as **offering T2**
  (asymmetric 1:1 harness + 2-party-aware reporting). Test-specifiable.
- → **Mixed 🔀.** **Paper hygiene** (uniform temperature + N≥10–20 config = Build;
  "explain zero within-cell variance" = Explore/investigate). Owned by
  `PAPER_PLAN.md` §5.0.
- 🟡 **Refine 👁.** **Doc↔code accuracy (periodic).** Keep specs honest against code
  (human judgment). Known: adversarial ARCH/code agree; the **PITCH** over-claims
  "manipulation/prompt-injection detection" — tracked in `OFFERING.md` ledger.

## 2. Future directions (deferred / icebox — parked)

Per `WORK_SEQUENCING.md` §7–§8; none on the Paper 1/2 critical path. (Regime =
*if undertaken*.)

- ⏸ **Build 🔨.** Tournament / `TurnBasedFlow` multi-game harness + cross-game state
  (Phase 40).
- ⏸ **Mixed 🔀.** **Coaching product** (live Telegram review-gate, coached self-play
  Run 13b, ClankmatesTransport, persona-drift) — frozen under D-56; revival mixes
  built infra (refine) + supervised live loops.
- ⏸ **Build 🔨 per stage** (Explore gate to advance). **Conversation-model evolution**
  (Stage 2a/2b/3, `ARCH_conversation_model.md`) — self-play *benchmark* realism.
  **Note:** *not* what the offering needs — a 1:1 customer chat wants a reactive/
  turn-based **Flow** on the shared Pipeline (`ARCH_flow.md` names "customer-service
  streams"; `TurnBasedFlow` example) = **offering T2**. Staged models don't transfer;
  the design-problem catalogue (termination, scoring snapshot, feedback loops) does.
- ⏸ **Build 🔨.** Exogenous events / mid-round BATNA shocks (Phase 39) + cascade scoring.
- ⏸ **Mixed 🔀.** **Paper 3** — behavioral steering (disposition × scenario): Build
  instruments + supervised runs + Explore framing.
- ⏸ **Mixed 🔀.** Scenario-class breadth beyond 4–5 shapes; divorce showcase (authoring
  via the builder is loopable, but operator verifies scenario properties).
- ⏸ **Build 🔨.** Infra niceties: provider-native structured output, Pareto-frontier
  annotation, identify-the-blocker tool.

## 3. Work for the paper → owned by `WORK_SEQUENCING.md` §9

Pointer only (full order + dependencies there; spec in `PAPER_PLAN.md`). Regimes
match WORK_SEQUENCING run-lanes:

- **Phase A — builds — Build 🔨 (autonomous):** mechanism classifier (§4.1) +
  per-question κ; capability probe battery (§4.2, 7 probes).
- **Phase B — scenario authoring — Mixed 🔀** (operator verifies scenario properties
  via `verify_scenario_optimum`): hidden-value/deception (4th shape); 4-faction;
  `coalition_values` on succ3b + over-grab diagnostic.
- **Phase C — hygiene — Build 🔨** (mostly; quick 👁 checks). See §1 pointer.
- **Phase D — unified campaign — Run 👁** (supervised: cost + judgment; the linchpin
  spend: roster × suite × {full,bare} × N).
- **Phase E — analysis — Build 🔨 (autonomous;** gated on Phase D data).
- **Phase F — figures + writing — Authoring 👁.** Silent long poles: Related Work +
  early Meta internal publication review.

## 4. Work for the offering → owned by `OFFERING.md` / `TACTIC_LIBRARY.md`

Pointer + live status:

- **Foundation:** T1 agent-under-test ingress (prompt path first) — **Build 🔨** ·
  T2 asymmetric 1:1 harness — **Build 🔨**.
- **Measurement:** T3 continuous-value *or* discretize — **Mixed 🔀** (Explore first) ·
  T4 vertical scenario templates — **Mixed 🔀** (authoring + operator economics check) ·
  **T5** robust real-dialogue extraction (🟡 open; needs a per-issue position/stance
  field in the extraction schema) — **Mixed 🔀** (Build on fixtures; 👁 validate on real
  dialogue) · T6 client report layer — **Mixed 🔀** (assembly Build; report design = Refine).
- **Tactic library:** v1 = **outcome-only** (decided 2026-06-30; `TACTIC_LIBRARY.md`
  §8.1) — **Mixed 🔀** (A/B runner + tactic templates = Build; persona realism = Refine).
- **Secure tier (roadmap):** T7 manipulation/jailbreak detection — **Mixed 🔀**
  (classifier Build; κ needs hand-labels) · T8 policy enforcement — **Build 🔨**.
  **Save tier:** T9 model right-sizing — **Mixed 🔀** (assembly Build; runs = 👁 cost).
- **Open decisions — Decision (Explore 👁):** discrete-vs-continuous · config-audit-
  vs-live v1 · who validates the $ figure · first validation target · org home.

## 5. Cross-cutting (one build, multiple consumers)

- **Mechanism/bluff classifier = one capability, three consumers** (paper §4.1,
  offering **T7** detection, tactic-library calibration) — **Mixed 🔀** (Build +
  κ validation vs. hand-labels). **Sibling of, not the same as, structured
  extraction (T5):** classifier emits *behavioral labels* (LLM-judge + binary
  questions) feeding taxonomy/detection; extraction emits *objective state/facts*
  feeding scoring and the **$ susceptibility delta**. Same `structured_llm`
  primitive, different schemas/outputs. v1 outcome-only leans on **extraction**.
- **Scenario shapes are shared substrate — Mixed 🔀:** the paper's deception (4th) +
  asym-BATNA-walkaway (5th) shapes ≈ the offering's bluff / high-value-walk-away
  verticals. Build once, skin per consumer.
- **Strategy.** The campaign findings ARE the offering's credibility engine — don't
  fork the research; sequence so the paper feeds the pitch.

## 6. Autonomous-loopable shortlist (Build 🔨 candidates for i2c loop testing)

Purpose: seed a test of the autonomous loop with **Build** phases — AI-evaluable,
bounded, ideally low external dependency so the loop self-verifies via tests
without secrets/cost/human sign-off. Each must ship a **tests-first** DEVPLAN phase
(GOVERNANCE: "tests and acceptance criteria specified *before* implementation").

**Tier 1 — pure-code, zero-cost, fast (ideal first smoke tests):**
1. **`event_store` persistence follow-up** (§1). `collect_results()` also dumps
   `event_store.query(...)`; unit test asserts the raw log is in the results JSON.
   Smallest, safest, no LLM/keys — the cleanest loop smoke test.
2. **Phase C hygiene bits** (§3): external-index (Elo + MMLU) lookup table; confirm
   the N-scaling dispatcher. Small code/data, unit-testable, no LLM calls.

**Tier 2 — Build, self-contained but larger / needs LLM keys+cost:**
3. **T2 asymmetric 1:1 harness** (§1/§4). Well-specified harness Build with clear
   tests (N=2 game runs; coalition analytics disabled; 2-party report fields). Unit
   layer needs no external keys; a live game does.
4. **Mechanism classifier — Phase A** (§3). The paper's designated 🔨 phase; ground
   truth via binary questions; **seed hand-labels already exist** (14e / Run-15, per
   PAPER_PLAN §4.1). Needs LLM keys + small cost + the κ check → loopable but not
   zero-dependency.
5. **Capability probe battery — Phase A/B** (§3). Auto-gradable ground truth (no
   LLM-judge), but the probes call LLMs (keys + cost).

**Not loop candidates:** Phase D campaign (Run 👁, cost/judgment); Phase F writing
(Authoring 👁); all Refine 👁 / Explore 👁 / Decision items.

**⚠️ Run-path caveats (read before launching anything):**
- **Diplomat is i2c-migrated** (`rules/deployment.md`, 2026-07-01): it runs on the
  **i2c framework** (`.state/*.json` + the `i2c` CLI), driven by the **i2c Telegram
  bot** (`i2c serve telegram`, systemd `i2c-bot`) on pirozhok — the same bot that
  drives clankercourts/toolkit. No "migrate to i2c" prerequisite remains; queue a
  phase via `/setdir diplomat` then `/run` / `/batch` (codexbot drives only the
  remaining non-migrated e2e projects).
- **Loops run on pirozhok, not this laptop** (FU-28; one-poller-per-token). Do **not**
  launch a loop from a Devmate laptop session — queue via the i2c bot on pirozhok.
- Each chosen phase needs its intent in ARCHITECTURE.md / the target ARCH file + a
  tests-first spec (see `WORKER_SPEC.md`), advanced via `i2c state` / `.state/`
  (not DEVPLAN frontmatter — DEVPLAN is a frozen e2e archive) before it's loop-ready.

---

## Change log

- **2026-07-05** — Corrected the §6 run-path caveats and the WORK_SEQUENCING
  run-lane framing: diplomat is **i2c-migrated** (2026-07-01) and driven by the
  **i2c bot** on pirozhok, not codexbot/e2e. The 2026-07-01 (b) entry below
  ("e2e-vs-i2c" caveats) described the pre-migration state and is superseded.
- **2026-07-01 (b)** — Added work-regime + autonomy tags (Build 🔨 / Refine 👁 /
  Explore 👁 / Mixed 🔀) to every item, keyed on GOVERNANCE evaluability +
  WORK_SEQUENCING run-lanes; added §6 autonomous-loopable shortlist for i2c loop
  testing, with e2e-vs-i2c + pirozhok run-path caveats.
- **2026-07-01 (a)** — Index created. Near-miss/defection code + tests deleted
  (tech-debt §1 ✅). `event_store` drift retracted (↩). T5 kept + sharpened
  (schema position field). `OFFERING.md` updated to match. WORK_SEQUENCING
  confirmed to have no tech-debt list (paper-order doc); no change needed there.
