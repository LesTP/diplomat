---
phase: 49
blocked: false
state: execute
steps_remaining: 0
---

# Diplomat — Development Plan

<!-- This file is the primary state document for cold-start sessions.
     Workers read it on every cold start to determine what to do next.
     Keep it concise — the DEVPLAN should get SHORTER as work progresses.

     For autonomous projects, the frontmatter includes a `state` field:
       state: plan | execute | review | close
     See WORKER_SPEC.md for state-machine semantics.

     `steps_remaining` is managed by the state machine at runtime — do NOT
     pre-populate.

     PHASE PLAN FORMAT (the PLAN action writes this shape into DEVPLAN):

       ## Phase N: <title> — In Progress

       **Goal.** <one paragraph>
       **Steps.**
       - [ ] N.1 — <first build step>
       - [ ] N.2 — <second build step>
       - [ ] N.3 — <doc update step>
       - [ ] N.4 — <phase close step>

     Each checkbox is one EXECUTE iteration. The state machine sizes the
     remaining work by counting `^- \[ \]` lines inside the `## Phase N`
     section. Read from `tools/state_machine.sh:count_unchecked`.

     This example block sits above any `## Phase N` header (outside the
     sed-extraction range) and inside an HTML comment (so it doesn't
     render). -->

## Cold Start Summary

<!-- Stable section — update on major shifts, not every step.
     Gotchas: operational knowledge learned through trial-and-error.
     Prescriptive one-liners only. Historical narrative belongs in
     DEVLOG_archive.md, not here. -->

