---
phase: 28
blocked: false
state: execute
steps_remaining: 6
---

# Diplomat — Development Plan

<!-- This file is the primary state document for cold-start sessions.
     Workers read it on every cold start to determine what to do next.
     Keep it concise — the DEVPLAN should get SHORTER as work progresses.

     For autonomous projects, the frontmatter includes a `state` field:
       state: plan | execute | review | close
     See WORKER_SPEC.md for state-machine semantics.

     `steps_remaining` is managed by the state machine at runtime — do NOT
     pre-populate. -->

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

## Current Status

- **Phase** — Phase 28 queued (coached self-play harness + near-miss diagnostic). Pre-planned by operator 2026-06-02 from NEXT_STEPS Tier 1 items §4 (Coaching test loop on Pi) and §1.9 (Near-miss diagnostic).
- **Focus** — Two independent Tier-1 builds bundled: (a) `tests/self_play/coached_game.py` swapping one faction's Pipeline transport+review_gate to TelegramReviewGate so the operator can coach a self-play game live via Telegram; (b) `near_miss` + `defection_event_log` fields in `tests/self_play/analysis.py` for diagnosing "almost reached a deal" outcomes. Pure build; no LLM cost.
- **Blocked/Broken** — Not blocked. Worker will run PLAN to confirm scope/design, then EXECUTE the 6-step checklist below.

<!-- Phase ordering convention:
       - Open / queued phases first, in forward execution order (next-to-do first).
       - Then a `<!-- history -->` marker separates open from closed.
       - Below the marker: closed phases in reverse-chronological order
         (most recently closed first; same-day closes sorted by phase number descending).
     This puts the active work at the top and the "recent past" right under it,
     with deep history at the bottom. -->

## Phase 28: Coached self-play harness + Near-miss diagnostic

**Scope.** Two independent builds, bundled because both are Tier 1 (per
`NEXT_STEPS.md` workstream tiering), both pure code/test work, and together
they enable the next set of operator-driven activities: the Pi-side coaching
smoke (NEXT_STEPS §4) needs the harness; future Run 11+ analysis benefits
from the diagnostic.

- **Coached self-play harness** (`[X]` cross-cutting). Builds
  `tests/self_play/coached_game.py` taking `--coach-faction <name>`. The
  named faction's Pipeline gets a `TelegramReviewGate` pointed at the
  operator's coaching chat; the other factions stay on
  `AutoApproveReviewGate`. Phase 22's Pipeline/Flow split makes this
  additive — no Orchestrator / Pipeline / Flow API changes.
- **Near-miss + defection diagnostic** (`[A]` agent architecture / analysis).
  Adds `near_miss: bool`, `converging_factions: list[str]`,
  `dissenting_faction: str | None`, and `defection_event_log: list[dict]`
  to `analyze_results()` in `tests/self_play/analysis.py`. Read-only on
  the score (Phase 27's `negotiated_surplus_share` correctly registers
  0.000 for any no-deal outcome; this diagnostic answers *why* without
  inflating the score).

**Decision rule for close.** Phase complete when:
- `tests/self_play/coached_game.py` exists and a dry-run test verifies the
  per-faction transport/review-gate routing.
- `analyze_results()` emits the four new fields; tests cover the synthetic
  near-miss case + the four Run-9/10 fixtures (β-squeezed and B' should
  return `near_miss=false`, α-squeezed and C' should return `near_miss=true`
  with the right dissenting faction).
- `CLI_REFERENCE.md` documents `coached_game.py`, `SMOKE_RUNBOOK.md` or
  `diplomat-testing-doc.md` documents the coached-game flow, and the Tier 1
  entries in `NEXT_STEPS.md` are updated to reflect Phase 28 status.
- Full test suite passes (≥ 340).

**Out of scope (carry to a later phase or operator-driven session):**
- The actual Pi-side coached self-play smoke (operator-driven, requires
  Telegram + Pi).
- Backfill of all historical runs with the near-miss diagnostic (only the
  4 Run-9/10 fixtures used as tests need to be backfilled in this phase).
