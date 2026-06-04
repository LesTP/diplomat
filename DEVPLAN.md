---
phase: 31
blocked: false
state: execute
steps_remaining: 2
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

- **Phase** — Phase 31 queued (Transport-routed OperatorReviewGate + chunking + lazy-fetch sections + command pass-through). Phase 30 closed.
- **Focus** — Refactor the review gate to (a) use the existing `Transport` abstraction instead of bypassing into `toolkit/telegram_client` directly, (b) chunk review messages so TG's 4096 char limit no longer breaks the loop, (c) lazy-load reasoning/adversarial sections via `/reasoning` and `/adversarial` commands, and (d) forward non-review slash commands (`/state`, `/intel`, etc.) to the normal dispatcher so they work during pending review. Pure build. Closes NEXT_STEPS §4a/b/c. §4d (operator-driven Pi re-test) remains open as the validation hook post-phase.
- **Blocked/Broken** — None.

<!-- Phase ordering convention:
       - Open / queued phases first, in forward execution order (next-to-do first).
       - Then a `<!-- history -->` marker separates open from closed.
       - Below the marker: closed phases in reverse-chronological order
         (most recently closed first; same-day closes sorted by phase number descending).
     This puts the active work at the top and the "recent past" right under it,
     with deep history at the bottom. -->

## Phase 31: Transport-routed OperatorReviewGate (chunking + lazy fetch + command pass-through)

**Goal:** Replace `TelegramReviewGate` with a transport-agnostic
`OperatorReviewGate` that (a) sends review messages through the existing
`Transport` abstraction (no direct `toolkit/telegram_client` dependency),
(b) splits messages over a configurable max-char limit with `[continued]`
markers so TG's 4096-char limit no longer drops drafts in later rounds,
(c) lazy-loads `Reasoning` and `Adversarial` sections via `/reasoning`
and `/adversarial` commands instead of pushing them eagerly, and
(d) forwards non-review slash commands to the normal operator dispatcher
so `/state`, `/intel`, `/ledger`, `/status`, `/divergences` work during
a pending review. The review gate stops polling `get_next_update()`
directly — it becomes a passive handler invoked by the dispatcher.
Closes NEXT_STEPS §4a/b/c. **Work regime:** Build.

**Why now:** The 2026-06-03 first coached game on Pi confirmed the loop
works end-to-end but surfaced 4 product-loop-breaking issues (TG char
limit, no commands during review, verbose generation, transcript
visibility). 4c (generation conciseness) shipped 2026-06-04 as a prompt
change; 4a/b/c live here as a structural refactor. 4d (operator-driven
Pi re-test) is the natural follow-up after this phase ships.

**Key infrastructure (read before starting):**
- `src/modules/review_gate/__init__.py` — current `TelegramReviewGate`
  (lines 47–216). Polls `telegram_client.get_next_update()` directly,
  formats a single message with draft + reasoning + adversarial + commands.
  This whole class is replaced; `AutoApproveReviewGate` and
  `ReviewDecision` stay.
- `src/modules/transport/__init__.py` — `Transport` interface and
  `TelegramBotTransport` impl. `send(OutboundMessage(channel="coaching"))`
  already routes to the coaching channel ID — the new gate uses this.
- `src/pipeline.py:57–61` — `dispatch_operator(content, event_id)`. Phase
  31 inserts a `review_gate.handle_command(content)` check before the
  fallthrough to `_route_operator_event`. The dispatcher consults the gate
  first; if the gate returns `True`, the command is consumed.
- `src/orchestrator.py:407` — existing example of
  `await self.transport.send(OutboundMessage(content=content, channel="coaching"))`
  — the OperatorReviewGate uses the same pattern for sending sections.
- `src/orchestrator.py:1024–1093` — `_build_modules` / `_build_module`.
  Modules are built sequentially per `REQUIRED_MODULES`. Review gate is
  built *after* transport, so the factory branch can pass the
  already-built `transport` module — but `_build_module` does not
  currently receive the in-progress modules dict. Step 31.4 adds that
  plumbing.
- `src/orchestrator.py:1128–1140` — current `review_gate` factory branch
  (constructs `TelegramReviewGate(telegram_client, ...)`). Replaced by
  `OperatorReviewGate(transport, ...)`.
- `src/registry.py:27` — class-name → import path map. Replace
  `TelegramReviewGate` entry with `OperatorReviewGate`.
- `config/pipeline.yaml:64–66` and `config/pipeline_smoke.yaml` —
  `modules.review_gate.class` config. Rename references.
