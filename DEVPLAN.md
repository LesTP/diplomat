---
phase: 46
blocked: false
state: execute
steps_remaining:
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
## Current Status
- **Phase** — Phase 46 IN PROGRESS (standalone `scenario_authoring` + unified CLI; autonomous-loopable Build — steps pre-written, `state: execute`). Architectural calls pre-settled in `DECISIONS.md` D-60. Phase 44 complete (scenario design-brief + verify-against-brief + auto-doc; see `DEVLOG.md` "Phase 44"). The remaining forward **scenario-authoring tooling** roadmap — Phase 45 (narrative-integration: Build shell loopable, prompt-quality tuning supervised), and a coalition track folding Phase 2b + §3.6 Path B coalition-exclusion scoring (scoring engine loopable; live mixed-model validation supervised) — is consolidated in the scenario-authoring handoff plan. Scenario-design (succ-v3 / Path C) and benchmark-run backlog live in `NEXT_STEPS.md`.
- **Phase numbering note:** 45 is intentionally unused — the roadmap's narrative phase was staged as Phase 48 after standalone (Phase 46) was chosen first; the coalition track slotted in as Phase 47. Gaps are normal here (40/41/42 were operator-supervised); the state machine keys on the `phase:` frontmatter value, so the gap is harmless. Supervised work outside the loops lives in `NEXT_STEPS.md`.
- **Phase B (proof-of-concept scenario):** Joint Space Mission scenario authoring unblocked. v1 spec produces 3 Pareto-optimal deals with distinct distributions (balanced consensus / alpha+gamma win / beta wins). Next operator session: run the LLM scenario compiler over the generated `scenario_analysis.json` to produce narrative + persona prose, then optionally smoke at flash-lite.
- **Operator-supervised work (2026-06-21): Phase 42 COMPLETE.** Commits 1-4 + C5a + C5b landed (`551caa9`, `257b1e0`, `d16248c`, `4c67abb`, `19e6a39`, `8a384c3`). PROJECT.md "4+ factions / 4+ issues" success criterion MET: 4×4×4 / D=256 reaches ≥2/3 probe acceptance, locked by `tests/test_scenario_builder_scale.py::test_builds_4x4x4_in_budget`. Key findings: the I-axis cliff was spec-semantic (fixed by C5a relative `batna_clearing_count_target`), and a builder determinism bug (C5b) had masked it; SA neighborhood broadening was tried and rejected (D-59). Phase 3 (scale probe) data at `scenarios/scale_probe_*` + `scenarios/c5b_final_singlecell_summary.md`. Phase 4 docs (`ARCH_scenario_authoring.md`, `SCENARIO_GUIDE.md`) shipped and updated with post-Phase-42 scaling data.
- **Operator-supervised work (2026-06-22): section 3.5 competitive-scoring benchmark built + pushed.** Per-game `faction_ranks` rank-among-factions lens + `faction_models` persistence + cross-game `mean_rank` aggregator (`tests/self_play/rank_aggregator.py`) + mixed-model dispatcher + position-rotation harness in `tools/ablation_multi.sh`. Three scoring bugs fixed (partial-coalition deal_reached normalization, below-BATNA deal rejection, aggregator no-deal filter). Runs 18-20: gpt-5.5 broke the section 10 tier/provider confound; Runs 19-20 (succ / succ2 distributive scenarios) showed the section 3.5 tooling works but no scenario yet *discriminates* - open gap is discriminating scenario design (sweet-spot for model-comparison vs bare-deadlock-headroom for the harness question; see `NEXT_STEPS.md` "State as of 2026-06-22"). Both repos (toolkit, diplomat) pushed to GitHub.

## Phase 46: Standalone scenario_authoring + unified CLI — In Progress

**Goal.** Make `src/scenario_authoring/` a self-contained, liftable package. Sever
the one load-time coupling into the pipeline (`scenario_compiler.py:32 → modules.persona`),
lock the standalone contract with a test, add a unified `python -m scenario_authoring <subcommand>`
CLI, and ship a single package onboarding README. Pure-Build, autonomous-loopable —
all architectural calls are pre-settled below and in `DECISIONS.md` D-60, so no step
requires an Explore/Refine decision.

