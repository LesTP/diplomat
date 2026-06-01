---
phase: 24
blocked: false
state: plan
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
  - **Pi deployment mechanism:** `incus exec claude-code -- sudo -u claude tmux new-window -t bot -n diplomat ...` (adds a window to the long-lived `bot` tmux session that already supervises codexbot). `tools/service.sh start` does NOT work via `incus exec` — the transient cgroup scope is torn down and kills the process even with `nohup`+`setsid`+`</dev/null`. See `CLI_REFERENCE.md` `tools/service.sh` section and `diplomat-testing-doc.md` §5b.
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

- **Phase** — Phase 24 (Build) closed 2026-06-01. Awaiting human audit before Phase 25.
- **Focus** — Phase 25 queued: `tools/service.sh` rewrite around tmux (closes the outstanding tooling debt from the Phase 19 smoke — `service.sh` is currently broken via `incus exec` and the Pi-deployment workflow falls back to a raw tmux command). See Phase 25 section below.
- **Blocked/Broken** — Blocked pending human audit of Phase 24. When clearing the gate, bump frontmatter `phase: 25` and set `state: plan` to dispatch Phase 25.

## Phase 25: `tools/service.sh` tmux rewrite (Build)

Regime: Build. Closes the outstanding tooling debt surfaced during the 2026-05-31 Telegram smoke. The current `tools/service.sh` is broken when invoked via `incus exec claude-code -- bash tools/service.sh start` — the nohup'd child dies because `incus exec` creates a transient cgroup scope that gets torn down when the immediate command exits. The smoke's workaround was a raw `incus exec -- sudo -u claude tmux new-window -t bot -n diplomat ...` invocation. This phase makes `service.sh` use the working tmux pattern internally so the operator-facing interface (`start`/`stop`/`status`/`logs`/`restart`) works again as a single wrapped command.

Prerequisite: None code-wise. The working pattern is already documented in `CLI_REFERENCE.md` (`tools/service.sh` section, "Working pattern" block) and `diplomat-testing-doc.md` §5b.