- **What this is** — AI faction agent for a multiplayer diplomacy game, with human coaching via Telegram review gate.
- **Key constraints** — Raspberry Pi deployment, all LLM calls via toolkit/llm_client, all Telegram I/O via toolkit/telegram_client, cost governance via toolkit/cost_accountant, SQLite persistence.
- **Gotchas** —
  - `toolkit` lives at `../toolkit` and must be installed editable per host (`<venv>/bin/python3 -m pip install -e ../toolkit`). Not declared in `pyproject.toml` (would be a misleading install contract — can't resolve from PyPI). Module-level tests use dependency-injected fakes; integration paths must exercise real `toolkit` imports.
  - Toolkit Phase 19 surface must import on the Pi: `from toolkit.llm_client import complete_with_retry` and `from toolkit.cost_accountant import normalize_model_name`. If ImportError, reinstall editable. See `SMOKE_RUNBOOK.md` §1.
  - **Pi deployment mechanism:** `incus exec claude-code -- bash /home/claude/workspace/diplomat/tools/service.sh start` is the canonical bot start command. `tools/service.sh` uses a `diplomat` window in the long-lived `bot` tmux session under the hood; override the session with `BOT_TMUX_SESSION` for tests or parallel deployments. See `CLI_REFERENCE.md` and `diplomat-testing-doc.md` §5b.
  - Bot vs. user account: must be resolved with game moderator before deployment. Implement `TelethonUserTransport` only if bot-to-bot is blocked.
  - Round structure (signal vs. time-based): confirm with moderator before deploying; set in `pipeline.yaml`.
  - **Telegram bot-to-bot platform limitation:** Telegram does NOT deliver bot-sent messages to other bots in groups, regardless of privacy mode. Non-operator faction-traffic in any Telegram-side test requires either a 2nd human Telegram account on another device, or a temporary de-op cycle (remove operator's user ID from `DIPLOMAT_OPERATOR_USER_IDS`).
  - **Debounce strategy:** per-event task set (each game message gets its own extraction task; no cancellation between different messages). The original cancel-and-replace design silently dropped messages in multi-message bursts.
  - **Cost governance:** CostAccountant wired through `ToolkitLLMAdapter` — every LLM call routes through `accountant.complete()` for budget-check + ledger write. `DiplomatCostGate` provides the check-before-call pattern for round-level budget control. Both share the same accountant instance.
  - All four LLM modules (extraction, analyst, adversarial, generation) use `toolkit.structured_llm.structured_call()` for schema-enforced JSON with retry-on-validation-failure.
  - Self-play cost ledger uses a local temp path (`%TEMP%/diplomat_selfplay/`) to avoid UNC path issues on network shares.
  - **Cross-provider JSON formatting:** Anthropic and Google wrap JSON in ` ```json ... ``` ` Markdown fences regardless of explicit "raw JSON" instructions. OpenAI returns raw. Toolkit's `parse_json_response` strips a single surrounding code fence; without this, structured_call's retries silently exhaust.
  - **Self-play env loading:** `tests/self_play/run_simulation.py` calls `load_dotenv()` at module top. Subprocess SDKs (Anthropic, Google) need this — only `OPENAI_API_KEY` was reliable from parent shell otherwise.
  - **Probe before live multi-provider runs:** `python -m tests.self_play.probe_providers --providers '<same JSON as --per-faction-providers>'` hits each provider once with a trivial request (~$0.001 total). Catches API keys, fence wrapping, model-name typos that `DryRunLLMClient` can't catch (DryRun replaces the LLM client entirely with canned responses).
  - For **Gemini 2.5 flash / pro**, set `--max-tokens 500` or higher on probes — thinking-mode consumes output tokens before producing visible content. `gemini-2.5-flash-lite` has no thinking mode and is the tuning default.
  - **Per-faction provider routing:** `--per-faction-providers '{"alpha":{"provider":"openai","model":"gpt-4.1-mini"},...}'` varies only the Generator per faction; other modules stay on shared primary/secondary. Verify with `verify_dryrun --expect-providers '{"alpha":"openai",...}'`.
  - **Pre-compiled analysis loader:** `--analysis-json <path>` skips live LLM compilation and loads a pre-edited analysis JSON (preserves hand-tuned BATNAs, scoring, deception tactics). Requires `--scenario` for the seed-message text.
  - **Prompt regression runner:** `_judge_response_text()` JSON path extraction must be wrapped in try-catch — if a scenario's `path` doesn't exist in module output, raw KeyError crashes the runner.
  - **Production reconciler is wired** in `src/main.py` via `_attach_reconciler` using primary provider's commodity tier; fires at every round boundary before analysts. Self-play harness has its own per-faction wiring that overrides.
  - **`game.total_rounds` optional config** in `pipeline.yaml` — when set, `Orchestrator.__init__` reads it and the persona's PENULTIMATE / FINAL ROUND markers fire. Unset = production stays endgame-blind (correct default when round count is unknown).
  - **Follow `RUN_PROTOCOL.md` for any live multi-agent run** (define inputs → verify scenario → probe providers → dry-run plumbing → run live → verify output → document). Skip rules and abort conditions are spelled out.
  - **Canonical docs at project root:** `ASSESSMENT.md` (skill framework + 4 scoring lenses + 3 workstream blocks A/B/C; tagged in NEXT_STEPS), `CLI_REFERENCE.md` (every CLI entry point), `SMOKE_RUNBOOK.md` (Telegram coaching/review smoke procedure), `RUN_PROTOCOL.md` (self-play pre-flight), `TUNING.md` (BATNA + provider defaults + prompt-tuning practice), `TUNING_LOG.md` (run-by-run record), `NEXT_STEPS.md` (forward backlog + 🔨/🔀/👁 loop-readiness classification).
  - **Reference docs to keep in sync** — see CLAUDE.md / CODEX.md "Reference Docs to Keep in Sync" section. Each Build phase's step list includes an explicit "doc update" step before phase-review naming the affected docs.
  - **`pareto_distribution_spread` ? "deals favor different factions":** `pareto_distribution_spread` measures per-faction frontier-range stdev (intra-faction uniformity). "Do different deals favor different factions?" is `pareto_outcome_diversity` (Phase 37). The spec author misread this in Phase B, causing a 3m27s wasted search run (Phase 36.5). When authoring a `ScenarioSpec`, double-check the metric definition in `CLI_REFERENCE.md` before setting a target value.
  - **Operator-supervised scenario-tooling reorg (2026-06-20/21):** scenario tools moved from `src/tools/` to dedicated `src/scenario_authoring/` package; scenarios data moved from `tests/self_play/scenarios/` to top-level `scenarios/`. `coalition_values` schema field added (Phase 2a). `verify_scenario_optimum` moved into the package (D-58). Public API curated in `__init__.py`. `tools/scenario_builder_scale_probe.py` characterizes builder convergence + wall-clock across F/I/O dimensions. Phase 42 algorithm work complete (PROJECT.md "4+ factions / 4+ issues" criterion MET at 4×4×4); see `DECISIONS.md` D-59 and commits `551caa9`..`8a384c3`.
  - **Codex backend loop failures (Phase 46):** Codex backend repeatedly failed to finish diplomat iterations due to turn/time limits or budget re-dispatch anti-pattern (iter 192 left work uncommitted; iter 196 committed but stalled on bookkeeping). Claude backend finished iterations cleanly. Recommend CLAUDE backend for diplomat loop runs, or raise codex turn/time budget. When codex stalls: verify committed work, fix bookkeeping manually, reset `steps_remaining` to empty, re-dispatch.
## Current Status
- **Phase 49 QUEUED (loop-ready, 2026-06-27):** Per-run cost capture + approximate backfill — pure offline build, zero API cost (Option A scalar `metadata.cost_usd`; design in DEVLOG / this phase). Frontmatter armed (`phase:49`, `blocked:false`, `state:plan`); dispatch on the Pi. First of the Paper 1 §5.0 hygiene batch (cost capture → bootstrap-CI aggregator are the two loop-safe builds; see `papers/PAPER_PLAN.md` §5.0 + §8).
- **Operator-supervised session (2026-06-26):** Live-tested `succ3b` (Run 21, homogeneous bare baselines): **headroom confirmed** - deepseek 0/3 vs sonnet 2/3, so succ3b discriminates capability. Failure mode = gamma over-grab (kingmaker takes both assets, starves the heartland loser); possible alpha seat-bias (n=2). See `TUNING_LOG.md` Run 21. Plus a deal-explorer **viz polish pass** (faction-colored headers + dynamic payoff-not-share caption, bars-beside-parcoords aligned/widened layout, live ternary surplus readout, clickable parcoords/ternary; D-63 viz contract, locked by `tests/test_scenario_viz.py`). Viz consolidated 2026-06-27: all four deal-explorers now live in their scenario folders as `deal_explorer.html` (`tools/build_viz.py` is the regen-all driver). Next: single-provider tier ladder, seat-rotated.
- **Operator-supervised session (2026-06-25):** autonomous-loop tooling COMPLETE - Phases 46/47/48 ran on the claude backend (two codex-cutoff recoveries; see DEVLOG). Authored discriminating scenarios `succ-v3` + `succ3b` (brief-passing, awaiting live test; tags `succ3`/`succ3b` in `tools/ablation_multi.sh`). Fixed + locked the deal-explorer viz layout (D-63). Loop is PARKED (frontmatter `blocked:true`/`state:close`); the autonomous roadmap is exhausted and remaining work is supervised - see `NEXT_STEPS.md`.
- **Phase** — Phase 48 complete (narrative re-skin shell; 37 new tests, D-62 closed; see `DEVLOG.md` "Phase 48 close"). Phase 47 complete (coalition scoring contract lock; 23 unit tests, D-61 closed; see `DEVLOG_archive.md` "Phase 47 close"). Phase 46 complete (standalone `scenario_authoring` + unified CLI; see `DEVLOG_archive.md` "Phase 46 close"). Phase 44 complete (scenario design-brief + verify-against-brief + auto-doc). Scenario-design (succ-v3 / Path C) and benchmark-run backlog live in `NEXT_STEPS.md`.
- **Phase numbering note:** 45 is intentionally unused — the roadmap's narrative phase was staged as Phase 48 after standalone (Phase 46) was chosen first; the coalition track slotted in as Phase 47. Gaps are normal here (40/41/42 were operator-supervised); the state machine keys on the `phase:` frontmatter value, so the gap is harmless. Supervised work outside the loops lives in `NEXT_STEPS.md`.
- **Phase B (proof-of-concept scenario):** Joint Space Mission scenario authoring unblocked. v1 spec produces 3 Pareto-optimal deals with distinct distributions (balanced consensus / alpha+gamma win / beta wins). Next operator session: run the LLM scenario compiler over the generated `scenario_analysis.json` to produce narrative + persona prose, then optionally smoke at flash-lite.
- **Operator-supervised work (2026-06-21): Phase 42 COMPLETE.** Commits 1-4 + C5a + C5b landed (`551caa9`, `257b1e0`, `d16248c`, `4c67abb`, `19e6a39`, `8a384c3`). PROJECT.md "4+ factions / 4+ issues" success criterion MET: 4×4×4 / D=256 reaches ≥2/3 probe acceptance, locked by `tests/test_scenario_builder_scale.py::test_builds_4x4x4_in_budget`. Key findings: the I-axis cliff was spec-semantic (fixed by C5a relative `batna_clearing_count_target`), and a builder determinism bug (C5b) had masked it; SA neighborhood broadening was tried and rejected (D-59). Phase 3 (scale probe) data at `scenarios/scale_probe_*` + `scenarios/c5b_final_singlecell_summary.md`. Phase 4 docs (`ARCH_scenario_authoring.md`, `SCENARIO_GUIDE.md`) shipped and updated with post-Phase-42 scaling data.
- **Operator-supervised work (2026-06-22): section 3.5 competitive-scoring benchmark built + pushed.** Per-game `faction_ranks` rank-among-factions lens + `faction_models` persistence + cross-game `mean_rank` aggregator (`tests/self_play/rank_aggregator.py`) + mixed-model dispatcher + position-rotation harness in `tools/ablation_multi.sh`. Three scoring bugs fixed (partial-coalition deal_reached normalization, below-BATNA deal rejection, aggregator no-deal filter). Runs 18-20: gpt-5.5 broke the section 10 tier/provider confound; Runs 19-20 (succ / succ2 distributive scenarios) showed the section 3.5 tooling works but no scenario yet *discriminates* - open gap is discriminating scenario design (sweet-spot for model-comparison vs bare-deadlock-headroom for the harness question; see `NEXT_STEPS.md` "State as of 2026-06-22"). Both repos (toolkit, diplomat) pushed to GitHub.

## Phase 49: Per-run cost capture + approximate backfill — In Progress

**Goal.** Populate a `metadata` block in self-play result JSONs with the per-run
LLM spend — sourced live from the shared `CostAccountant` going forward, and
re-estimated offline for historical runs — so Paper 1's cost-economics ($/closed-deal)
and per-cell cost-coverage stop being back-of-envelope. Pure offline build:
fully fake/dry-run testable, **zero API cost** (the live capture reads an
already-computed total; the backfill re-prices existing logs). Scope is Option A
(scalar total only) per the 2026-06-27 design discussion — by-model/by-operation
breakdown (`report(since=...)`) and per-faction attribution are deliberately out
of scope (not a Paper 1 need; per-faction served the D-56-deferred per-role-model
strategy). Schema is forward-compatible so those can extend `metadata` later
without a breaking change.

**Metadata schema** (new top-level `metadata` block in each result JSON):
`{"cost_usd": <float>, "cost_source": "metered" | "estimated_from_log" | "dry_run", "n_llm_calls": <int>}`.

**Steps.**
- [x] 49.1 — Emit cost metadata on the live path. Thread the shared `accountant`
  (already in `_run()` scope) into `_write_results` in
  `tests/self_play/run_simulation.py`; write
  `results["metadata"] = {"cost_usd": accountant.session_total, "cost_source": "metered", "n_llm_calls": len(results.get("llm_call_log", []))}`.
  Dry-run path (FakeCostAccountant injected) writes `cost_source: "dry_run"`.
- [x] 49.2 — Make it fake-testable + add the test. Extend `FakeCostAccountant`
  (`tests/helpers/factories.py`) with a `session_total` property (currently
  missing). Add a unit test asserting the `metadata` block is written with the
  correct fields/values via the fake / dry-run path — no live API.
- [x] 49.3 — Add `tools/backfill_cost.py` (sibling to `backfill_pareto.py` /
  `backfill_scoring_metrics.py`). For each historical result, re-estimate cost
  from `llm_call_log` (token ≈ len(text)/4 over messages + response, priced via
  `CostAccountant.estimate_cost` for pricing consistency) and write `metadata`
  with `cost_source: "estimated_from_log"`. Idempotent: skip runs already
  carrying `cost_source: "metered"`. Unit test on a synthetic result JSON.
- [ ] 49.4 — Run the backfill over `tests/self_play/results/*.json`; spot-check a
  couple of cells against `TUNING_LOG.md` back-of-envelope figures (sanity, not
  exactness — these are estimates); commit the updated result JSONs.
- [ ] 49.5 — Doc update: `NEXT_STEPS.md` (move "Per-run cost capture" out of the
  open Tier-1 list / mark done), `ASSESSMENT.md` §5 Block C tech-debt (drop the
  `metadata.cost_usd: None` / stale-ledger line), `CLI_REFERENCE.md` (document
  `tools/backfill_cost.py` + the `metadata` schema), `papers/PAPER_PLAN.md` §5.0
  (mark cost-capture done).
- [ ] 49.6 — Phase close: full suite green; DEVLOG entry; DECISIONS entry for the
  `metadata` schema + `cost_source` semantics; set DEVPLAN frontmatter to close.

**Build notes / gotchas** (not iteration steps):
- **One game per process.** `run_simulation._run()` runs exactly one
  `env.run_game()` and writes one result file, so `accountant.session_total` at
  write time is exactly that run's spend — no ledger windowing / `report(since=)`
  needed. Do NOT total the on-disk `cost_ledger.jsonl` (append-only, cumulative
  across runs → the "stale ledger" trap). If any *other* entrypoint
  (e.g. `coached_game.py`) ever batches multiple games in one process, it must
  reset `session_total` per game before this metadata is trustworthy there.
- **Backfill model resolution.** `llm_call_log` entries carry `config_provider`
  + `tier` + text, not a resolved model name. Resolve the model for pricing from
  `faction_models` (bare mode: every call is the faction's generator model) and
  the pipeline primary/secondary defaults (full mode: module calls). Treat the
  result as an estimate — that's exactly what `cost_source: "estimated_from_log"`
  signals; don't claim false precision against `session_total`.
- **Accuracy bound.** `cost_usd` is only as accurate as toolkit/cost_accountant's
  pricing table at run time; the downstream pricing audit (`NEXT_STEPS.md`)
  tightens it. Document this caveat where the schema is described.
- **Loop-readiness:** 🔨 pure build, fake/dry-run testable, zero API cost — safe
  for the autonomous loop (runs on the Pi per the Windows sandbox limit; gates at
  phase close).

## Phase 46: Standalone scenario_authoring + unified CLI — Complete

Closed 2026-06-25. `round_context.py` leaf (stdlib-only) created inside the package to sever the lone `scenario_compiler.py → modules.persona` load-time coupling; `modules/persona` re-exports `CoachingContext` + `render_round_context_section` for back-compat. Standalone contract locked by `tests/test_scenario_authoring_standalone.py`. Unified `python -m scenario_authoring build|compile|verify|brief` CLI added in `__main__.py`. Package README written. D-60 closed. 559 tests passing. See `DEVLOG_archive.md` "Phase 46 close".

## Phase 47: Coalition scoring — lock the Path B contract — Complete

Closed 2026-06-25. 23 unit tests lock `_find_coalition_value` + `_resolve_deal_scores` across all paths (partial coalition, grand coalition full-agreement path, no-deal, below-BATNA, malformed-input edges). `ARCH_scenario_authoring.md` updated with coalition Path B contract section. D-61 closed. 583 tests passing. See `DEVLOG_archive.md` "Phase 47 close".

## Phase 48: Narrative-integration shell — Complete

Closed 2026-06-25. `scenario_narrative.py` module: `apply_relabel` (bijective identifier relabeling, numeric values preserved) + `assert_structure_preserved` (value-isomorphism guard) + `extract_catalogue_entry` (heading-scoped catalogue slicer) + `reskin_scenario` (one `structured_call` → relabeled analysis + themed prose) + `main()` CLI. Wired into `scenario_authoring` package API and `narrative` subcommand. 37 new tests. D-62 closed. 620 tests passing. See `DEVLOG.md` "Phase 48 close".

## Phase 44: Scenario design-brief + verify-against-brief + auto-doc — Complete

Closed 2026-06-25. New `scenario_authoring.scenario_brief` module:

Closed 2026-06-25. New `scenario_authoring.scenario_brief` module: `load_brief` + `check_brief` (6 structural features: constant_sum, priority_collision, no_focal_point, winner_spread, batna_clearing_count, no_exact_ties) + `build_brief_readme` auto-doc + CLI. `--brief` wired into `verify_scenario_optimum` (focal-deal helper extracted + reused); `--viz` added to `scenario_compiler`. Golden briefs for `succ`/`succ2` prove the gate catches Run 19 (focal point) and Run 20 (deadlock). Public API exported; docs synced. 555 tests passing. See `DEVLOG.md` "Phase 44".

## Phase 43: Integrate deal-explorer viz into scenario_authoring — Complete

Closed 2026-06-23. `scenario_authoring.scenario_viz` module created; deal-explorer renderer moved from `tools/viz.py` (now a run-discovery wrapper); `--viz` wired into `verify_scenario_optimum` and `scenario_builder`; public API exported; docs synced. 535 tests passing. See `DEVLOG.md` "Phase 43 close".

## Phase 39: Scenario compiler `--fill-narrative` mode — Complete

Closed 2026-06-11. `scenario_authoring.scenario_compiler` now has permanent `--fill-narrative-only` and `--domain-context-file` support via `fill_narrative()`, and the temporary helper was removed. See `DEVLOG.md` "Phase 39 close".

## Phase 38: Pressure mechanisms small bundle — Complete

Closed 2026-06-11. Pressure mechanisms shipped as a small bundle: round-cost decay, asymmetric clocks, penalty floor, pressure-profile metadata, and pressure-aware final-round BATNA wording. See `DEVLOG.md` "Phase 38 close".

<!-- Closed phases only: newest first. -->

<!-- history -->

## Phase 37: Add `pareto_outcome_diversity` metric — Complete

Closed 2026-06-11. Added `pareto_outcome_diversity` metric to `src/scenario_authoring/scenario_fitness.py` (distinct-winner-fraction: `distinct_winners / min(frontier_size, n_factions)`) and `pareto_outcome_diversity: float = 0.0` field to `ScenarioSpec` in `src/scenario_authoring/scenario_spec.py`. 5 new unit tests. Updated `joint_space_mission_v1/spec.json` with `pareto_outcome_diversity: 0.66`. `CLI_REFERENCE.md` updated with side-by-side metric cross-reference (intra-faction-uniformity vs inter-deal-diversity). VERIFY PASSED; 435→440 tests. See `DEVLOG_archive.md` Phase 37 close.

<!-- history -->


## Phase 36: Scenario Builder Search Improvements — Complete

Closed 2026-06-11. Shipped four algorithm improvements to `src/scenario_authoring/scenario_builder.py`: structured per-restart logging + `--debug-search` flag (36.1), weighted fitness budget + `target_weights: dict[str,float]` on `ScenarioSpec` with categorical-default weight 0.3 (36.2), simulated annealing `_anneal_local` replacing greedy flip loop (36.3), seeded initialization biased toward spec-requested categorical structure (36.4). Validation on `scenarios/joint_space_mission_v1/spec.json` PASSED in 3.6s after operator investigation revealed a misspecified `pareto_distribution_spread` target; spec fixed with `target_weights: {pareto_distribution_spread: 0.0}` (36.5). 9 new tests; 426→435 total. Reference docs updated in 36.6; DEVLOG close in 36.7. See `DEVLOG.md` Phase 36 close. Phase 37 queued (operator-gated): add `pareto_outcome_diversity` metric.

<!-- history -->

## Phase 35: Reverse Scenario Builder — Complete

Closed 2026-06-10. Shipped `src/scenario_authoring/scenario_builder.py`: constraint-driven reverse scenario generator. Operator writes a `ScenarioSpec` (Pareto count target, distribution spread, BATNA gap, logrolling requirement, asymmetric BATNAs); tool searches scoring-table space via random-restart hill-climb and emits `scenario_analysis.json` + per-faction `.txt` personas via the existing compiler helpers. `logrolling` and `deception_tactics` emitted as stubs for operator hand-authoring. CLI: `python -m scenario_authoring.scenario_builder --spec <spec.json> --output-dir <dir> --verify`. 6 new files (3 source, 3 test); 12 new tests; 426 total (up from 414). See `DEVLOG.md` Phase 35 close.

<!-- history -->

## Phase 34: Bare-prompt mode — Complete

Closed 2026-06-08. Bare-prompt ablation mode shipped as a self-play-only toggle: `tests/self_play/bare_mode.py`, `DefaultContextAssembler.assemble(bare_mode=True)`, `GameEnvironment(bare_mode=True)`, and `run_simulation.py --bare-prompt`. The mode disables Extraction, Analyst, Divergence, Reconciliation, Adversarial, and Coaching while preserving Persona + raw transcript + Generation, was smoke-tested live, and is documented in `DEVLOG.md` and the architecture/reference docs. See `DEVLOG.md` Phase 34 close and `NEXT_STEPS.md` §10 for the queued Run 14a-14f ablation series.

<!-- history -->

## Phase 32: Toolkit-level TG chunking + Diplomat cleanup + queue-drain + /intel trim — Complete

Closed 2026-06-04. Pushed Telegram message chunking down to `toolkit/telegram_client` — `TelegramClient.send_message` auto-chunks oversized text via the upgraded paragraph-first `split_message` (with `[continued ...]` markers); `CONTINUATION_PREFIX` constant exported. Diplomat's local `chunk_text` helper removed; `OperatorReviewGate._send_draft` / `_send_section` simplified to single-send compose. `CoachedGameEnvironment._listen_for_operator` now drains pending TG updates on startup (1s window) so stale `/approve`-style commands from previously-killed sessions can't auto-resolve R1. `/intel` operator command trimmed to the latest intelligence row (compact summary: faction, round, threat level, leverage, risks) instead of dumping every row's full JSON. Decisions D-46 (toolkit-level auto-chunking) and D-47 (coached-game startup drain window). Steps 32.1 + 32.2 (operator-driven shared toolkit changes) + 32.3-32.6 (autonomous loop, Diplomat cleanup + tests + docs) + 32.7 (cross-project NEXT_STEPS notes skipped — operator clarified NEXT_STEPS.md is a Diplomat-specific convention, knowledge preserved in toolkit docs + Diplomat DEVLOG/DECISIONS). See `DEVLOG.md` "Phase 32 close" + `TUNING_LOG.md` Run 13 (the run that surfaced the queue-staleness + /intel issues).

## Phase 31: Transport-routed OperatorReviewGate — Complete

Closed 2026-06-04. Shipped `OperatorReviewGate` (transport-based, chunked, lazy `/reasoning` + `/adversarial` fetch, command pass-through via `Pipeline.dispatch_operator` → `handle_command`). Hard rename from `TelegramReviewGate`. `chunk_text` helper added to `src/modules/review_gate/chunking.py`. Decisions D-39 through D-43. 370 tests passing on Linux Pi.

**Phase 31a hotfix (same session):** `CoachedGameEnvironment` operator-input bridge — `RoundSteppedFlow` lacked the `EventDrivenFlow.process_event` routing that the new passive gate relies on, so coached games hung at the first review prompt. Added `_listen_for_operator(tg_transport, pipeline)` that consumes the wrapped `TelegramBotTransport.listen()` and forwards operator-tagged events to `dispatch_operator`. Decision D-44.

Validated end-to-end via Run 13 (first coached game with new gate, all-Gemini-flash on Water Rights symmetric). Run 13 surfaced two follow-up items now queued as Phase 32: (a) operator command responses also need chunking (`/intel` silently dropped at oversize), and (b) the listener should drain stale TG-queue updates on startup so a previously-killed session can't poison R1 of the next session. See `DEVLOG.md` "Phase 31 Close" + "Phase 31a hotfix" + `TUNING_LOG.md` Run 13 for details.


## Phase 30: OpenRouter provider connector — Complete

Closed 2026-06-03. Added `OpenRouterProvider` to `toolkit/llm_client/providers.py` (subclasses `OpenAIProvider` with `base_url="https://openrouter.ai/api/v1"`), wired factory dispatch, added `OPENROUTER_API_KEY` env mapping in `tests/self_play/run_simulation.py`, added OpenRouter pricing entries in `cost_accountant/types.py`, 6 unit tests, probe/dry-run integration verified. Use `--per-faction-providers '{"alpha":{"provider":"openrouter","model":"<model-id>"}}'` in any self-play run with `OPENROUTER_API_KEY` set. See DEVLOG.md "Phase 30 close" section.

## Phase 29: vs-Naive baseline scorers (equal-split, BATNA-clearing, Nash bargaining) — Complete

Closed 2026-06-03. Added equal-split, BATNA-clearing, and Nash bargaining baseline scorers to the self-play scoring pipeline, rendered them in report output, backfilled historical metrics, and closed D-33. See `DEVLOG.md` "Phase 29 close".

<!-- history -->

## Phase 28: Coached self-play harness + Near-miss diagnostic — Complete

Closed 2026-06-02. Added `tests/self_play/coached_game.py` with `TelegramReviewGate`/`DryRunTelegramReviewGate` injection via `module_overrides`, `compute_near_miss()` to `tests/self_play/analysis.py` with four-field near-miss diagnostic, dry-run wiring tests, and fixture-backed near-miss tests for Run 9/10 scenarios. 346 tests passing. See `DEVLOG.md` "Phase 28 close" section.

## Phase 27: No-deal-aware scoring metrics — Complete

Closed 2026-06-01. Added baseline-normalized scoring fields to `_pareto_efficiency_metrics()` (`negotiated_surplus_share`, `faction_deltas`, `delta_above_batna_sum`, `min_faction_delta`, `surplus_distribution_stdev`), NO-DEAL-AWARE SCORING report section, `tools/backfill_scoring_metrics.py` CLI, and docs (`ASSESSMENT.md`, `diplomat-testing-doc.md`, `TUNING_LOG.md`). 340 tests passing. See `DEVLOG.md` "Phase 27 close" section.

## Phase 26: Structured per-event logging — Complete

Closed 2026-06-01. Added stream-based `diplomat.*` logging config, `DIPLOMAT_LOG_LEVEL`, Telegram inbound/outbound/tagging records, flow/pipeline/orchestrator event lifecycle records, caplog unit + integration coverage, and logging docs. 337 tests passing. See `DEVLOG.md` "Phase 26 close" section.

## Phase 25: `tools/service.sh` tmux rewrite — Complete

Closed 2026-06-01. Rewrote `tools/service.sh` to supervise the bot in a `diplomat` tmux window inside the long-lived `bot` session, with `BOT_TMUX_SESSION` override, tmux-backed `start`/`stop`/`status`/`restart`, and a shell smoke test. 331 tests passing. See `DEVLOG_archive.md` "Archived 2026-06-01 — Phase 25 service tmux rewrite" section.

## Phase 24: Small builds + Level 1 modularization — Complete

Closed 2026-06-01. Asymmetric BATNA flags (`--batna-fractions`, `--force-batna-fraction`), game-mode runtime override (`--game-mode`), extraction examples moved to `config/examples/extraction_examples.json`, entity types derived from `state_patch.json` schema in reconciler and self-play analysis. 330 tests passing. See `DEVLOG.md` "Phase 24 close" section.

## Phase 23: Scoring expansion — Pareto efficiency + process signatures — Complete

Closed 2026-05-31. Added `pareto_efficiency` field to `GameEnvironment.score_game()` and `compute_process_signatures()` to `tests/self_play/analysis.py`. Four deterministic process signatures (broken-promise rate, coalition stability, time-to-deal, opening gap). 316 tests passing. See `DEVLOG.md` "Phase 23 close" section.

## Phase 22: Pipeline / Flow split — Complete

Closed 2026-05-31. Added `Pipeline`, `EventDrivenFlow`, and `RoundSteppedFlow`; converted `Orchestrator` to a compatibility factory returning `EventDrivenFlow(Pipeline(core))`; made `GameEnvironment` a thin `RoundSteppedFlow` wrapper; documented `ARCH_flow.md`. 308 tests passing. See `DEVLOG.md` "Phase 22 close" section.

## Phase 21: Module boundary cleanup — Complete

Closed 2026-05-31. `OrchestrationOptions` dataclass; public `advance_to_round(n)`; deleted `_TaggedLLMClient`; `attribution`/`purpose` kwargs threaded through adapter stack; `build_reconciler` + `subsystem_llm_config` factories; `StubAnalyst` out of production registry; reconciler exceptions logged. 296 tests passing. See `DEVLOG_archive.md` "Phase 21 close" section.

## Phase 20: Layer 3 integration tests for Phase 18 paths — Complete

Closed 2026-05-31. Added `tests/integration/test_phase18_paths.py` (6 tests, 290 total): burst extraction no-drops, reconciler dedup/fulfillment/inconsistency/missed-proposal. Deterministic fake LLM. `ASSESSMENT.md` Block A reconciliation path coverage → closed debt. `diplomat-testing-doc.md` Layer 3 counts updated. See `DEVLOG_archive.md` "Phase 20 close" section.

## Phase 19: Execute, ad-hoc — Complete

Closed 2026-05-31. Shipped toolkit `complete_with_retry` / `normalize_model_name` / `max_completion_tokens` dispatch; production `_attach_reconciler` + `game.total_rounds`; CLI_REFERENCE.md; SMOKE_RUNBOOK.md (coaching scope); ASSESSMENT.md (skill framework + scoring lenses + workstream blocks); module boundary audit → Phases 20-24 queued. See `DEVLOG_archive.md` "Archived 2026-05-31 — Phase 18 + Phase 19" section.

## Phase 18: Multi-Agent Self-Play + Tuning — Complete

Closed 2026-05-30. Regime shifted Build → Explore mid-phase. Built complete self-play infrastructure (GameEnvironment, scenario compiler, post-game scoring, state reconciliation, game-mode), reusable `structured_call` toolkit, 8 simulations across 4 scenario types (~$5-6 spend). Decisions D-20 through D-24. See `DEVLOG_archive.md` Phase 18 Close section.

## Phase 17: Layer 2 — Prompt Regression Infrastructure — Complete

`tests/prompt_regression/` package: scenario/result dataclasses, JSON-path helpers, LLM-as-judge, runner with CLI, 4 free Extraction + 2 LLM-backed Generation scenarios. 211 tests pass. See `DEVLOG_archive.md` Phase 17.

## Phase 16: Deployment Readiness — Complete

Live-smoke fix regression coverage, two-channel Telegram docs, `config/diplomat.service` unit (later found broken via incus exec — see Pi deployment gotcha), CostAccountant adapter construction fix. 193 tests passing. See `DEVLOG_archive.md`.

## Phase 15: Live Smoke Test — Environment Setup — Complete

`.env.template` + `config/pipeline_smoke.yaml`; manual Pi smoke confirmed Telegram transport, operator commands, `/preview`, review gate. Five integration fixes applied. See `DEVLOG_archive.md`.

## Phase 14: Layer 3 — Transcript Replay Tests — Complete

Two JSON transcript fixtures + 5 replay tests verifying multi-round promise/coalition/inconsistency/intelligence persistence. 187 tests passing. See `DEVLOG_archive.md`.

## Phase 13: Layer 3 — Pipeline Integration Tests — Complete

Fake-backed Layer 3 infrastructure + 12 tests (fixture startup, core Orchestrator flow, failure handling). 182 tests passing. See `DEVLOG_archive.md`.

## Phase 12: Orchestrator Refactor — Complete

Extracted `ToolkitLLMAdapter` + `DiplomatCostGate` to `src/adapters.py`; expanded State Manager (5 persistence APIs); typed `InboundEvent`; 170 tests passing. See `DEVLOG_archive.md`.

## Phase 11: Orchestrator — Complete

`pipeline.yaml`, registry lookup, full Orchestrator wiring, `src/main.py`, 44 focused Orchestrator tests + 165 total. Post-phase toolkit integration probes found 3 mismatches; adapters applied and verified on Pi. See `DEVLOG_archive.md`.

## Phase 10: Adversarial — Complete

`AdversarialResult`, `LLMAdversarialReader`, local schema validation, 9 tests + 121 total. See `DEVLOG_archive.md`.

## Phase 9: Review Gate — Complete

Review decisions, auto-approve mode, Telegram approve/edit/block workflow, optional timeout auto-block, 14 tests + 112 total. See `DEVLOG_archive.md`.

## Phase 8: Generation — Complete

`GenerationResult`, `LLMGenerator`, review-gate JSON parsing (`response`, `reasoning`), `config/prompts/generation.txt`, 11 tests + 98 total. See `DEVLOG_archive.md`.

## Phase 7: Context Assembler — Complete

`CoachingEntry`, `DecisionContext`, `DefaultContextAssembler` (pure composition), 7 tests + 87 total. See `DEVLOG_archive.md`.

## Phase 6: Analyst + Divergence — Complete

`LLMAnalyst`, pure divergence comparison, analyst prompt/schema, 12 tests + 80 total. See `DEVLOG_archive.md`.

## Phase 5: Persona — Complete

`CoachingContext`, `FileBasedPersona` (hot-reload via mtime), section stripping at `## CURRENT ROUND CONTEXT`, dynamic round-context formatting, sample `config/faction_prompt.txt`. 68 tests passing. See `DEVLOG_archive.md`.

## Phase 4: Transport — Complete

Shared Transport API exports, `CLITransport`, dependency-injected `TelegramBotTransport`, 21 tests + 59 total. See `DEVLOG_archive.md`.

## Phase 3: Coaching — Complete

`config/coaching_routes.yaml`, `CoachingEvent`, `Command`, `RouteRule`, `TaggedCoachingParser`, tagged/free coaching parsing, slash command parsing, 11 tests + 38 total. See `DEVLOG_archive.md`.

## Phase 2: Extraction — Complete

`ExtractionResult`, `OpenAIStructuredExtractor`, `RuleBasedExtractor`, local JSON/schema enforcement, `config/prompts/state_updater.txt`, 18 tests + 27 total. See `DEVLOG_archive.md`.

## Phase 1: Event Store + State Manager — Complete

Shared storage types, `SQLiteEventStore`, `SQLiteStateManager`, state patch schema validation, audit logging. See `DEVLOG_archive.md`.