**Pre-settled decisions (do NOT re-open — see D-60):**
- The extracted round-context renderer lives at **`src/scenario_authoring/round_context.py`**
  (inside the package). `modules/persona/__init__.py` re-exports `CoachingContext` +
  `render_round_context_section` from it for back-compat (zero consumer churn).
- **Do NOT add a `toolkit` extra to `pyproject.toml`.** Toolkit is not PyPI-resolvable
  and is deliberately omitted (Cold Start gotcha). "toolkit optional" is satisfied at the
  code level (no load-time toolkit import; LLM paths import it lazily and raise a clear
  ImportError if absent) and locked by the standalone test in 46.2 — not by packaging.
- Unified CLI subcommands for now: `build` (scenario_builder), `compile` (scenario_compiler),
  `verify` (verify_scenario_optimum), `brief` (scenario_brief). `viz` stays a flag on
  verify/build/compile; `narrative` arrives with Phase 45.

**Reference facts (from Phase 46 coupling research):**
- `CoachingContext` (frozen dataclass) + `_ROUND_CONTEXT_MARKER` + 6 private helpers
  (`_format_items`, `_format_number`, `_format_pressure_lines`, `_format_deadline_lines`,
  `_format_effective_batna_line`, `_format_final_round_lines`) + `render_round_context_section`
  are stdlib-only and self-contained in `src/modules/persona/__init__.py` (~150 LOC).
- `FileBasedPersona` + `_strip_round_context` STAY in `modules/persona`; `FileBasedPersona.build_round_context`
  calls the renderer, so persona must re-import it from the new leaf.
- Import sites to update: `scenario_compiler.py:32`, `orchestrator.py:23` (CoachingContext only),
  `tests/test_persona.py:7`, `tests/self_play/verify_scenario_pressure.py:22`.
- `scenario_compiler` already imports toolkit/adapters/dotenv lazily (lines 411, 616, 891-894);
  line 32 is the only load-time pipeline edge. The other 6 package modules are already
  sibling/stdlib-only at load time.

**Steps.**
- [x] 46.1 — Create `src/scenario_authoring/round_context.py`; move `CoachingContext`,
  `_ROUND_CONTEXT_MARKER`, the 6 helpers, and `render_round_context_section` into it
  (verbatim, stdlib-only). In `src/modules/persona/__init__.py`, delete those definitions
  and re-import the two public symbols from the leaf (`from scenario_authoring.round_context
  import CoachingContext, render_round_context_section`), keeping the existing `__all__`.
  Update the 4 import sites: `scenario_compiler.py:32` → import from `scenario_authoring.round_context`;
  `orchestrator.py:23`, `tests/test_persona.py:7`, `tests/self_play/verify_scenario_pressure.py:22`
  may keep importing from `modules.persona` (re-export covers them) — leave them unless a circular
  import appears, in which case point them at the leaf. Run the full suite; must stay green.
- [ ] 46.2 — Add `tests/test_scenario_authoring_standalone.py` locking the standalone contract:
  (a) assert `scenario_authoring` and its pure-core modules (`scenario_spec`, `scenario_fitness`,
  `verify_scenario_optimum`, `scenario_viz`, `scenario_brief`, `round_context`) import with NO
  `modules.*` module loaded (e.g. via a subprocess with `modules` shadowed/blocked, or assert
  `modules` not in `sys.modules` after a fresh import in a subprocess); (b) assert the LLM paths
  (`analyze_scenario` / `fill_narrative`) raise a clear ImportError (not AttributeError) when
  `toolkit` is unavailable. Keep it deterministic and offline (no real LLM calls).
- [ ] 46.3 — Add `src/scenario_authoring/__main__.py`: an argparse dispatcher mapping
  `build|compile|verify|brief` to the existing submodule `main()`s (rewrite `sys.argv` then call;
  compiler/builder mains are async-wrapped already). Add a test invoking the dispatcher
  (`monkeypatch sys.argv` to `["scenario_authoring","verify","--analysis",<tmp>]` and assert rc 0,
  plus an unknown-subcommand → non-zero). Update the api/contract test only if a new public symbol
  is exported (the dispatcher itself need not be exported).
