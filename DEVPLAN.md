---
phase: 33
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

- **Phase** — Phase 33 queued 2026-06-07. Coaching v2: `/revise: <directive>` LLM-rewrite edit mode + auto-classifier for the review-gate edit log. Closes `NEXT_STEPS.md` §4e and unblocks the §4 feedback loop (re-run, inspect edit log, classify edits, feed patterns into faction_prompt) by giving the operator a cheap edit path and giving the system a way to surface recurring edit patterns.
- **Focus** — 10 steps, all 🔨 pure build, loop-ready. No live LLM spend during build (DryRun + fixtures throughout). Step 33.9 fixture validation is the only live-LLM step (~$0.30, classifier discrimination on hand-curated edit pairs). Live re-run (Run 14) queued separately in `NEXT_STEPS.md` for after phase close.
- **Blocked/Broken** — `blocked: false`. Worker may begin execution.

<!-- Phase ordering convention:
       - Open / queued phases first, in forward execution order (next-to-do first).
       - Then a `<!-- history -->` marker separates open from closed.
       - Below the marker: closed phases in reverse-chronological order
         (most recently closed first; same-day closes sorted by phase number descending).
     This puts the active work at the top and the "recent past" right under it,
     with deep history at the bottom. -->

<!-- history -->

## Phase 33: Coaching v2 — `/revise: <directive>` LLM-rewrite edit mode + auto-classifier — Plan

**Goal.** Close the coaching feedback loop. Run 13 (2026-06-04) validated the gate end-to-end but the operator chose approve-only; `/edit:` requires retyping the whole draft, which is more expensive than approving a marginal draft. Two related additions:

1. **`/revise: <directive>`** — operator gives intent, model regenerates the draft in-place, gate replaces the pending slot with the new draft. Capped at 3 iterations per pending review. Closes `NEXT_STEPS.md` §4e.
2. **Auto-classifier for `review_gate_edits`** — every `action='edited'` row gets one of six `diplomat-testing-doc.md` §7.3 categories via LLM-judge (`tone_softer`, `tone_harder`, `commitment_removed`, `ambiguity_added`, `constraint_enforcement`, `persona_correction`). New `/edits-summary` command surfaces recurring patterns mid-game. Closes the original §4 "classify edits" TODO and gives Block B (prompt tuning) a real evaluation signal.

All 10 steps are 🔨 pure build, loop-ready. No live LLM spend during build (DryRun + fixtures throughout). The only live-LLM step is 33.9 fixture validation (~$0.30 to confirm classifier discriminates on hand-curated edit pairs). Run 14 (live re-run on Pi exercising `/revise:`) queued in `NEXT_STEPS.md` for after phase close, not part of this phase.