- `tests/self_play/coached_game.py:22, 56, 175–177` —
  `TelegramReviewGate` import and `DryRunTelegramReviewGate` shim used
  via `module_overrides`. Rename to `OperatorReviewGate` /
  `DryRunOperatorReviewGate`.
- `tests/test_review_gate.py`, `tests/test_coached_game.py`,
  `tests/test_orchestrator.py:531` — references that move to the new
  names + the new transport-based fakes.
- `tests/integration/` — existing integration tests with fake transports;
  pattern to follow for the new integration coverage in step 31.6.
- `tools/state_machine.sh` — autonomous loop control. Do not modify.
- `WORKER_SPEC.md` — loop discipline (single call per iteration, trust
  the script). Follow strictly.

**Decisions baked into this phase (operator-confirmed 2026-06-04):**
- D-39: Buttons are NOT in scope. Toolkit `telegram_client` does not
  surface `callback_query` updates; building that is a separate project.
  Text commands (`/approve`, `/edit:`, `/block`, `/reasoning`,
  `/adversarial`) cover the same UX surface at far lower cost.
- D-40: Lazy fetch for `Reasoning` and `Adversarial`. Only the draft is
  pushed eagerly. Operator types `/reasoning` or `/adversarial` to
  fetch deeper context. Reduces noise on routine approvals.
- D-41: Concurrent `submit()` is rejected with `RuntimeError`. Current
  pipeline never concurrent-submits per agent; if that changes later,
  upgrade the single-slot pending state to a keyed dict.
- D-42: Chunk-mid-send failure aborts the review with
  `ReviewDecision(action="blocked", edit_notes="transport error: <e>")`
  and re-raises after logging. Transport already handles retries on
  individual sends; if it still fails, the review session collapses
  cleanly rather than silently leaving partial messages.
- D-43: Hard rename of `TelegramReviewGate` → `OperatorReviewGate`
  everywhere. No back-compat shim — anti-modular and there's only one
  in-tree consumer outside the production config (coached_game.py).

### Steps

- [x] **31.1 Add `chunk_text` helper + unit tests.**
  Create a free function `chunk_text(text: str, max_chars: int) -> list[str]`
  in `src/modules/review_gate/chunking.py` (new file). Algorithm:
  if `len(text) <= max_chars`, return `[text]`. Otherwise greedily pack
  paragraphs (split on `\n\n`); if a paragraph alone exceeds `max_chars`,
  fall back to line split (`\n`); if a line alone still exceeds, fall
  back to character chunks. Every chunk after the first is prefixed
  with `"[continued ...]\n\n"`. Reserve room for the prefix in the
  `max_chars` budget (e.g. `effective_max = max_chars - len(prefix)`).
  Add `tests/test_review_gate_chunking.py` with cases: short text returns
  single chunk; paragraph split; line-fallback split; character-fallback
  split; continuation markers present on all chunks ≥ 2; reassembly
  preserves all original content (modulo continuation markers).
  Verify with `python -m pytest tests/test_review_gate_chunking.py -v`.