- [ ] 46.4 — Doc update: new `src/scenario_authoring/README.md` (package onboarding — purpose,
  the two construction directions, public API surface, unified CLI, links to `SCENARIO_GUIDE.md`
  + `ARCH_scenario_authoring.md`). Update `ARCH_scenario_authoring.md` coupling notes (the
  `modules.persona` coupling is gone; `round_context` leaf added; pipeline→package direction noted)
  + module map row for `round_context`. Update `CLI_REFERENCE.md` with the unified-CLI entry +
  quick-index row + change-history line. Append a `DEVLOG.md` Phase 46 entry. Run full suite green.

## Phase 47: Coalition scoring — lock the Path B contract — Queued (autonomous Build)

> **Activate** after Phase 46 closes + audit: set frontmatter `phase: 47`, `state: execute`,
> `blocked: false`, `steps_remaining:` (empty), and change this title to "— In Progress".

**Goal.** Lock the existing coalition-exclusion scoring contract in
`tests/self_play/game_environment.py` (`_resolve_deal_scores` + `_find_coalition_value`)
with comprehensive unit tests, and harden malformed-input edges — WITHOUT changing
semantics. Pure-Build, autonomous-loopable; all scope/semantics calls pre-settled in
`DECISIONS.md` **D-61**. Decision-heavy / supervised coalition work (representation
rationalization, builder `coalition_values` emission, runtime detection, live mixed-model
validation) is explicitly out of scope (separate supervised phases).

**Pre-settled contract (D-61 — do NOT change semantics):**
- Partial coalition (`coalition_members` strict-subset of factions) + matching
  `coalition_values` → members get stated values, excluded factions → BATNA.
- Partial coalition + no matching entry → no-deal (`deal_reached=False`, `no_deal_reason`,
  all-BATNA).
- Grand coalition (members == all factions) → full-agreement path (`faction_score` on
  `agreed_outcomes`), NOT `coalition_values`.
- Below-BATNA and `deal_reached`-without-`agreed_outcomes` normalizations stand.

**Fixture:** `scenarios/three_party_coalition_v1/scenario_analysis.json` (coalition_values
a+b→{a:6,b:7}, a+c→{a:5,c:6}, b+c→{b:4,c:3}, grand→{a:7,b:6,c:5}; BATNAs 0/0/0).

**Steps.**
- [ ] 47.1 — Add `tests/self_play/test_game_environment_coalition.py`: unit-test
  `_find_coalition_value` (sorted-set match / miss / empty-or-missing list) and
  `_resolve_deal_scores` across every path using the fixture values — AB coalition
  (`coalition_members=["a","b"]`, non-empty agreed_outcomes → a:6, b:7, c:BATNA 0,
  `deal_reached` True), AC, BC, grand (`["a","b","c"]` → full-agreement path), unknown subset
  → no-deal (`partial_coalition_without_coalition_values`), below-BATNA → no-deal
  (`deal_below_batna_for_some_faction`), `deal_reached` with empty agreed_outcomes →
  normalized (`deal_reached_without_agreed_outcomes`). Assert `deal_reached`, `no_deal_reason`,
  and exact `faction_scores` per case. Import the module-level functions directly (no live LLM).
- [ ] 47.2 — Harden malformed inputs surfaced by 47.1 + add a precise contract docstring:
  member in `coalition_members` but absent from the entry's `values` dict → BATNA (test it);
  `coalition_members` with a non-faction id; `coalition_members` == all factions (grand path);
  missing `batna`/`factions` keys default safely. Add explicit handling + tests only where 47.1
  exposes a gap; otherwise lock the edges with assertions. Keep semantics per D-61.
- [ ] 47.3 — Doc update: add a "coalition Path B scoring contract" note to
  `ARCH_scenario_authoring.md` (the locked contract + the explicitly deferred supervised items:
  representation rationalization, builder emission, runtime detection, live validation). Append
  a `DEVLOG.md` Phase 47 entry. Run the full suite green.

## Phase 48: Narrative-integration shell — Queued (autonomous Build)