**Design decisions pinned 2026-06-07:**
- `/revise:` regenerate call sees **full `DecisionContext`** (persona + intel + coaching + transcript) plus two appended high-priority sections: `[OPERATOR REVISION DIRECTIVE]: <directive>` and `[PREVIOUS DRAFT — REVISE PER DIRECTIVE]: <draft>`. Preserves voice and persona; treats directive as the highest-priority coaching note. See Step 33.1.
- Revise chain capped at **3 iterations** per pending review. After the 3rd, gate responds `[revise limit reached — /approve, /edit:, or /block to resolve]` and ignores further `/revise:` until the slot resolves. See Step 33.3.
- Revise directives stored as **JSON array in a new `revise_directives TEXT` column on `review_gate_edits`** (no separate `revise_log` table — directives only matter as context for the final `ReviewDecision`). See Step 33.3.
- Classifier results stored in a **separate `edit_classifications` table** with FK to `review_gate_edits.id` — preserves re-classification history when the classifier prompt changes. See Step 33.6.
- Classifier runs **on demand** via `tools/classify_edit_log.py` (post-game bulk) or lazily via `/edits-summary` (in-game). **Never** auto-classifies on every `/edit:` — zero added latency during coached games, zero cost surprise if never invoked.
- Default classifier model: **`gemini-2.5-flash-lite`** (commodity tier, already integrated, ~$0.01-0.05 per game's worth of edits).
- Scope lock: Phase 33 stays inside existing Review Gate, Pipeline, State Manager, and prompt-regression surfaces. No new module is introduced and no ARCHITECTURE implementation-sequence status changes are needed.

**Out of scope (deliberate):**
- `NEXT_STEPS.md` §4f UX polish (`/ledger` info-density, `/intel-history`) — stays in NEXT_STEPS.
- Auto-rewriting `config/faction_prompt.txt` from classification patterns — manual operator action remains; tooling surfaces data, operator writes prompt changes.
- Live re-run on Pi — queued as Run 14 in `NEXT_STEPS.md` for operator-driven execution after phase close.

### Part A — `/revise: <directive>` directive mode

- [x] **Step 33.1 — Pipeline regeneration API.** Add `Pipeline.regenerate_with_directive(directive: str, previous_draft: str) -> GenerationResult`. Builds normal `DecisionContext` via the existing assembler. Appends two sections to the assembled context: `[OPERATOR REVISION DIRECTIVE]: <directive>` (treated as highest-priority coaching note) and `[PREVIOUS DRAFT — REVISE PER DIRECTIVE]: <draft>`. Routes through the same Generation module call shape (same `attribution`, `purpose="generation_revision"` to distinguish in ledger). Returns a fresh `GenerationResult`. Tests: unit test asserts the two sections are appended in the right order; verifies `purpose=` is propagated; verifies the regenerate call uses the same provider/tier as the original generation.
- [x] **Step 33.2 — `/revise:` command in `OperatorReviewGate`.** Add `/revise: <directive>` (and `/revise <directive>` legacy) to `OperatorReviewGate.handle_command`. Parses the directive from the command suffix. Validates a pending review exists (returns `True` consumed with error message if not). Calls `pipeline.regenerate_with_directive(directive, self._pending.draft.response_text)`. Atomically replaces `_pending` slot with `(new_draft, adversarial=None, round_number, new_future)` — old future is discarded (the original `submit()` await is still bound to the old future via the same `_pending` reference, so updating the slot also updates what `submit()` will resolve on). Sends new draft via `transport.send(OutboundMessage(content=..., channel="coaching"))` with `Round N — Revised Draft (revise N/3)` header. Increments revise counter on the pending slot. Tests: unit test parses the command; integration test via `DryRunTelegramReviewGate` verifies slot replacement, header text, and that `submit()` ultimately returns the post-revise final action.
- [x] **Step 33.3 — Revise cap + chain logging.** Cap revise count at 3 per pending review (configurable via `OperatorReviewGate(max_revises=3)`). On the 4th `/revise:`, gate responds `[revise limit reached — /approve, /edit:, or /block to resolve]` and ignores the directive (review stays pending with the last revised draft). Schema migration: add `revise_directives TEXT` column (JSON array of directives in order) to `review_gate_edits`. `StateManager.log_review_decision` accepts an optional `revise_directives: list[str] | None` parameter and serializes it on write. Tests: unit test the cap rejection message; schema migration test confirms backward compatibility (existing rows have NULL); integration test via `DryRunTelegramReviewGate` runs revise → revise → revise → revise (4th rejected) → approve and verifies the final stored row has exactly 3 directives in order.
- [ ] **Step 33.4 — `/revise:` flow tests.** End-to-end integration tests via `DryRunTelegramReviewGate` (extends the existing dry-run gate with a scripted command sequence): (a) revise → approve happy path; (b) revise → revise → approve (chain of 2); (c) revise → revise → revise → revise (4th rejected) → block; (d) revise → block; (e) revise then transport-send error in the new draft — verify `ReviewDecision(action="blocked", edit_notes="transport error: ...")` per D-42. Asserts no orphan futures (the gate's `_pending` field is always a valid slot or None), correct directive chain in storage, correct counter values on cap rejection. Verifies the originally-awaiting `submit()` returns the post-chain action.

### Part B — Auto-classifier

- [ ] **Step 33.5 — `LLMEditClassifier` module.** New `src/modules/edit_classifier/` package with `__init__.py`, `classifier.py`, `types.py`. `EditClassification` dataclass (`category: str`, `confidence: float`, `rationale: str`, `classifier_model: str`, `classified_at: datetime`). `LLMEditClassifier` class with `async classify(original: str, edited: str, edit_notes: str | None) -> EditClassification`. Uses `toolkit.structured_llm.structured_call(tier="commodity", purpose="edit_classification")` with schema enforcing `category ∈ {tone_softer, tone_harder, commitment_removed, ambiguity_added, constraint_enforcement, persona_correction}` and `confidence ∈ [0, 1]`. New prompt file `config/prompts/edit_classifier.txt` with the six category definitions copied from `diplomat-testing-doc.md` §7.3 plus 1-2 illustrative examples per category. Factory `build_edit_classifier(llm_client, llm_providers_config, tier, attribution)` mirrors `build_reconciler` pattern. Tests: unit test schema validation; mock `structured_call` and assert the prompt includes original + edited + edit_notes; assert tier/purpose propagation; assert factory wiring.
- [ ] **Step 33.6 — `edit_classifications` table + State Manager API.** New SQL DDL in `config/schemas/state_patch.json` (or wherever DDL lives — confirm in `ARCH_state_manager.md`):
  ```sql
  CREATE TABLE edit_classifications (
      id INTEGER PRIMARY KEY,
      review_gate_edit_id INTEGER NOT NULL,
      category TEXT NOT NULL,
      confidence REAL NOT NULL,
      rationale TEXT,
      classified_at TIMESTAMP NOT NULL,
      classifier_model TEXT NOT NULL,
      FOREIGN KEY (review_gate_edit_id) REFERENCES review_gate_edits(id)
  );
  CREATE INDEX idx_edit_classifications_edit_id ON edit_classifications(review_gate_edit_id);
  ```
  Migration runs on `SQLiteStateManager.__init__` via the existing schema-evolution path. Add `StateManager.store_edit_classification(review_gate_edit_id, classification)` and `StateManager.get_edit_classifications(game_id=None, since_round=None) -> list[dict]` (joined view returning original_text + edited_text + classification fields). Tests: unit test the migration runs idempotently; CRUD round-trip test; join query test with synthetic data.
- [ ] **Step 33.7 — `tools/classify_edit_log.py` CLI.** New script: `python tools/classify_edit_log.py --db <path> [--game-id <id>] [--force]`. Opens the SQLite DB read-write, queries `review_gate_edits` for `action='edited'` rows, filters out already-classified unless `--force`, instantiates `LLMEditClassifier` (provider/model from CLI flags or pipeline.yaml defaults), invokes classify per row, writes to `edit_classifications`. Prints summary table after completion: `category | count | most_recent_example_id`. Cost estimate: ~$0.01 per edit at `gemini-2.5-flash-lite` defaults. Tests: integration test against a fake DB with hand-crafted edited rows; verifies idempotency without `--force`; verifies summary output format.
- [ ] **Step 33.8 — `/edits-summary` operator command.** Wire into `Pipeline.dispatch_operator` (existing `_dispatch_command` registry in `src/orchestrator.py`). Handler queries `edit_classifications` joined with `review_gate_edits`; for any `review_gate_edits` row with `action='edited'` and no matching classification, lazy-classifies via the same `LLMEditClassifier` (so the operator gets fresh data without running the CLI). Returns markdown table: category, count, most-recent example pair (original truncated to 80 chars, edited truncated to 80 chars). Updates the `/commands` help list. Tests: unit test on the dispatch registry; integration test confirms lazy classification happens for unclassified rows; verifies the markdown output shape.
- [ ] **Step 33.9 — Classifier discrimination tests.** Fixture-based regression suite in `tests/prompt_regression/scenarios/edit_classification/`: 4-5 hand-curated `(original, edited, edit_notes, expected_category)` tuples per category (~24-30 fixtures total). Each scenario asserts `classify()` returns the expected category at confidence ≥ 0.7. Uses live `LLMEditClassifier` (not mock) — this is the only live-LLM step in Phase 33. Cost: ~$0.30 total. Acceptance threshold: ≥ 85% category accuracy across the suite (some category boundaries are genuinely fuzzy — e.g. `tone_softer` vs `ambiguity_added` overlap — so 100% isn't realistic). Runs in the existing prompt-regression pytest pathway with `--scenarios tests/prompt_regression/scenarios/edit_classification/`. If accuracy < 85%, iterate on the `edit_classifier.txt` prompt and re-run; don't ship below threshold.

### Part C — Docs

- [ ] **Step 33.10 — Documentation update.** Files to update before phase-review:
  - `ARCH_review_gate.md` — add `/revise:` to the review commands list under `handle_command`; document the revise state machine (slot replacement, counter, cap); add `revise_directives` to the storage contract; add Step 33.4 test scenarios to the Usage Example section if appropriate.
  - `ARCH_coaching.md` — update the "Review Gate Edit Log → Prompt Refinement" section: auto-classification now exists; recurring patterns are surfaceable via `/edits-summary` mid-game or `tools/classify_edit_log.py` post-game; the "write into `config/faction_prompt.txt` directly" step remains manual.
  - `ARCHITECTURE.md` — add `/revise: <directive>` and `/edits-summary` to the User Actions list; add new "Edit Classifier" row to the Component Map; add coupling note for Edit Classifier ↔ State Manager and Edit Classifier ↔ toolkit/structured_llm; add `EditClassification` to the Core Objects list.
  - `CLI_REFERENCE.md` — add a `tools/classify_edit_log.py` entry with flags, defaults, working example, cost estimate.
  - `diplomat-testing-doc.md` §7.3 — note that auto-classification now exists; reference `tools/classify_edit_log.py` and the `/edits-summary` command; the manual classification workflow remains as a fallback / verification path.
  - `NEXT_STEPS.md` §4 — mark §4e closed; leave §4f open; add Run 14 ("coached game exercising `/revise:` and `/edits-summary`") to the Carry-Forward Items list as a queued experimental run.
  - `DEVLOG.md` — Phase 33 close entry following the standard pattern (one paragraph summary + per-step bullets + cross-references).
  - `DEVPLAN.md` — collapse Phase 33 to a closed-phase summary block (this active step list is removed at close per the phase-close convention).

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
