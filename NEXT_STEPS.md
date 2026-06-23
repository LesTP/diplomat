# Diplomat — Next Steps

> **Live forward backlog only.** Closed work lives in `DEVLOG.md` /
> `DEVLOG_archive.md` (phases) and `TUNING_LOG.md` (runs). Findings / theses
> live in `RESEARCH_NOTES.md`. Decisions live in `DECISIONS.md`. The canonical
> phase plan is `DEVPLAN.md`. Keep this file short — route everything else home.
>
> **Workstream tags** (`ASSESSMENT.md` §5): `[A]` agent architecture & memory ·
> `[B]` prompt tuning · `[C]` game creation & scoring · `[X]` cross-cutting infra.
> **Loop-readiness:** 🔨 pure build · 🔀 mixed · 👁 supervised.
>
> **Direction (D-56, 2026-06-16).** Diplomat is an LLM **negotiation benchmark**.
> Tier 1 = `[C]` game creation & scoring (primary surface); Tier 2 = `[A]`/`[X]`
> infra that serves the benchmark; coaching-product work is deferred
> (infrastructure preserved, no new investment). Rationale: `DECISIONS.md` D-56.

## Current state (2026-06-22)

The §3.5 competitive-scoring stack is shipped and validated (rank-among-factions
lens + `faction_models` persistence + cross-game `mean_rank` aggregator +
mixed-model / position-rotation dispatcher; scoring hardened to credit only
genuine, rational, unanimous deals). **The open gap is discriminating scenario
design.** Two distributive scenarios bracket but miss the target: `succ` (Run 19)
converged on a seat-determined focal deal; `succ2` (Run 20) over-collided into
deadlock (5/6 no-deal). Budget ~$11-13 API remaining at session close. Detail:
`TUNING_LOG.md` Runs 18-20, `RESEARCH_NOTES.md` Note 2.

## Now — sequencing

Two open questions want *different* scenarios — decide first:

1. **Q1 "which model negotiates better?"** → build **`succ-v3`**: a distributive
   scenario in the sweet spot where deals close AND the outcome varies by skill
   (no focal point). Tune `succ` BATNAs / loser compensation so the contested
   asset resolves without an obvious Schelling point. (Needs **priority
   collision** — a contested asset — per Run 19; a 1:1 faction→asset mapping is
   itself a focal point.)
2. **Q2 "does the harness help?"** → run **`succ2` full-mode**: its bare deadlock
   is headroom, not failure; measure close-rate lift. Calibrate cost with 1 game
   first (~$2-5/game). A `succ2` full run could answer Q2 and, if harness-brokered
   deals vary by winner, also yield Q1 rank signal.

Then, in rough order: **Path B coalition-value scoring** (§3.6) → **Path A
calibration** (§11.b) → broaden **Path C** scenario authoring (asym-BATNA,
hidden-value) → **Run 17 follow-ups** (V3 n=3, R1 cells) + **N4** pressure on
jsm1 → **per-run cost capture** + **pricing audit**.

## Tier 1 — `[C]` benchmark direction (open)

| Item | Tags | Loop | Detail |
|---|---|---|---|
| **`succ-v3` sweet-spot scenario** (Q1) — deals close AND vary by skill; needs priority collision without deadlock | `[C]` | 👁 | `SCENARIO_GUIDE.md` (distributive authoring); `TUNING_LOG.md` Run 19 |
| **`succ2` full-mode harness test** (Q2) — measure close-rate lift over bare deadlock | `[C][A]` | 👁 | `TUNING_LOG.md` Run 20; `RESEARCH_NOTES.md` Note 1 |
| **§3.6 coalition-value scoring engine** (Path B build) — extend `scenario_analysis.json` `coalition_values`; `score_game()` detects partial-agreement coalitions, applies split, BATNA to excluded faction | `[C][A]` | 🔨 | `ASSESSMENT.md` §3.6; `RESEARCH_NOTES.md` Note 2 Path B. Three-Party Coalition v1 patched as first consumer |
| **§11.b Path A calibration** — mixed Three-Party Coalition × position rotation (9 cells, ~$1-2) | `[C]` | 👁 | `RESEARCH_NOTES.md` Note 2 Path A |
| **Path C scenario-class authoring** — asymmetric-BATNA-with-walkaway, hidden-value bluff (distributive done: `succ`/`succ2`) | `[C]` | 👁 | `RESEARCH_NOTES.md` Note 2 Path C |
| **Run 17 V3 full n=3 expansion** — solidify V3 baseline (~$0.15) | `[C]` | 👁 | `TUNING_LOG.md` Run 17 |
| **Run 17 R1 cells × 3** — first reasoning-model data points; toolkit-unblocked (`606e309`) (~$2-4) | `[C]` | 👁 | `TUNING_LOG.md` Run 17 |
| **N4 — gpt-mini + pressure × 3 on jsm1** — does pressure unstick the mid-tier "stuck-but-engaged" pattern (~$1.50) | `[C][B]` | 👁 | `RESEARCH_NOTES.md` Note 1 (revised-prediction table) |
| **Per-run cost capture in result JSONs** — `metadata.cost_usd` is `None`; benchmark cost-coverage is back-of-envelope without it | `[C][X]` | 🔨 | — |
| **Pricing audit** — cross-provider pricing accuracy across models we use (best after cost-capture) | `[X][C]` | 👁 | `toolkit.cost_accountant` |
| **ASSESSMENT §3.4 persuasion / concession-curve signatures** — LLM-judge over transcripts; higher cost, defer until other Tier-1 lands | `[C]` | 👁 | `ASSESSMENT.md` §3.4 |
| **Surplus-distribution investigation** — why does the neutral-on-bottleneck faction extract 52-55% of surplus? Likely game-theoretic → a scenario-design lever | `[C]` | 👁 | `TUNING_LOG.md` Runs 9-10 |
| **Divorce scenario design** — hand-author showcase for the pressure mechanisms after Path C lands | `[C]` | 👁 | pressure-mechanism cell |
| **Rationalize coalition-coercive representation** — the synthetic `coalition_formation` issue is partly redundant now that `coalition_values` is first-class; decide its shape during Path B | `[C][A]` | 🔀 | `scenarios/three_party_coalition_v1/` |

