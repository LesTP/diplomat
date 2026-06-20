# Diplomat

## Spark
> An **LLM negotiation benchmark** — a multi-model, multi-scenario evaluation harness that measures negotiation skill across model classes. Originally scoped as an AI faction agent coached by a human operator through a review gate; pivoted 2026-06-16 to the benchmark direction per DECISIONS D-56 after Runs 14, 15, 16, 17 produced *de facto* benchmark work surfacing the agreeableness-bias problem in the coaching framing.

## What This Is
A modular self-play harness for measuring how LLMs negotiate. Multi-agent games run with configurable scenarios (single-Pareto, multi-Pareto, coalition-coercive, pressure-augmented), arbitrary provider/model assignments per faction (`--per-faction-providers`), and optional harness ablation (`--bare-prompt`). The post-game scoring layer produces a battery of metrics — BATNA-relative outcomes, Pareto efficiency, vs-naive baselines, process signatures — across full × bare × model-tier matrices that surface differential negotiation behaviors (strategic refusal, balanced-consensus coordination, stuck-but-engaged failures, etc.).

The coaching product (live Telegram games via `OperatorReviewGate`, coached self-play, persona drift management, real-game deployment) is **deferred**: infrastructure stays in tree but no new investment until benchmark milestones land. Runs 1-13 produced the foundational findings (extraction → reconciliation → analyst → BATNA pressure → provider consistency) under coaching framing; that work seeded the benchmark direction.

## Audience
**Primary:** Researchers comparing model classes on adversarial / coordination / mixed-motive negotiation tasks. The benchmark produces ranked outcomes across (model × scenario × harness-mode) cells. Decisions like "which OpenRouter reasoning model exhibits strategic refusal on single-Pareto" or "does harness compensate for model tier on multi-Pareto" are first-class questions.

**Secondary:** The operator (still relevant for benchmark design — scenario authoring, spec tuning, picking the model matrix). The operator role shifts from "play one faction in a real game" to "design the experimental campaign and read the results."

## Scope

### Core (benchmark direction)
- Self-play multi-agent harness (`GameEnvironment`, `RoundSteppedFlow`) with configurable per-faction providers and bare-mode toggle
- Scenario compiler: narrative description → scored persona files with point tables, BATNAs, deception tactics, pressure metadata, game-mode classification (`src/scenario_authoring/scenario_compiler.py`)
- Reverse scenario builder: `ScenarioSpec` → fitness-search → committed scenario_analysis.json (`src/scenario_authoring/scenario_builder.py`)
- Post-game scoring: BATNA-relative, Pareto efficiency, vs-naive baselines, process signatures, near-miss diagnostic
- Pre-game tooling: probe_providers, dry-run, verify_scenario_optimum
- Multi-provider integration: OpenAI, Anthropic, Google (Gemini), OpenRouter (DeepSeek V3/R1, Llama, Qwen, etc.) — all via `toolkit/llm_client`
- Cost governance via toolkit/cost_accountant
- Append-only event store + structured state manager with schema-validated patches and audit log (preserves transcript + state for post-hoc analysis)
- LLM-based extraction, reconciliation, dual-provider analyst with divergence detection (the "full harness" arm of bare-vs-full ablation)
- Pipeline configuration via single YAML file

### Flexible (benchmark)
- [in] Path B coalition-exclusion scoring engine (NEXT_STEPS §11) — extends scenario schema with `coalition_values`, modifies `score_game()` to detect partial-agreement coalitions
- [in] Rank-based scoring lens (`rank_among_factions`) for mixed-model populations
- [in] Scenario library expansion: distributive bargaining, asymmetric-BATNA-with-walkaway, hidden-value bluff, Susskind coalition variants
- [in] Phase 41/42 scale-matrix verification → 4+ factions / 4+ issues scenarios
- [in] Phase 39 exogenous events (mid-round shocks recomputing BATNAs)
- [deferred] Tournament harness (multi-game round-robin with position rotation; cross-game state) — Phase 40 candidate, promote when benchmark scale demands it

### Deferred (coaching product — infrastructure preserved, no new investment)
- TelegramBotTransport / TelethonUserTransport for live game I/O
- `OperatorReviewGate` (`/approve`, `/edit`, `/revise:`, `/block`)
- Coaching feedback loop on Pi
- ClankmatesTransport for game platform
- Persona drift management, persona payment rigidity A/Bs, endgame over-anchoring decisions
- Coached self-play (Run 13b queued)
- Edit classifier production usage (toolkit primitive stays; production wiring deferred)

