---
phase: 32
blocked: true
state: close
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

- **Phase** — Phase 32 closed 2026-06-04. See `DEVLOG.md` "Phase 32 close".
- **Focus** — Awaiting operator dispatch for the next phase.
- **Blocked/Broken** — `blocked: true` terminal close state; no open worker tasks.

<!-- Phase ordering convention:
       - Open / queued phases first, in forward execution order (next-to-do first).
       - Then a `<!-- history -->` marker separates open from closed.
       - Below the marker: closed phases in reverse-chronological order
         (most recently closed first; same-day closes sorted by phase number descending).
     This puts the active work at the top and the "recent past" right under it,
     with deep history at the bottom. -->

## Phase 32: Toolkit-level TG chunking + Diplomat cleanup + queue-drain + /intel trim

**Goal:** Push Telegram message chunking down to `toolkit/telegram_client.TelegramClient.send_message` so every TG send across every consumer auto-splits at the 4096-char limit with `[continued ...]` markers — eliminating the entire bug class where individual callsites forget to chunk. With that universal floor in place, drop Diplomat's local `chunk_text` helper from `OperatorReviewGate`, drain stale TG-queue updates on `_listen_for_operator` startup (R1 staleness fix from Run 13 post-mortem), and trim `/intel` output to the latest round so it isn't dumping 30 KB of analyst history every query. Sister projects (Phosphene, Codexbot) inherit the auto-chunking for free when/if they adopt the shared toolkit; today they do nothing. **Work regime:** Build.

**Why now:** Run 13 surfaced two related issues. (1) `/intel` was silently dropped because the response exceeded 4096 chars and `transport.send` doesn't chunk command responses — Phase 31 only fixed chunking for the review-gate path. The bug class is "any TG send anywhere that exceeds 4096 silently fails." (2) The first coached game's R1 was poisoned by a stale `/approve` from the previously-killed Phase-31-bug session — the listener consumed all backed-up updates on first poll. Operator-confirmed 2026-06-04. Both are small, both compound, both worth fixing in one phase.