## Tier 2 — `[A]`/`[X]` infrastructure that serves the benchmark (open)

| Item | Tags | Loop | Detail |
|---|---|---|---|
| **Tournament / TurnBasedFlow harness** — multi-game round-robin with cross-game state, for tournament-style benchmark cells | `[A][C]` | 🔨 | `ARCH_flow.md`; `RESEARCH_NOTES.md` Note 2 Option D |
| **Reconciliation live validation** — status transitions + inconsistency flagging untested in live runs | `[C]` | 👁 | natural targets: α-squeezed / defection runs |
| **Identify-the-blocker tool** — pre-game analyst pass predicting the squeeze target; scenario-design aid | `[C][X]` | 🔀 | `tools/identify_blocker.py` (proposed) |
| **Provider-native structured output** (`response_format: json_schema`) — token-level schema compliance; current `structured_call` + retry works, so low priority | `[X]` | 🔀 | toolkit `llm_client` passthrough |
| **Pareto-frontier annotation in analyst output** — enumerate BATNA-clearing deals in intel; coaching-direction enhancement, lower priority under D-56 | `[C][B]` | 🔀 | analyst schema + prompt |

## Deferred (icebox)

Preserved, no new investment. **Coaching product (D-56):** coaching test loop on
Pi + Run 13b (`/revise:` + `/edits-summary` live exercise); game-platform
exploration (Clankmates / Discord transports); `TelegramReviewGate` as production
default; strategy routing (hardball / integrative / tit-for-tat library);
per-role model strategy (cost × quality × consistency per slot); persona tuning
(payment rigidity, long-horizon drift, endgame over-anchoring).
**Provider-consistency tests** (all-Anthropic BATNA baseline; cross-scenario
`gpt-4.1-mini` R3→R4 defection check) — finding consolidated in
`RESEARCH_NOTES.md` Note 3; tests would still yield benchmark-relevant data.
**Pressure mechanisms (unnumbered, deferred):** exogenous-events pressure
(mid-round shocks that recompute BATNAs); cascade scoring (cross-game state).
**Conversation-model evolution** (`ARCH_conversation_model.md` Stage 2a K-pass /
2b convergence / 3 async) — pursue only when a benchmark scenario class demands
within-round reactivity or timing-as-strategy.

## Where things live

- **Closed phases / runs** → `DEVLOG.md` · `DEVLOG_archive.md` · `TUNING_LOG.md`
  (+ `TUNING_LOG_archive.md`). No closed-items audit is kept here.
- **Findings / theses** → `RESEARCH_NOTES.md`: Note 1 (harness contribution =
  f(scenario shape, what the model already does well)), Note 2 (competitive vs
  cooperative scoring; Paths A/B/C), Note 3 (provider consistency as a deal
  variable).
- **Decisions** → `DECISIONS.md` (D-56 benchmark direction; D-58/D-59 scenario
  tooling).
- **Scoring framework** → `ASSESSMENT.md` (§3 lenses, §5 workstream tiers).
- **Scenario authoring** → `SCENARIO_GUIDE.md` + `ARCH_scenario_authoring.md`.