- [x] **31.2 Add `OperatorReviewGate` class (basic — approve/edit/block, no lazy fetch yet).**
  In `src/modules/review_gate/__init__.py`, add `OperatorReviewGate`
  alongside the existing `AutoApproveReviewGate` and `TelegramReviewGate`
  (do NOT delete `TelegramReviewGate` yet — it's removed in step 31.7
  once the migration is verified). Signature:
  ```python
  class OperatorReviewGate:
      def __init__(
          self,
          transport: Any,                       # has .send(OutboundMessage)
          *,
          max_message_chars: int = 4000,       # reserve below TG's 4096 limit
          state_manager: Any | None = None,
          timeout_seconds: float | None = None,
      ) -> None: ...

      async def submit(
          self,
          draft: GenerationResult,
          adversarial: Any,
          round_number: int,
      ) -> ReviewDecision: ...

      async def handle_command(self, command: str) -> bool: ...
  ```
  `submit()`:
  - raises `RuntimeError("OperatorReviewGate has a pending review")` if
    `self._pending` is not None (D-41).
  - stores `self._pending = (draft, adversarial, round_number,
    asyncio.get_event_loop().create_future())`.
  - sends the draft section via transport (chunked through `chunk_text`).
    Format the first chunk's header as `"Review Gate - Round {N}\n\nDraft:\n{text}"`.
    Append the commands hint as a trailing line on the **last** draft
    chunk: `"\n\nCommands: /approve | /edit: <text> | /block | /reasoning | /adversarial"`.
  - awaits the future (with `asyncio.wait_for` if `timeout_seconds` is set;
    on timeout return `ReviewDecision("blocked", None, f"Review timed out after {N} seconds")`).
  - on any transport error during the eager send, abort with
    `ReviewDecision("blocked", None, f"transport error: {exc}")` (D-42),
    clear `_pending`, log via `state_manager.log_review_decision` if
    present, then re-raise after logging — caller must surface the failure.
  - logs the decision via `state_manager.log_review_decision` mirroring
    `TelegramReviewGate._log_decision`.
  - clears `_pending` in a `finally` block.

  `handle_command(command)`:
  - returns `False` immediately if `self._pending is None` (caller falls
    through to the normal dispatcher).
  - returns `True` (consumed) for `/approve`, `/edit:`, `/edit ` (legacy),
    `/block` — resolves the pending future with the appropriate
    `ReviewDecision`. Mirrors the existing `_parse_command` logic.
  - returns `True` for `/reasoning` and `/adversarial` but only after
    sending the section through transport (chunked). Lazy fetch added in
    step 31.3 — for this step, stub these as `return False` with a
    `# TODO 31.3` comment.
  - returns `False` for any other text (the dispatcher then routes it).

  Add a `FakeTransport` helper in `tests/test_review_gate.py` that records
  `OutboundMessage`s. Add `OperatorReviewGate` tests:
  - submit + handle_command("/approve") → `approved` with stripped draft.
  - submit + handle_command("/edit: foo") → `edited` with "foo".
  - submit + handle_command("/edit foo") (legacy form) works.
  - submit + handle_command("/block") → `blocked`.
  - submit + handle_command("/state") → returns `False`, review stays pending.
  - submit twice without resolving the first → `RuntimeError`.
  - handle_command before any submit → returns `False`.
  - submit with `timeout_seconds=0.05` and no command → `blocked`/timeout.
  - submit with a draft > `max_message_chars` → `transport.sent` contains
    multiple OutboundMessages, all to coaching channel, last one ends
    with the commands hint.
  - State manager log path: a fake `state_manager` with
    `log_review_decision` is called once per decision.

  Verify with `python -m pytest tests/test_review_gate.py -v`.

- [x] **31.3 Add lazy fetch (`/reasoning`, `/adversarial`) to `OperatorReviewGate`.**
  Replace the `# TODO 31.3` stubs from step 31.2 with real handlers:
  - `/reasoning` → if `draft.reasoning` is set, send
    `"Reasoning:\n{draft.reasoning}"` chunked through transport; if not
    set, send `"Reasoning: [not available]"`. Return `True`. `_pending`
    stays.
  - `/adversarial` → format adversarial via a helper mirroring the
    existing `_format_adversarial` (handle dict, object, str, None,
    success=False cases). Send chunked. Return `True`.

  Add tests in `tests/test_review_gate.py`:
  - submit + /reasoning + /approve → two messages sent (draft + reasoning),
    then `approved`.
  - submit + /adversarial + /approve → two messages sent (draft +
    adversarial), then `approved`.
  - submit + /reasoning when reasoning is None → sends `[not available]`.
  - submit + /adversarial when adversarial is None → sends a
    `"Skipped or unavailable."` line.
  - submit + /reasoning + /reasoning → two extra messages (idempotent
    fetch — operator can re-request).
  - submit with a large reasoning string → reasoning message is chunked.

  Verify with `python -m pytest tests/test_review_gate.py -v`.