- Coaching-system-level work beyond wiring (e.g. live edit-log analysis
  patterns — that's NEXT_STEPS §4 follow-up).

### Step 28.1: Design + scope confirmation

- [x] Read `tests/self_play/run_simulation.py` to identify where
      `GameEnvironment` constructs per-faction Pipelines and where review
      gates are wired. Read `src/modules/review_gate/telegram.py` and the
      `TelegramReviewGate` constructor signature. Confirm the coached-game
      harness can subclass / wrap `run_simulation` rather than fork it.
      Read `tests/self_play/analysis.py` `analyze_results()` and confirm
      the rendering insertion point for the near-miss block. Document
      decisions in DEVLOG (analysis-only; no code change; no test run).

### Step 28.2: Build coached_game.py

- [ ] Add `tests/self_play/coached_game.py` with a `main()` that reuses
      `run_simulation`'s scenario/persona/LLM-client construction but
      overrides the coached faction's Pipeline so its `review_gate` is
      `TelegramReviewGate` (and its `transport` is the operator
      `TelegramBotTransport` for the coaching chat). CLI flags:
      `--coach-faction <id>` (required), plus a pass-through of the
      existing `run_simulation` flags (`--rounds`, `--scenario`,
      `--analysis-json`, `--factions`, `--output`). When
      `TELEGRAM_BOT_TOKEN` / `DIPLOMAT_COACHING_CHANNEL_ID` /
      `DIPLOMAT_OPERATOR_USER_IDS` are not set, fail fast with a clear
      message. Add a `--dry-run` path that uses a fake review-gate stand-in
      so wiring can be tested without Telegram. Run
      `.venv/bin/python -m pytest tests/test_self_play.py` to confirm no
      regression.

### Step 28.3: Tests for coached_game wiring

- [ ] Add `tests/test_coached_game.py` (or extend `tests/test_self_play.py`)
      with a `--dry-run` test that constructs a coached-game environment
      and asserts (a) the named faction's review_gate is the
      Telegram-flavored stand-in, (b) the other two factions' review_gates
      are `AutoApproveReviewGate`, (c) running 4 rounds against
      `DryRunLLMClient` produces the expected transcript shape. Run the
      focused test plus the existing self-play suite.

### Step 28.4: Near-miss + defection detector in analysis.py

- [ ] Add `compute_near_miss(results)` to `tests/self_play/analysis.py`
      returning `{near_miss, converging_factions, dissenting_faction,
      defection_event_log}`. Hand-extract per-faction R4 positions by
      substring-matching outcome strings from
      `scenario_analysis['issues'][*]['outcomes']` against each
      `round_responses[<round>][<faction>]` message. `defection_event_log`
      diffs R(n) → R(n+1) positions per faction and emits one entry per
      issue-level change with a `was_contingent` boolean (heuristic: the
      prior round's message contained "if" / "contingent on" / "conditional
      on" near the issue). Emit fields in `analyze_results()` output under
      a "NEAR-MISS DIAGNOSTIC" section parallel to the existing
      "NO-DEAL-AWARE SCORING" section. Defensive: if
      `scenario_analysis` is missing, skip silently and emit
      `near_miss=None`. Run `.venv/bin/python -m pytest
      tests/test_self_play.py` after.

### Step 28.5: Tests for near-miss detector

- [ ] Add focused tests using a synthetic fixture (3 factions, 4 rounds,
      hand-crafted R4 messages where 2 of 3 agree exactly) confirming
      `near_miss=true` with the correct `dissenting_faction` and the
      expected position-change log. Add four fixture-backed tests using the
      real run JSONs at `tests/self_play/results/`: Run 9 α-squeezed +
      Run 10 C' should both return `near_miss=true` with the right
      dissenting faction (beta, then gamma); Run 9 β-squeezed + Run 10 B'
      should both return `near_miss=false`. Tolerate the natural-language
      extraction noise floor — assert what the extractor *should* find, not
      every position change in the transcript.

### Step 28.6: Doc updates

- [ ] Update `CLI_REFERENCE.md` to add a `tests.self_play.coached_game`
      entry under the Self-play section, with flags + Telegram env-var
      requirements + the dry-run path. Update `SMOKE_RUNBOOK.md` or
      `diplomat-testing-doc.md` §5b with the coached-game smoke procedure
      (start the bot, route operator to the coaching chat, launch
      coached_game, expected approve/edit/block messages). Update
      `NEXT_STEPS.md` §4 (Coaching test loop on Pi) and §1.9 (Near-miss
      diagnostic) to reflect Phase 28 status — Tier 1 sequencing block too.
      Update `ASSESSMENT.md` §3.4 if it mentions process signatures, adding
      `near_miss` as a deterministic signature. No source-code changes in
      this step. Confirm `.venv/bin/python -m pytest` returns ≥ 340 passing.

<!-- history -->

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