### Exclusions
- Not a general-purpose chatbot or assistant
- No local inference — all LLM calls are API-based
- No real-time voice or video interaction
- No multi-game state persistence (Phase 40 cascade scoring — indefinitely deferred until tournament-style use case)

## Constraints
- **Hardware:** Raspberry Pi 4 (4GB min) or Pi 5 (8GB recommended) for the deployed harness; benchmark campaigns also run from operator laptops via SSH
- **OS:** Raspberry Pi OS Lite 64-bit (Pi); macOS/Windows (operator)
- **Language:** Python (async)
- **Persistence:** SQLite with WAL mode, single file per agent
- **LLM inference:** API-based via toolkit/llm_client (Anthropic Claude, OpenAI GPT, Google Gemini, OpenRouter)
- **Cost governance:** toolkit/cost_accountant with per-round and per-session budgets
- **Shared dependencies:** toolkit project (llm_client, structured_llm, cost_accountant, telegram_client, coaching, edit_classifier)
- **No monorepo tooling:** Each module has typed interfaces, wired by the Pipeline/Flow composition layer

## Prior Art
- **Phosphene** (sibling project) — autonomous personality-driven agent on Pi. Shares toolkit dependencies, similar module architecture.
- **Codexbot** (sibling project) — Telegram bot wrapping Codex. Shares toolkit/telegram_client, similar State Store pattern.
- **Clanker Courts** (sibling project, queued) — multiplayer game built around AI faction agents; potential real-game venue if the coaching direction revives.
- **Generative Agents (Park et al.)** — memory stream + reflection for believable agents. Relevant: structured memory and reflection.
- **AI Diplomacy (Meta CICERO)** — state-of-the-art AI for Diplomacy board game. Different scale (full board game AI with planning), same domain of strategic communication and trust modeling.
- **Negotiation literature** — Harvard PON exercises (Harborco, Three-Party Coalition, Chestnut Village), Susskind coalition values, Nash bargaining. Source catalogue in `Multi-Party Negotiation Scenarios.md`.

## Success Criteria (benchmark direction)
- The harness produces deterministic, reproducible outcomes across (model, scenario, mode) cells — same seed + same config → same scoring outputs
- Multi-model populations produce rank-discriminating outcomes on at least one scenario class (validates Note 2 Path A/B/C — required before "X model wins" claims are meaningful)
- Scoring lenses surface meaningful differentiation across at least 5 distinct behaviors observed to date: strategic refusal, balanced-consensus coordination, stuck-but-engaged convergence, identity-confusion failure, BATNA-floored deadlock
- Scenario library covers at least 4 axes: BATNA-Pareto gap, Pareto count, coalition coerciveness, pressure profile (with reverse builder validating each spec mechanically)
- Reverse scenario builder scales to 4+ factions / 4+ issues (Phase 41/42)
- Per-cell run cost is predictable and bounded — no toolkit-side bugs (e.g., empty-content retry loops) silently burn budget
- Campaigns produce findings that survive cross-model and cross-scenario testing (the Note 1 / Note 2 framings continue to evolve with data)

> **What "negotiating well" means + how we score it.** Conceptual rationale (calculation-vs-negotiation tension, dimensions of skill, four scoring lenses, scenario properties) and the workstream organization (A: agent architecture & memory, B: prompt tuning, C: game creation & scoring) live in `ASSESSMENT.md`. Under D-56, Block C is the primary investment surface; Block B demotes; Block A stays infrastructure.

## MVP Definition

**Benchmark MVP** (effectively achieved as of Runs 14/16/17 — what remains is expansion):

| Surface | MVP Scope | Status |
|---|---|---|
| Self-play harness | `GameEnvironment` + `RoundSteppedFlow` + `--per-faction-providers` | ✓ Operational |
| Scenario authoring | `scenario_authoring.scenario_compiler` + `scenario_authoring.scenario_builder` (3×3×3 validated) | ✓ Operational |
| Scoring | BATNA-relative, Pareto efficiency, vs-naive baselines, 5 process signatures | ✓ Operational |
| Multi-provider | OpenAI, Anthropic, Google, OpenRouter (incl. reasoning models post-toolkit `606e309`) | ✓ Operational |
| Ablation | Bare-mode toggle (Phase 34) | ✓ Operational |
| Pre-flight | probe_providers, dry-run, verify_scenario_optimum, verify_dryrun | ✓ Operational |