- [x] **31.4 Wire `OperatorReviewGate` into the orchestrator factory + dispatcher routing.**
  Three coupled edits:

  (a) `src/registry.py:27` — add a new entry:
  `"OperatorReviewGate": "modules.review_gate:OperatorReviewGate"`.
  Leave the `TelegramReviewGate` entry in place until step 31.7.

  (b) `src/orchestrator.py:1024–1141` — make the previously-built
  `transport` accessible in the `review_gate` factory branch. Easiest
  surgical change: change `_build_modules` to pass the in-progress
  `modules` dict into `_build_module`, and have the `review_gate` branch
  read `modules.get("transport")`. Concretely:
  ```python
  def _build_modules(self, *, module_overrides, llm_client, telegram_client):
      modules: dict[str, Any] = {}
      module_config = self.config["modules"]
      for name in REQUIRED_MODULES:
          if name in module_overrides:
              modules[name] = module_overrides[name]
              continue
          modules[name] = self._build_module(
              name,
              module_config[name],
              llm_client=llm_client,
              telegram_client=telegram_client,
              built_modules=modules,        # NEW
          )
      return modules
  ```
  Update `_build_module` to accept `built_modules: dict[str, Any]`. In
  the `review_gate` branch, add an `OperatorReviewGate` arm:
  ```python
  if name == "review_gate":
      if class_name == "OperatorReviewGate":
          transport = built_modules.get("transport")
          if transport is None:
              raise PipelineConfigError(
                  "OperatorReviewGate requires the transport module"
              )
          return cls(
              transport,
              max_message_chars=int(config.get("max_message_chars", 4000)),
          )
      if class_name == "TelegramReviewGate":
          # legacy path — preserved through step 31.6
          ...
      return cls()
  ```
  Ensure `REQUIRED_MODULES` orders `transport` before `review_gate`
  (it already does — verify but no change expected).

  (c) `src/pipeline.py:57–61` — insert review-gate command dispatch:
  ```python
  async def dispatch_operator(self, content, event_id="operator-dispatch"):
      review_gate = getattr(self.orchestrator, "review_gate", None)
      if review_gate is not None and content.strip().startswith("/"):
          handle = getattr(review_gate, "handle_command", None)
          if handle is not None:
              consumed = await handle(content.strip())
              if consumed:
                  return
      event = SimpleNamespace(content=content)
      await self.orchestrator._route_operator_event(event, event_id)
  ```
  This routes /approve, /edit, /block, /reasoning, /adversarial to the
  gate while it has pending state; everything else (including the same
  slash commands when no review is pending) falls through. The dispatcher
  is the single entry point — no second consumer of telegram updates.

  Add a small unit test in `tests/test_pipeline.py` that exercises:
  - Pipeline.dispatch_operator with a fake orchestrator + fake review gate
    where handle_command returns True → underlying `_route_operator_event`
    is NOT called.
  - Same with handle_command returning False → `_route_operator_event`
    IS called.
  - Pipeline.dispatch_operator with non-slash content → review gate NOT
    consulted; `_route_operator_event` called.

  Verify with `python -m pytest tests/test_pipeline.py tests/test_orchestrator.py -v`.

- [x] **31.5 Flip configs and harness to `OperatorReviewGate`.**
  Five files:
  - `config/pipeline.yaml:65–66` — update the comment from
    `"For Telegram human review, change to: TelegramReviewGate"` to
    `"For human review via the operator coaching channel, change to: OperatorReviewGate"`.
  - `config/pipeline_smoke.yaml` — if it references `TelegramReviewGate`,
    flip to `OperatorReviewGate`.
  - `tests/self_play/coached_game.py:22, 56, 175–177` —
    `TelegramReviewGate` import → `OperatorReviewGate`;
    `DryRunTelegramReviewGate` → `DryRunOperatorReviewGate` (the dry-run
    shim only needs to satisfy `submit()` and now also `handle_command()`
    returning `False` for everything). Update the live-mode constructor:
    instead of `TelegramReviewGate(client, coaching_channel_id=...)`,
    construct `OperatorReviewGate(transport, max_message_chars=4000)` —
    grab the transport from the agent's pipeline.
  - `tests/test_coached_game.py:13, 95` — rename references.
  - `tests/test_orchestrator.py:531` — update the parametrize case from
    `("TelegramReviewGate", "TelegramReviewGate")` to
    `("OperatorReviewGate", "OperatorReviewGate")`.

  Verify with `python -m pytest tests/ -v` — all tests pass; no module
  raises an import error. Existing `TelegramReviewGate` class still
  exists in `review_gate/__init__.py` but is no longer referenced by any
  config or test.

- [ ] **31.6 End-to-end integration tests through `EventDrivenFlow`.**
  Add `tests/integration/test_review_gate_flow.py` exercising the full
  loop with a `FakeTransport` that supports both `send()` (records
  OutboundMessages) and `listen()` (yields scripted InboundEvents).
  Four tests:
  1. **Happy path:** scripted events include an operator `/approve`
     after the response pipeline submits a draft. Assert the public
     channel receives the approved text and the review gate's pending
     state is cleared.
  2. **`/state` during pending review (4b validated end-to-end):**
     scripted events include `/state` (which goes to the state handler
     and produces a coaching-channel response) followed by `/approve`.
     Assert the state-handler response was sent AND the approval closed
     the review AND the public post happened.
  3. **Chunked draft through transport:** force a draft text >
     `max_message_chars` (use a fake generator that produces a long
     string). Assert `FakeTransport.sent` contains ≥ 2 messages on the
     coaching channel before the operator's `/approve`, all bearing the
     continuation marker on chunks ≥ 2.
  4. **Lazy fetch through transport:** scripted events include
     `/adversarial` then `/approve`. Assert the adversarial message
     reached coaching before the approval, and the approval still
     closes the loop normally.

  Verify with `python -m pytest tests/integration/test_review_gate_flow.py -v`
  and a full suite run `python -m pytest tests/ -v` to confirm no
  regressions.