Steps:
- **25.1** Scope analysis. Read current `tools/service.sh`. Confirm the replacement design: `start()` invokes `sudo -u claude tmux new-window -t <session> -n diplomat <cmd>` with the python command running foreground in the pane and `tee -a logs/diplomat.log` for output; `stop()` invokes `sudo -u claude tmux kill-window -t <session>:diplomat`; `status()` queries `sudo -u claude tmux list-windows -t <session>`. Decide and document: (a) the supervising tmux session name — default `bot` (matches the existing long-lived session that already supervises codexbot), overridable via `BOT_TMUX_SESSION` env var for tests and parallel deployments; (b) auto-detect whether already running as user `claude` (skip `sudo -u claude` if so); (c) handling for missing tmux session — fail with a clear "session `bot` not found; create with: `sudo -u claude tmux new-session -d -s bot`" message rather than silently auto-creating (auto-create would mask configuration errors).
- **25.2** Rewrite `start()`. Replace `nohup "$VENV_PYTHON" -u src/main.py >> "$LOG_FILE" 2>&1 < /dev/null &` with the tmux invocation per 25.1. Preserve the `DIPLOMAT_PIPELINE_CONFIG` env var passthrough. Remove the legacy `.diplomat.pid` write (tmux is now the source of truth). Add the "session missing" guard.
- **25.3** Rewrite `stop()`. Use `sudo -u claude tmux kill-window -t "$SESSION":diplomat 2>/dev/null || true`. Idempotent — if the window doesn't exist, exit 0 with "Diplomat is not running" message. Remove legacy `.diplomat.pid` cleanup.
- **25.4** Rewrite `status()` and `restart()`. `status` queries `sudo -u claude tmux list-windows -t "$SESSION" -F '#{window_name}'` and greps for `diplomat`; prints "Diplomat is running (tmux window $SESSION:diplomat)" or "Diplomat is not running". `restart` stays as `stop + start` (compositional). `logs()` is unchanged (continues to `tail -n N "$LOG_FILE"`).
- **25.5** Add a basic shell-driven smoke test in `tests/test_service_sh.py`. Skips if `tmux` is not on PATH. Uses `BOT_TMUX_SESSION=_test_diplomat_session` (not `bot`, to avoid colliding with the operator's real session) and creates the session in setup. Subprocess-drives `service.sh start`, polls `status` until running, calls `stop`, verifies `status` reports not-running. Tears down the temp session in cleanup.
- **25.6** Doc update: `CLI_REFERENCE.md` `tools/service.sh` section (remove the ⚠️ broken-via-incus-exec warning; promote the "Working pattern" examples to the canonical interface; keep the env-var table and add `BOT_TMUX_SESSION` row); `SMOKE_RUNBOOK.md` §2 (replace the raw `incus exec ... tmux new-window` block with `incus exec claude-code -- bash tools/service.sh start`); `diplomat-testing-doc.md` §5b "Running the bot on the Pi (current container)" subsection (drop the `tools/service.sh start (nohup)` row from the "what doesn't work" table since it now works; promote service.sh back to the canonical lifecycle command); `DEVPLAN.md` Cold Start gotcha "Pi deployment mechanism" (rewrite to reflect `service.sh` now works; tmux is the underlying mechanism but `service.sh` is the operator-facing tool).
- **25.7** Phase review + commit + close. Definition of done: `tools/service.sh start` works both from inside a long-lived shell AND from `incus exec claude-code -- bash tools/service.sh start`; `status`, `stop`, `restart`, `logs` all work; service.sh smoke test passes (or skips cleanly if tmux unavailable); the four named docs updated; the smoke runbook can demonstrate a single-command bot start.

Expected outcome: one canonical Pi-deployment command (`service.sh start`) replacing the four-line raw tmux invocation. The "broken via incus exec" gotcha disappears from DEVPLAN and `CLI_REFERENCE`. SMOKE_RUNBOOK §2 shrinks meaningfully. Closes the last 🔨 PURE BUILD item from the post-smoke tooling debt; the remaining "structured per-event logging" item stays in `NEXT_STEPS.md` for a possible Phase 26.

## Phase 21: Module boundary cleanup — Complete

Closed 2026-05-31. `OrchestrationOptions` dataclass; public `advance_to_round(n)`; deleted `_TaggedLLMClient`; `attribution`/`purpose` kwargs threaded through adapter stack; `build_reconciler` + `subsystem_llm_config` factories; `StubAnalyst` out of production registry; reconciler exceptions logged. 296 tests passing. See `DEVLOG_archive.md` "Phase 21 close" section.

## Phase 22: Pipeline / Flow split — Complete

Closed 2026-05-31. Added `Pipeline`, `EventDrivenFlow`, and `RoundSteppedFlow`; converted `Orchestrator` to a compatibility factory returning `EventDrivenFlow(Pipeline(core))`; made `GameEnvironment` a thin `RoundSteppedFlow` wrapper; documented `ARCH_flow.md`. 308 tests passing. See `DEVLOG.md` "Phase 22 close" section.

## Phase 20: Layer 3 integration tests for Phase 18 paths — Complete

Closed 2026-05-31. Added `tests/integration/test_phase18_paths.py` (6 tests, 290 total): burst extraction no-drops, reconciler dedup/fulfillment/inconsistency/missed-proposal. Deterministic fake LLM. `ASSESSMENT.md` Block A reconciliation path coverage → closed debt. `diplomat-testing-doc.md` Layer 3 counts updated. See `DEVLOG_archive.md` "Phase 20 close" section.

## Phase 23: Scoring expansion — Pareto efficiency + process signatures — Complete

Closed 2026-05-31. Added `pareto_efficiency` field to `GameEnvironment.score_game()` and `compute_process_signatures()` to `tests/self_play/analysis.py`. Four deterministic process signatures (broken-promise rate, coalition stability, time-to-deal, opening gap). 316 tests passing. See `DEVLOG.md` "Phase 23 close" section.

## Phase 24: Small builds + Level 1 modularization — Complete

Closed 2026-06-01. Asymmetric BATNA flags (`--batna-fractions`, `--force-batna-fraction`), game-mode runtime override (`--game-mode`), extraction examples moved to `config/examples/extraction_examples.json`, entity types derived from `state_patch.json` schema in reconciler and self-play analysis. 330 tests passing. See `DEVLOG.md` "Phase 24 close" section.

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