> **Activate** after Phase 47 closes + audit: set frontmatter `phase: 48`, `state: execute`,
> `blocked: false`, `steps_remaining:` (empty), and change this title to "— In Progress".
> Depends on Phase 46's `scenario_authoring/__main__.py` (for the `narrative` subcommand).

**Goal.** Build the deterministic shell for narrative integration (generalized
`fill_narrative`, the Build slice of roadmap Phase 45): apply an LLM-proposed themed relabel
+ prose onto a guaranteed numeric scaffold while a structure-preservation guard asserts the
numeric payoff structure is unchanged. Pure-Build, autonomous-loopable; the re-skin design is
pre-settled in `DECISIONS.md` **D-62**. The LLM re-skin PROMPT QUALITY (themed-name aptness,
prose faithfulness) is Refine → tuned supervised in a later phase via
`tests/prompt_regression/`; this phase authors only an initial prompt and stops at the
shell+tests boundary.

**Pre-settled design (D-62):**
- Re-skin = apply a consistent **bijection** (`relabel_map`) over faction/issue/outcome
  identifiers + themed prose; numeric scores/BATNAs/`coalition_values` come from the source
  untouched (member ids relabel, values unchanged).
- `assert_structure_preserved(source, reskinned, relabel_map)` = value-isomorphism guard:
  same counts, every score equals source under relabel, BATNAs map by faction relabel.
  REJECTS numeric drift, non-bijective/incomplete maps, missing labels.
- LLM emits ONLY `relabel_map` + prose via one schema-validated `structured_call`.
- Catalogue "parser" = deterministic heading-scoped section extractor over the prose
  catalogue (`Multi-Party Negotiation Scenarios.md`), feeding `--domain-context`.

**Reuse:** `scenario_compiler.generate_persona`/`save_persona` + the structured-LLM call
pattern; `fill_narrative` schema as a starting point for the prose fields.

**Steps.**
- [ ] 48.1 — Create `src/scenario_authoring/scenario_narrative.py` deterministic core:
  `apply_relabel(analysis, relabel_map) -> analysis` (renames factions/issues/outcomes
  consistently, preserving all numeric scores/BATNAs/coalition_values; relabels
  coalition_values member ids) + `assert_structure_preserved(source, reskinned, relabel_map)`
  (value-isomorphism guard). Unit tests (NO LLM): identity relabel round-trips; a themed
  relabel preserves all values; a tampered numeric value is REJECTED; a non-bijective or
  incomplete map is REJECTED. Standalone: stdlib + sibling imports only.
- [ ] 48.2 — Add `extract_catalogue_entry(catalogue_text, heading) -> str`: deterministic
  `###`/`####` heading-scoped section slice over the prose catalogue. Tests against
  `Multi-Party Negotiation Scenarios.md` (extract a known `#### ...` entry; unknown heading
  raises a clear error).
- [ ] 48.3 — Add `reskin_scenario(analysis, source_context, llm_client, llm_config, tier=...,
  *, domain_context="")`: one `structured_call` emitting `{relabel_map, logrolling,
  deception_tactics, narrative_md}` (+ optional persona prose) against a new schema; apply the
  relabel; run `assert_structure_preserved`; return `(reskinned_analysis, narrative_md)`.
  Author an INITIAL system prompt (quality tuning deferred — D-62). Test with a MOCKED
  `structured_call` (mirror `test_scenario_compiler.py::fake_sc`): structure preserved +
  narrative produced; a value-tampering mock is rejected by the guard.
- [ ] 48.4 — Add a `narrative` subcommand to `scenario_authoring/__main__.py` (analysis +
  catalogue source → reskinned bundle); export `reskin_scenario` + `assert_structure_preserved`
  in `__init__.__all__` and update `tests/test_scenario_authoring_api.py`. Doc update:
  `SCENARIO_GUIDE.md` (narrative-integration section; mark prompt-tuning as the supervised
  follow-on), `CLI_REFERENCE.md` (the `narrative` subcommand + quick-index + change-history),
  `ARCH_scenario_authoring.md` (new `scenario_narrative` module + public surface). Append a
  `DEVLOG.md` Phase 48 entry. Run the full suite green.

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