- [ ] **31.7 Remove `TelegramReviewGate` and clean up.**
  - Delete the `TelegramReviewGate` class from
    `src/modules/review_gate/__init__.py`.
  - Remove `TelegramReviewGate` from `__all__`.
  - Remove the `TelegramReviewGate` entry from `src/registry.py:27`.
  - Remove the `if class_name == "TelegramReviewGate":` arm from
    `src/orchestrator.py:1128`.
  - Search the tree for any remaining `TelegramReviewGate` references
    (`Select-String -Path p:\shared\diplomat -Pattern "TelegramReviewGate" -Recurse | Where-Object { $_.Path -notlike "*DEVLOG*" -and $_.Path -notlike "*DEVPLAN.md" }`)
    — only mentions in DEVLOG_archive.md, DEVPLAN.md history, and
    DECISIONS.md historical entries are allowed.
  - Re-run `python -m pytest tests/ -v` and confirm everything still
    passes.

- [ ] **31.8 Doc updates + close §4a/b/c + DEVLOG/DECISIONS entries.**
  - **`ARCH_review_gate.md`** — full rewrite. New public API spec
    (`submit` + `handle_command`), `Transport` dependency, chunking
    contract, lazy fetch contract, command pass-through behavior.
    Replace the `TelegramReviewGate` section with `OperatorReviewGate`.
  - **`ARCHITECTURE.md`** — update coupling notes. Replace the
    "Review Gate ↔ Transport: moderate — Review Gate uses
    toolkit/telegram_client for its own UI" bullet with
    "Review Gate ↔ Transport: tight — `OperatorReviewGate` consumes the
    pipeline's `Transport` for coaching-channel I/O. No direct
    `toolkit/telegram_client` dependency." Add a "Review Gate ↔
    Pipeline.dispatch_operator" bullet noting the handle_command
    routing.
  - **`NEXT_STEPS.md`** — close §4a, §4b, §4c. Mark each item resolved
    with a one-line reference to Phase 31. §4d (Pi re-test) stays open.
    Move §4 from the Tier 1 sequencing recommendation now that 4a/b/c
    are gone.
  - **`DEVLOG.md`** — append a `## Phase 31 close (YYYY-MM-DD)` entry
    summarizing: what shipped, files touched, tests added, decisions
    D-39 through D-43 (linked to DECISIONS.md).
  - **`DECISIONS.md`** — add D-39 through D-43 entries with rationale
    (no buttons, lazy fetch, single-pending guard, chunk-mid-fail
    behavior, hard rename).
  - **`README.md`** — update the doc-inventory table if the
    `ARCH_review_gate.md` row needs a status bump.
  - **`PROJECT.md` "Review Gate" line under MVP Definition** — no edit
    expected (still `TelegramReviewGate` in the historical sense is
    fine to reword to `OperatorReviewGate` if it's mentioned explicitly).
  - Bump the test count in `ARCHITECTURE.md` Testing Status row if it's
    tracked.

  Verify by reading each updated doc; no test run needed for this step.

### Verification

After all 8 steps:

```
python -m pytest tests/ -v
```

All tests pass. New tests:
- `tests/test_review_gate_chunking.py` — `chunk_text` unit coverage.
- `tests/test_review_gate.py` — `OperatorReviewGate` covers happy
  paths, lazy fetch, chunking, timeout, concurrent-submit guard,
  non-review command pass-through.
- `tests/test_pipeline.py` — `dispatch_operator` review-gate routing.
- `tests/integration/test_review_gate_flow.py` — end-to-end
  through `EventDrivenFlow` with `FakeTransport`.

Manual Pi smoke is **not** part of this phase — it lives as NEXT_STEPS
§4d (operator-driven re-run of the coached game with the new gate).
That's the next session's work.

<!-- history -->

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