**Cross-project notes (read before starting):**
- **Toolkit** lives at `p:\shared\toolkit` (Diplomat's vendored editable install per the `toolkit` rule). Steps 32.1 + 32.2 modify shared toolkit code — they are **OPERATOR-DRIVEN** and outside the autonomous worker's project-directory contract.
- **Codexbot** has its **own vendored copy** of toolkit at `p:\shared\codexbot\toolkit\telegram_client.py` — independent of the shared one. Shared-toolkit changes do not propagate to Codexbot until it drops the vendored copy. Codexbot uses `send_message` return values for `working_message_id` / `edit_message` streaming (lines 991, 1193, 1469-1484 of `codexbot/main.py`), but those messages are short status indicators (~20 chars), never near the limit. When Codexbot eventually adopts shared toolkit, auto-chunking is a free win.
- **Phosphene** has no current TG callsites in `src/` — nothing to break.
- Step 32.7 adds tech-debt notes to Phosphene's and Codexbot's `NEXT_STEPS.md` — also operator-driven (cross-project).
- D-46 (toolkit-level chunking) is the architectural decision behind 32.1 + 32.2.

**Key infrastructure (read before starting):**
- `p:\shared\toolkit\src\toolkit\telegram_client\client.py:259-277` — current `send_message` implementation. Single API call, no length check.
- `p:\shared\toolkit\src\toolkit\telegram_client\client.py:300-321` — `send_with_keyboard` returns a `SendResult` with one message_id; the keyboard variant won't be chunked (chunking + keyboard is messy — only the last chunk would get the keyboard).
- `p:\shared\diplomat\src\modules\review_gate\chunking.py` — current `chunk_text` helper to be relocated. Algorithm: paragraph → line → char fallback split with `[continued ...]` prefix on chunks ≥ 2.
- `p:\shared\diplomat\src\modules\review_gate\__init__.py:173-216` — `OperatorReviewGate._send_draft` and `_send_section`. Currently chunk before sending; after 32.3 they just compose the message and call `transport.send` once.
- `p:\shared\diplomat\tests\self_play\coached_game.py` — `_listen_for_operator` (added Phase 31a). Step 32.4 drains pending TG updates before forwarding.
- `p:\shared\diplomat\src\orchestrator.py:350-352` — `_command_intel` dumps every intelligence row. Step 32.5 trims to latest round only.

**Operator dispatch protocol:**
1. Operator manually completes 32.1 + 32.2 (shared toolkit changes + unit tests).
2. Operator marks 32.1 + 32.2 as `[x]` in DEVPLAN.
3. Operator sets `blocked: false` in frontmatter.
4. Operator dispatches the autonomous worker. Worker picks up at 32.3.
5. After worker closes 32.6, operator handles 32.7 (cross-project doc notes) and any optional Pi smoke.

### Steps

- [x] **32.1 OPERATOR — Move `chunk_text` to toolkit as `split_message` and add unit tests.**
  **Shipped 2026-06-04.** Spec deviation flagged at start: `split_message` + `TELEGRAM_MESSAGE_LIMIT` already existed in `toolkit/telegram_client/formatting.py` (Codexbot-style line-only algorithm, **zero callers in toolkit/diplomat/phosphene**, zero tests). Upgraded in place rather than creating a parallel helper — preserves the public API (`from toolkit.telegram_client import split_message, CONTINUATION_PREFIX, TELEGRAM_MESSAGE_LIMIT`). Algorithm replaced with Diplomat's paragraph-first + line + char fallback; `CONTINUATION_PREFIX = "[continued ...]\n\n"` added and exported from package; 17 unit tests in `tests/telegram_client/test_chunking.py` covering short/exact/empty/defaults/paragraph-pref/line-fallback/char-fallback/marker-placement/reassembly/validation. Codexbot's eventual migration is a drop-in import swap with two upgrades inherited automatically (paragraph-first, markers).

- [x] **32.2 OPERATOR — Add auto-chunking to `TelegramClient.send_message` (using `split_message`).**
  **Shipped 2026-06-04.** `client.py:send_message` now branches on `len(text) <= TELEGRAM_MESSAGE_LIMIT`: ≤ limit → single API call (unchanged behavior); > limit → `split_message(text)` + N serial `sendMessage` calls, `reply_to` applied only to chunk 1 (continuations are not replies), `parse_mode` applied to every chunk, INFO log records chunk count + total chars, returns the LAST message_id (preserves `int` return type for backward compatibility). Added internal `_validate_text_type` (type-only) used by `send_message` while `_validate_message_text` (strict 4096) is retained for `edit_message` and `send_with_keyboard` (those don't auto-chunk — chunking + keyboard is messy, editing is single-message-at-a-time). 12 unit tests in `tests/telegram_client/test_send_message_chunking.py`. Docs updated: `ARCH_telegram_client.md` (auto-chunking subsection + send_message + split_message + CONTINUATION_PREFIX entries), `README.md` (quick-start + public API table), `TOOLKIT_REFERENCE.md` (helper description + example).

- [x] **32.3 LOOP — Drop Diplomat's local chunking from `OperatorReviewGate`.**
  Delete `src/modules/review_gate/chunking.py`. In `src/modules/review_gate/__init__.py`:
  - Remove the `chunk_text` / `CONTINUATION_PREFIX` import.
  - Rewrite `_send_draft` to compose the single message: `header + draft_text + commands_hint`, then ONE `transport.send(OutboundMessage(content=full, channel="coaching"))` call. Toolkit handles the split automatically. No `max_message_chars` param needed (it becomes vestigial — leave it for now with a deprecation note in the docstring, or remove it; removal is cleaner).
  - Rewrite `_send_section` similarly: single `f"{title}{body}"` send.
  - Delete `tests/test_review_gate_chunking.py` (chunking now lives in toolkit's test suite).
  - Update existing `tests/test_review_gate.py` chunking-related cases:
    - `test_operator_review_gate_chunks_large_draft_through_transport` → either retire OR rewrite to assert that the fake transport saw `len(content) > 4096` in the single send (responsibility moved to toolkit).
    - `test_operator_review_gate_chunks_large_reasoning_through_transport` → same treatment.
  - Verify with `python -m pytest tests/test_review_gate.py tests/integration/test_review_gate_flow.py -v`.

- [x] **32.4 LOOP — Queue-drain on `_listen_for_operator` startup.**
  In `tests/self_play/coached_game.py`, modify `_listen_for_operator`:
  - Before entering the forward loop, capture a `drain_until = loop.time() + 1.0` (one-second drain window — empirically enough to absorb the initial `getUpdates` dump from an abnormally-terminated previous session).
  - While `loop.time() < drain_until`, consume events from `tg_transport.listen()` but discard them silently (don't forward to `dispatch_operator`). Log `logger.info("listener drain window absorbed %d stale events", count)`.
  - After the drain window, switch to normal forwarding behavior.
  - Add a regression test: scripted fake TG transport that yields 3 events immediately + 1 event after a `await asyncio.sleep(1.5)`. Assert that only the post-drain event reaches `dispatch_operator`.
  - Verify with `python -m pytest tests/test_coached_game.py -v`.

- [x] **32.5 LOOP — Trim `/intel` output to latest round.**
  In `src/orchestrator.py` `_command_intel`:
  - Keep only the latest intelligence row (by `created_at` or `round_number`, whichever the schema uses). If multiple rows for the same round (primary + secondary), prefer primary unless asked otherwise.
  - Format as a compact summary: faction, round, threat level, top 3 leverage points, top 3 risks (read from `analysis_json`), not the raw `json.dumps(rows)` of every column.
  - The pre-trim full-history behavior can be exposed as `/intel-history` if desired (defer — wait for operator demand).
  - Add a unit test: `_command_intel` returns a string < 2000 chars when there are 8 intelligence rows in the DB.
  - Verify with `python -m pytest tests/test_orchestrator.py -v -k intel`.

- [x] **32.6 LOOP — Diplomat doc updates.**
  - `ARCH_review_gate.md`: remove the "Chunking Contract" section (now owned by toolkit). Add a one-line note pointing readers to toolkit's `send_message` auto-chunk contract for the underlying behavior.
  - `ARCHITECTURE.md` coupling notes: update Review Gate ↔ Transport bullet to reflect that chunking is no longer a review-gate concern.
  - `DECISIONS.md`: add D-46 (toolkit-level chunking) and D-47 (queue-drain on listener startup) entries.
  - `NEXT_STEPS.md`: close the `/intel silent` open item with reference to Phase 32.5; close the R1-startup-race open item with reference to Phase 32.4.
  - `DEVLOG.md`: append a `## Phase 32 close (YYYY-MM-DD)` entry.
  - No `README.md` or `PROJECT.md` changes expected.

- [x] **32.7 OPERATOR — Cross-project NEXT_STEPS notes + optional Pi smoke.**
  **Closed 2026-06-04, cross-project notes skipped.** Operator clarified: "NEXT_STEPS.md was an ad-hoc place to hold notes from my discussions; it was meant for things that are not proper SWD but rather experiments and directions, other projects may or may not have this and we don't need to formalize it." Neither Phosphene nor Codexbot uses a NEXT_STEPS.md convention — both have only DEVPLAN/DEVLOG/DECISIONS/ARCH_*. The Codexbot migration knowledge is preserved in (a) Diplomat's DEVLOG Phase 32 close entry, (b) DECISIONS D-46, (c) toolkit's own ARCH_telegram_client.md auto-chunking section + README + TOOLKIT_REFERENCE.md (which Codexbot's owner naturally consults when migrating). Pi smoke is optional and operator-driven — they'll exercise it if/when they want a fresh coached re-test. Worker may proceed to REVIEW + CLOSE on next dispatch.

### Verification

After all 7 steps:

```
python -m pytest tests/ -v
```

Diplomat suite passes. New tests:
- toolkit `chunking.py` unit tests (32.1)
- toolkit `send_message` auto-chunk integration tests (32.2)
- `tests/test_coached_game.py::test_operator_listener_drains_pending_updates_on_startup` (32.4)
- `tests/test_orchestrator.py::test_command_intel_trimmed_output` (32.5)

Cross-project NEXT_STEPS notes (32.7) confirmed by visual inspection of each project's file.

<!-- history -->

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