**Benchmark v2 (gating)** — items required before the harness produces *competitive* (rank-discriminating mixed-model) outcomes:

| Surface | v2 Scope | Status |
|---|---|---|
| Coalition-exclusion scoring | Path B per Note 2 — `coalition_values` schema, `score_game()` partial-agreement detection | Queued |
| Rank-based scoring lens | `rank_among_factions` per ASSESSMENT §3.5 | Queued |
| Mixed-model dispatcher | `ablation_multi.sh` extension for heterogeneous lineups + position rotation | Queued |
| Adversarial-scoring scenario class | Distributive / asymmetric-BATNA / hidden-value scenarios | Queued |

### Coaching product MVP (achieved, deferred for further work)
The original coaching MVP closed Phases 1-33. `OperatorReviewGate`, coached self-play, `/revise:`, edit classifier, telegram chunking, lazy-fetch — all operational. Run 13 (coached, all-Gemini-flash, Water Rights symmetric) validated the gate end-to-end. Run 13b queued and deferred per D-56.

## Risks and Open Questions
- [closed] **Bot vs. user accounts** — `TelegramBotTransport` operational; Telethon deferred indefinitely under D-56
- [closed] **Structured output enforcement** — Phase 2 (Extraction handles via prompt + parse + jsonschema)
- [closed] **Debounce strategy** — Phase 18 + Phase 22
- [closed] **Review gate timeout** — Phase 9 (configurable auto-block)
- [watch] **Benchmark coverage breadth** — current matrix has 5 models × 2 scenarios. Path to "credible benchmark" needs ~10 models × ~6 scenarios at n≥3 = ~$50-150 per full sweep. Cost governance becomes important.
- [watch] **Coalition-exclusion scoring complexity** — Path B is the load-bearing v2 build. Estimated 1-2 days; could be larger if `RoundSteppedFlow` partial-agreement detection turns out to require schema work beyond `coalition_values`.
- [watch] **Reasoning model wiring on OpenRouter** — toolkit `606e309` fixed the empty-content fallback for non-OpenAI reasoning backends; future reasoning models (o5, Gemini-thinking, Qwen reasoning variants) may need per-model probing.
- [deferred] **Game platform** — Clankmates / Discord transports are now coaching-direction concerns. Revisit if D-56 trigger condition (a) fires.

## Extension Points
- New Transport implementations (Discord, Matrix, CLI variants) — additive
- New LLM providers via toolkit/llm_client — provider-side; no Diplomat code changes
- New Flow implementations (TurnBasedFlow, tournament round-robin) — additive against the Pipeline contract per ARCH_flow.md
- New scoring lenses — add to `tests/self_play/game_environment.py::score_game` + rendering in `tests/self_play/analysis.py`
- New scenario classes — author via `scenario_authoring.scenario_builder` with a `ScenarioSpec` targeting the desired property profile
- Post-game replay and analysis from the append-only event store + state_change_log + per-run JSON

## Size Estimate
Multi-module. 12 core pipeline modules with defined interfaces, single Pipeline/Flow composition layer, plus `src/tools/` (scenario compiler + scenario builder + scenario fitness) and `tests/self_play/` (GameEnvironment, bare-mode helpers, coached_game.py, probe/verify tooling, ~35 tests). Self-play infrastructure is now the primary surface. Coaching infrastructure preserved but no longer the investment frontier.

---

## Change History
| Date | What Changed | Why |
|------|-------------|-----|
| 2026-05-24 | Initial PROJECT.md created from diplomat-system-spec.md v0.5 | Project setup |
| 2026-05-27 | Closed Orchestrator implementation risks for debounce/review timeout and clarified round-structure deployment watch | Phase 11 close |
| 2026-06-16 | **Direction pivot to negotiation benchmark per D-56.** Spark / What This Is / Audience / Scope / Success Criteria / MVP Definition all reframed around benchmark use case. Coaching product items moved to "Deferred" (infrastructure preserved, no new investment). Risks section updated. Original coaching framing preserved in Change History for context. | Operator decision after consolidation discussion 2026-06-16 — Runs 14-17 were *de facto* benchmark work under coaching framing producing thrashing pattern. Per `RESEARCH_NOTES.md` Note 2 + D-56. |
