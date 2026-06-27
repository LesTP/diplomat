# Diplomat — Decision Log

<!-- Record non-trivial design and implementation decisions here.
     Use the full template for genuine design forks with trade-offs.
     For reactive decisions during Refine work, a one-line note in
     the DEVLOG is sufficient — don't over-use this file.

     Once Closed, don't reopen unless new evidence appears. -->

D-1: Toolkit integration over direct SDK dependencies
Date: 2026-05-24 | Status: Closed
Priority: Critical
Decision: All LLM calls go through toolkit/llm_client and all Telegram I/O goes through toolkit/telegram_client. No direct imports of `anthropic`, `openai`, or `python-telegram-bot` SDKs. Cost governance via toolkit/cost_accountant.
Rationale: Three sibling projects (Phosphene, Codexbot, TGBot) already consume toolkit. Using the same abstractions gives Diplomat provider rotation, rate-limit handling, cost tracking, and message formatting for free. Eliminates redundant SDK integrations.
Revisit if: Diplomat needs a toolkit capability that doesn't exist yet (e.g., structured output enforcement) and adding it to toolkit is higher cost than a local workaround.

D-2: Single LLMAnalyst implementation parameterised by provider
Date: 2026-05-24 | Status: Closed
Priority: Important
Decision: One `LLMAnalyst` class used for both primary and secondary analysis, configured with different `LLMConfig` objects (different providers, same interface). Not separate `ClaudeAnalyst` / `OpenAIAnalyst` classes.
Rationale: The analysis logic is identical — only the provider differs. Provider selection is a config concern, not a code concern. Adding a third analyst (e.g., Google) is a pipeline.yaml change, not a new class.
Revisit if: Provider-specific features (e.g., Claude's extended thinking) become important for analysis quality and can't be handled through toolkit/llm_client's interface.

D-3: Python as implementation language
Date: 2026-05-24 | Status: Closed
Priority: Critical
Decision: Python for all modules. Async throughout (asyncio).
Rationale: Consistent with toolkit (Python), good Telegram libraries, easy SQLite handling, good fit for Pi deployment. Same language as all sibling projects.
Revisit if: Performance on Pi becomes a problem, or a better-supported SDK appears in another language.

D-4: SQLite as sole persistence layer
Date: 2026-05-24 | Status: Closed
Priority: Important
Decision: Single SQLite file for all state (events, domain tables, coaching, intelligence, reviews).
Rationale: Simplest option that survives restarts. No external database dependencies. Fits the single-process, single-machine model. Same pattern as Codexbot.
Revisit if: Concurrent write contention becomes a real problem, or state needs to be shared across machines.

D-5: Review gate enabled by default
Date: 2026-05-24 | Status: Closed
Priority: Important
Decision: `review_gate.enabled: true` for the first game. No autonomous posting.
Rationale: First game is about calibrating the faction prompt and building operator trust. The edit log from the review gate is the primary feedback mechanism for prompt improvement.
Revisit if: The operator consistently approves without edit for multiple consecutive rounds, indicating the prompt is well-calibrated.

D-6: Extraction remains stateless
Date: 2026-05-25 | Status: Closed
Priority: Important
Decision: The Extraction module processes one supplied text batch at a time and does not own debounce windows, batching, or event scheduling.
Rationale: `ARCH_extraction.md` already defines independent `extract()` calls, and Orchestrator has the pipeline context needed to batch transport events. Keeping Extraction stateless makes it easy to test with fake LLM responses and avoids coupling it to round timing before Orchestrator is implemented.
Revisit if: Real game traffic shows that extraction quality depends on stateful message accumulation that cannot be represented by Orchestrator-provided batches.

D-7: Coaching remains a pure config-driven parser
Date: 2026-05-25 | Status: Closed
Priority: Important
Decision: Phase 3 will implement Coaching as a stateless parser that loads tag routes and command allowlists from `config/coaching_routes.yaml`; persistence, command dispatch, and INTEL forwarding stay with later Orchestrator wiring.
Rationale: `ARCH_coaching.md` defines Coaching as pure parsing with no state. Keeping routing data in config preserves domain flexibility and makes Phase 3 testable without storage or Telegram dependencies.
Revisit if: Operator coaching requires durable queue semantics before Context Assembler or Orchestrator integration.

D-8: Phase 4 targets Telegram bot transport plus CLI test transport
Date: 2026-05-25 | Status: Closed
Priority: Important
Decision: Phase 4 will implement the platform-neutral Transport contract, `CLITransport` for deterministic local testing, and `TelegramBotTransport` through `toolkit/telegram_client`. `TelethonUserTransport` remains deferred unless the game moderator confirms bot-to-bot messaging is blocked.
Rationale: MVP scope requires Telegram bot I/O and all Telegram access must go through toolkit. CLI transport gives repeatable coverage without live credentials. Building Telethon now would add a direct SDK dependency and expand scope before the account-mode question is answered.
Revisit if: The moderator requires a user account, or toolkit lacks the Telegram client surface needed for polling and sending.

D-9: Persona strips CURRENT ROUND CONTEXT section from faction_prompt.txt
Date: 2026-05-25 | Status: Closed
Priority: Important
Decision: `faction_prompt.txt` may contain a `## CURRENT ROUND CONTEXT` section. `FileBasedPersona.get_base_prompt()` returns everything before that marker, allowing the operator to optionally include a human-readable placeholder in the file without it leaking into the base prompt. `build_round_context()` constructs the round context string dynamically from caller-supplied inputs.
Rationale: Keeps the faction prompt file self-documenting (the operator can annotate the expected round context format) while ensuring the dynamic context is always freshly assembled from live state, not read from a static file that may be stale.
Revisit if: The file format needs to support multiple sections or variable interpolation within the base prompt.

D-10: Generation parses review-gate JSON locally
Date: 2026-05-25 | Status: Closed
Priority: Important
Decision: Phase 8 will implement a single `LLMGenerator` that consumes `DecisionContext` and parses review-gate JSON (`response`, `reasoning`) locally while preserving a plain-text mode when review gate output is disabled.
Rationale: `toolkit/llm_client` returns plain text and the Review Gate needs both a draft and reasoning for human approval. Keeping parsing local mirrors Extraction and Analyst, avoids a toolkit contract expansion, and preserves provider selection as configuration/dependency injection.
Revisit if: toolkit adds first-class structured output with portable schema enforcement across providers.

D-11: Review gate timeout is configurable auto-block
Date: 2026-05-25 | Status: Closed
Priority: Important
Decision: Phase 9 will resolve the provisional Review Gate timeout contract with a configurable `timeout_seconds`. When set, `TelegramReviewGate.submit()` auto-blocks after the timeout and logs the blocked decision; when unset, it waits indefinitely for an operator command.
Rationale: Auto-block is the safest default for a diplomacy agent because it prevents stale or unreviewed drafts from being posted after a round boundary. Keeping the timeout optional preserves local/manual workflows where the operator intentionally wants the gate to wait.
Revisit if: Orchestrator round management needs carry-forward drafts or explicit operator escalation instead of blocking.

D-12: Adversarial remains optional, stateless, and locally schema-validated
Date: 2026-05-26 | Status: Closed
Priority: Important
Decision: Phase 10 will implement `LLMAdversarialReader` as an independent optional module that validates JSON analysis locally against `config/schemas/adversarial.json`, while leaving skip behavior and persistence to the Orchestrator.
Rationale: `ARCH_adversarial.md` defines the reader as standalone and optional, and `toolkit/llm_client` returns plain text. Local validation matches the established Extraction, Analyst, and Generation pattern without expanding toolkit contracts or coupling the module to pipeline state.
Revisit if: toolkit adds portable structured output enforcement or Orchestrator needs adversarial reads to own persistence.

D-13: External dependency fakes must be derived from source, not from prose
Date: 2026-05-27 | Status: Closed
Priority: Critical
Decision: When a module depends on an external library (toolkit, etc.), test fakes must match the real library's type signatures — not the ARCH file's prose description. If the library is not importable in the worker's environment, the worker must read the library's source files (ARCH docs, type definitions, function signatures) from the shared filesystem to derive correct fakes. Unverified fakes must be logged as warnings in DEVLOG.
Rationale: Phases 2–11 built fakes from ARCH prose ("calls toolkit/llm_client.complete()") without verifying the real function signature. This produced three integration mismatches: Message objects vs dicts, LLMConfig vs plain dict, LLMResponse vs plain str. All 165 unit tests passed against incorrect fakes. The mismatches were only caught during the post-implementation dependency probe — after 11 phases of code had been written against the wrong interface. An adapter layer (ToolkitLLMAdapter, DiplomatCostGate) was required to bridge the gap.
Revisit if: The governance framework adds a structural mechanism (interface snapshot files, cross-project contract tests) that makes this rule redundant.

D-14: Phase 12 moves Orchestrator persistence fallbacks into State Manager
Date: 2026-05-27 | Status: Closed
Priority: Important
Decision: Phase 12 will expand `SQLiteStateManager` with explicit persistence methods for coaching, intelligence, game-state key/value updates, adversarial reads, and coaching consumption, then remove the Orchestrator's raw SQLite fallback code for those operations.
Rationale: The Orchestrator should compose modules, not own persistence details for State Manager tables. Making these operations public State Manager APIs keeps table ownership in one module, removes duplicate SQLite write paths, and makes Orchestrator tests use the same contract production code uses.
Revisit if: State Manager persistence needs become large enough to justify a separate repository/service boundary rather than a module API expansion.

D-15: Phase 13 integration tests use injected fakes only
Date: 2026-05-27 | Status: Closed
Priority: Important
Decision: Phase 13 pipeline integration tests will exercise cross-module Diplomat behavior through Orchestrator wiring while injecting `TestTransport`, `FakeLLMClient`, `FakeCostAccountant`, and `StubAnalyst`; they will not call real toolkit providers or Telegram APIs.
Rationale: Layer 3 tests should prove Diplomat's pipeline data flow, persistence effects, and failure handling deterministically. Real provider and Telegram compatibility is already covered by adapter probes and belongs to deployment/integration validation, not the core regression suite.
Revisit if: A stable local toolkit simulator becomes available and can run without credentials or network access.

D-16: Phase 14 transcript replay stays deterministic and fake-backed
Date: 2026-05-27 | Status: Closed
Priority: Important
Decision: Phase 14 will add synthetic JSON transcripts that intentionally match `RuleBasedExtractor` regex patterns, replay them through the Phase 13 fake-backed Orchestrator integration fixture, and assert on persisted final state rather than generated prose quality.
Rationale: Transcript replay should validate full-pipeline state accumulation across round boundaries without introducing live API calls, prompt variability, or Telegram dependencies. Keeping fixture text aligned to deterministic rule-based extraction makes failures actionable and keeps Layer 3 regression tests stable.
Revisit if: Layer 3 replay needs to validate LLM extraction quality rather than pipeline state flow; that belongs in Layer 2 prompt regression or a separately costed integration suite.

D-17: Phase 15 smoke setup uses OpenAI-only cheap config first
Date: 2026-05-27 | Status: Closed
Priority: Important
Decision: Phase 15 will prepare a dedicated smoke-test pipeline config that uses OpenAI `gpt-4.1-mini` for primary and secondary LLM roles, keeps `RuleBasedExtractor`, enables the live Telegram review gate, disables adversarial review, and applies tight per-round/session budgets.
Rationale: The smoke test needs to validate real Telegram, toolkit imports, LLM calls, and review-gate wiring with the smallest practical credential and cost surface. A separate config preserves the production-oriented `pipeline.yaml` while giving the Pi operator a low-cost startup path.
Revisit if: OpenAI credentials are unavailable during deployment or the cheapest model fails required response quality for smoke validation.

D-18: Phase 16 deployment readiness is operational hardening only
Date: 2026-05-27 | Status: Closed
Priority: Important
Decision: Phase 16 will limit work to regression coverage for smoke-test fixes, two-channel Telegram deployment documentation, a Raspberry Pi systemd unit, production log cleanup, and final regression verification. It will not tune game rules, faction strategy, round mechanics, or prompt content.
Rationale: The live smoke test proved the core pipeline works. The remaining gap before deployment is operational readiness and test coverage for the fixes found during smoke testing; game-specific configuration should stay a deployment-time concern.
Revisit if: Deployment reveals a runtime failure that cannot be fixed without changing pipeline contracts or game-specific behavior.

D-19: Phase 17 prompt regression stays module-scoped and adapter-compatible
Date: 2026-05-27 | Status: Closed
Priority: Important
Decision: Phase 17 will build Layer 2 prompt regression infrastructure around module-level scenarios, structural JSON-path checks, and optional LLM-as-judge checks that use the same injected `llm_client.complete(messages, config, tier)` adapter shape as Diplomat modules. It will not exercise the full Orchestrator pipeline or import provider SDKs/toolkit directly.
Rationale: Prompt regression needs to catch prompt-quality regressions with a smaller, more targeted surface than Layer 3 pipeline replay. Keeping the harness module-scoped makes failures actionable, while reusing the adapter shape preserves the no-direct-SDK contract and lets the suite run on the Pi where toolkit is installed.
Revisit if: Prompt regressions primarily arise from cross-module context assembly rather than individual module behavior.

D-20: Per-event extraction replaces cancel-and-replace debounce
Date: 2026-05-28 | Status: Closed
Priority: Critical
Decision: Rewrite Orchestrator message extraction from a single `_debounce_task` that cancels the previous message's extraction to `_extraction_tasks: set[asyncio.Task]` where each message gets its own independent extraction task with self-cleanup via `done_callback`.
Rationale: Self-play Run 2 revealed that the cancel-and-replace pattern silently dropped all messages except the last in a burst. In a 3-faction game, only `[ROUND END]` was ever extracted because it arrived last and cancelled all faction messages. This is also a production bug — in a real Telegram game, multiple players could send messages within the debounce window. The per-event model ensures every message is extracted regardless of arrival timing.
Revisit if: Extraction costs become a concern under genuine burst traffic (e.g., 50+ messages in seconds). In that case, consider batching rather than cancellation.

D-21: All LLM modules use toolkit structured_call
Date: 2026-05-28 | Status: Closed
Priority: Important
Decision: Rewire all four LLM-consuming modules (extraction, analyst, adversarial, generation) to use `toolkit.structured_llm.structured_call()` instead of manual prompt assembly + parse + validate patterns. `structured_call` handles schema injection into the system prompt, few-shot example formatting, JSON parsing, schema validation, and retry-with-error-feedback.
Rationale: Each module independently reimplemented the same pattern: build messages with schema, call LLM, parse JSON, validate, handle errors. Self-play Run 3 showed that ~30% of extraction calls failed schema validation when using narrative-only prompts. `structured_call` with few-shot examples and retry reduced failures to near zero. Centralizing this in toolkit eliminates duplication and ensures consistent enforcement across all modules.
Revisit if: Provider-native structured output (OpenAI `response_format: json_schema`) becomes available through toolkit — would replace the prompt-based enforcement with token-level enforcement.

D-22: Extraction tracks proposals, not just binding commitments
Date: 2026-05-28 | Status: Closed
Priority: Important
Decision: Broaden the extraction prompt's definition of a "promise" to include concrete proposals with specific terms, conditional offers, and demands — not just explicit binding commitments.
Rationale: Self-play Run 6 (Three-Party Coalition) tracked only 1 promise despite 12 messages full of specific proposals ("I propose we split 70/14"). The original definition ("a promise requires a clear commitment") was too strict for negotiation language where parties make offers, demands, and conditional proposals before anything becomes binding. Tracking proposals gives the intelligence pipeline material to work with.
Revisit if: Over-extraction becomes a problem (too many low-quality promise entries). May need a confidence threshold or a separate "proposals" entity type.

D-23: Scenario compiler is a production tool, not test infrastructure
Date: 2026-05-28 | Status: Closed
Priority: Important
Decision: Place the scenario compiler in `src/tools/` rather than `tests/self_play/`. It is an operator-facing pre-game preparation tool, not test scaffolding.
Rationale: The scenario compiler converts a narrative game description into scored persona files with point tables, BATNAs, deception tactics, and game-mode-specific behavioral instructions. This is exactly what a human operator would do before a real game — read the rules, assess their faction's interests, and prepare a strategy. Placing it in `src/tools/` signals that it's part of the operational toolkit, usable both in self-play and in real game preparation.
Revisit if: The compiler grows complex enough to warrant its own module with tests alongside (currently tested via `tests/test_scenario_compiler.py`).

D-24: Game-mode classification drives persona behavioral style
Date: 2026-05-28 | Status: Closed
Priority: Important
Decision: The scenario compiler classifies each scenario as cooperative, competitive, or mixed, and the persona template injects mode-specific behavioral instructions accordingly. Competitive mode instructs agents to maximize their own score, exploit others' urgency, and threaten to walk away. Cooperative mode instructs mutual value creation while maximizing own share.
Rationale: Self-play Runs 1-4 showed that LLMs default to cooperative behavior regardless of scenario structure. Without explicit competitive instructions, agents converge on reasonable deals too quickly and never employ deception or hardball tactics. The game-mode classification lets the scenario structure (not a global toggle) determine how competitive agents should be. Dirty bargaining Run 5 with explicit competitive personas produced dramatically more strategic play including successful bluffs and progressive concession tactics.
Revisit if: A more nuanced per-issue competitiveness model is needed (some issues cooperative, others zero-sum within the same negotiation).

D-25: Phase 21 cleanup stays in Build regime
Date: 2026-05-31 | Status: Closed
Priority: Important
Decision: Phase 21 will execute the existing module-boundary cleanup plan as nine state-machine-tracked Build steps, with review and close handled by the autonomous loop rather than as an executable checkbox.
Rationale: The work is already scoped to concrete API cleanup, adapter attribution plumbing, and duplicate wiring removal. Keeping review/close out of the executable checklist prevents the loop from treating governance actions as code steps and lets `STOP_BEFORE_REVIEW=true` stop at the intended review gate.
Revisit if: A Phase 21 step requires a contract change outside Orchestrator/self-play/LLM adapter boundaries.

D-26: Phase 22 extracts Pipeline and Flow in Build regime
Date: 2026-05-31 | Status: Closed
Priority: Important
Decision: Phase 22 will split Orchestrator into a per-agent `Pipeline` capability interface plus `Flow` scheduling strategies, with review and close handled by the autonomous loop rather than as an executable checkbox.
Rationale: Production and self-play already share the same module capabilities but differ in scheduling. Making that boundary explicit lets new applications add a Flow without copying Orchestrator internals or inventing a parallel driver.
Revisit if: Extraction exposes a cross-module contract change that cannot be contained inside Orchestrator, Pipeline, Flow, and self-play wiring.

D-27: Phase 23 scoring expansion stays diagnostic-only
Date: 2026-05-31 | Status: Accepted
Priority: Important
Decision: Phase 23 will add Pareto efficiency and four deterministic process signatures as post-game diagnostic outputs only. It will not change agent prompts, negotiation behavior, provider routing, or live run protocol.
Rationale: The scoring lenses are meant to improve assessment quality before further tuning. Keeping them out of runtime decision-making avoids coupling evaluation metrics to agent behavior while tests lock down the calculations.
Revisit if: A later tuning phase explicitly uses these metrics as feedback signals for prompt or strategy changes.

D-28: Phase 24 closes small tooling debt in Build regime
Date: 2026-05-31 | Status: Closed
Priority: Important
Decision: Phase 24 will execute a fixed Build checklist of small standalone improvements: toolkit OpenAI dispatch tests, asymmetric BATNA CLI support, force-clamped BATNAs, game-mode runtime override, extraction examples moved to config JSON, and schema-derived entity type references. Review and close remain state-machine actions, not executable checklist items.
Rationale: These items are already scoped, testable, and do not require live provider calls or product judgment. Keeping them in one Build phase closes known tooling and Level 1 modularization debt while preserving the autonomous loop's review gate.
Revisit if: Any step requires expanding runtime contracts outside the named CLI/self-play/extraction/reconciliation surfaces.

D-29: Phase 25 makes tmux the service supervisor
Date: 2026-06-01 | Status: Closed
Priority: Important
Decision: Phase 25 will rewrite `tools/service.sh` around the working tmux window pattern. The default supervising session is `bot`, overridable with `BOT_TMUX_SESSION`; commands skip `sudo -u claude` when already running as `claude`; missing sessions fail with a clear create-session command instead of auto-creating.
Rationale: The 2026-05-31 smoke showed `nohup` children die when started through `incus exec` because the transient cgroup is torn down. A tmux pane in the long-lived `bot` session survived the same launch path, and making that pattern the canonical service interface keeps Pi operations to one wrapped command while preserving a test override.
Revisit if: The deployment host moves away from the long-lived tmux supervision model or the operator standardizes on systemd outside `incus exec`.

D-30: Phase 26 adds structured per-event logging in Build regime
Date: 2026-06-01 | Status: Closed
Priority: Important
Decision: Phase 26 will add structured, grep-able logging across startup, Telegram transport, event-driven flow, pipeline routing, extraction, round boundaries, and response completion. Logs will stream to stdout/stderr through the normal service `tee` path, default to INFO, and support `DIPLOMAT_LOG_LEVEL` override plus config-level defaults.
Rationale: The Phase 19 smoke exposed a routing/tagging failure that required temporary `print` instrumentation to diagnose. Making per-event logging part of the runtime contract gives future smokes an auditable diagnostic surface without ad-hoc code changes or duplicate log-file writers.
Revisit if: The runtime moves to a structured log collector that requires JSON output or a non-stream handler.

D-32: Phase 28 coached-game uses module_overrides injection, not YAML swap
Date: 2026-06-02 | Status: Closed
Priority: Important
Decision: `coached_game.py` injects `TelegramReviewGate` for the coached faction via `module_overrides["review_gate"]` in the `Orchestrator` constructor rather than writing a custom pipeline YAML with `class: TelegramReviewGate`. `FakeTelegramReviewGate` is a dedicated dry-run stand-in (not `AutoApproveReviewGate`) so test assertions can distinguish the coached faction's gate from auto-approve by type.
Rationale: `module_overrides` is the existing pattern for injecting test doubles (`TestTransport`). Using the same mechanism for the review gate keeps `_generate_faction_config()` unchanged and makes the coaching wiring visible in one place (`setup()` override). A dedicated fake class avoids coupling test assertions to production-only imports while keeping the dry-run path completely free of Telegram dependencies.
Revisit if: A future coached-game variant needs to configure the review gate primarily through YAML (e.g., different timeout per run file) — at that point, adding `TelegramReviewGate` to the YAML registry becomes the cleaner path.

D-31: Phase 27 stays metric-only in Build regime
Date: 2026-06-01 | Status: Closed
Priority: Important
Decision: Phase 27 will add baseline-normalized no-deal-aware scoring metrics, report rendering, a historical backfill tool, and documentation updates without changing scorer prompts, agent behavior, provider routing, or partial-consensus deal detection.
Rationale: Run 9 showed the current `pareto_efficiency` metric ranks no-deal outcomes by BATNA height rather than negotiated improvement. Companion fields can correct post-game interpretation while preserving the existing all-faction convergence scorer and keeping partial-consensus scoring as a separate Phase 28 candidate.
Revisit if: Later tuning work needs the normalized surplus metrics to influence prompts or runtime negotiation strategy rather than remain diagnostic outputs.

D-33: Phase 29 baseline scorers stay diagnostic-only in Build regime
Date: 2026-06-03 | Status: Closed
Priority: Important
Decision: Phase 29 will add equal-split, BATNA-clearing, and Nash bargaining baseline scorers to the self-play scoring pipeline, plus report rendering, backfill support, and documentation updates, without changing negotiation behavior, scenario compilation, or provider routing.
Rationale: The new metrics answer "did negotiation outperform naive strategies?" in a way that is comparable across scenarios while keeping the scoring layer purely observational. That preserves the existing runtime contract and keeps the phase inside the current self-play/test surface.
Revisit if: A later tuning phase needs these baselines to influence prompts or live decision-making rather than remain post-game diagnostics.

D-34: Phase 30 keeps OpenRouter support as a thin OpenAI-compatible adapter
Date: 2026-06-03 | Status: Open
Priority: Important
Decision: Phase 30 will add `OpenRouterProvider` as a thin wrapper around the OpenAI-compatible client, wire `"openrouter"` through provider selection and self-play env loading, add representative OpenRouter pricing entries, and keep the phase scoped to provider plumbing, probe support, and docs.
Rationale: OpenRouter is a provider concern, not a new runtime behavior. Keeping the phase narrow preserves the existing `toolkit/llm_client` contract, avoids broader refactors, and lets the phase land as a pure build step.
Revisit if: OpenRouter needs provider-specific behavior beyond OpenAI-compatible request/response handling or a later provider abstraction refactor is warranted.

D-35: Phase 31 stays scoped to transport-routed operator review handling
Date: 2026-06-04 | Status: Closed
Priority: Important
Decision: Phase 31 will replace `TelegramReviewGate` with a transport-routed `OperatorReviewGate`, add message chunking, lazy fetch for reasoning/adversarial sections, and dispatcher pass-through for non-review slash commands. Buttons and callback-query UX remain out of scope.
Rationale: The current product issue is not "more UI", it is that the review gate is too tightly coupled to Telegram polling and a single oversized message. Keeping the phase limited to transport reuse and command routing fixes the actual failure modes while preserving the existing operator text-command workflow.
Revisit if: A later operator UX pass explicitly adds callback-query support or another review-channel interaction model.

D-39: No inline buttons in Phase 31 OperatorReviewGate
Date: 2026-06-04 | Status: Closed
Priority: Important
Decision: Telegram inline buttons are out of scope for Phase 31. Text commands (`/approve`, `/edit:`, `/block`, `/reasoning`, `/adversarial`) cover the same UX surface.
Rationale: `toolkit/telegram_client` does not surface `callback_query` updates. Building that pipeline is a separate project. Text commands have the same result with no new platform surface.
Revisit if: A later operator UX pass adds callback_query support to the toolkit transport.

D-40: Lazy fetch for Reasoning and Adversarial sections
Date: 2026-06-04 | Status: Closed
Priority: Important
Decision: Only the draft is pushed eagerly on `submit()`. Operator types `/reasoning` or `/adversarial` to fetch deeper context on demand.
Rationale: Reduces noise on routine approvals where the operator only needs the draft. Avoids bloating every review message with sections that may not be needed.
Revisit if: Operator feedback shows they always want reasoning/adversarial inline — at that point, make eager push the default and remove lazy-fetch path.

D-41: Concurrent submit raises RuntimeError
Date: 2026-06-04 | Status: Closed
Priority: Important
Decision: `OperatorReviewGate` holds a single `_pending` slot. Concurrent `submit()` while a review is in progress raises `RuntimeError("OperatorReviewGate has a pending review")`.
Rationale: The current pipeline never concurrent-submits per agent. Raising hard is the correct contract signal if that invariant ever breaks, rather than silently queuing or overwriting.
Revisit if: The pipeline architecture changes to support concurrent per-agent response pipelines — upgrade the single slot to a keyed dict at that point.

D-42: Chunk-mid-send failure aborts review with blocked decision
Date: 2026-06-04 | Status: Closed
Priority: Important
Decision: If transport.send() raises during the eager draft send, `submit()` returns `ReviewDecision(action="blocked", edit_notes="transport error: <e>")`, clears `_pending`, logs via state_manager, then re-raises after logging.
Rationale: Transport already handles retries on individual sends. If it still fails, the review session collapses cleanly rather than leaving partial messages that confuse the operator. The caller sees the exception and can surface it.
Revisit if: A future transport layer adds its own idempotent retry and the abort-on-partial-send behavior becomes wrong.

D-43: Hard rename TelegramReviewGate → OperatorReviewGate
Date: 2026-06-04 | Status: Closed
Priority: Important
Decision: All production code, tests, configs, and registry entries rename `TelegramReviewGate` to `OperatorReviewGate`. No back-compat shim or re-export.
Rationale: There is only one in-tree consumer outside the production config (`coached_game.py`). Back-compat shims are anti-modular and would survive into future phases. The rename is the correct permanent signal that the gate is no longer Telegram-specific.
Revisit if: An external consumer (outside this repo) depended on the old name — would need a shim there, not here.

D-44: Coached-mode operator-input bridge
Date: 2026-06-04 | Status: Closed
Priority: Important
Decision: `CoachedGameEnvironment` spawns a background `_listen_for_operator` task that consumes the wrapped `TelegramBotTransport.listen()` iterator and forwards operator-tagged events to the coached agent's `pipeline.dispatch_operator`. The task is cancelled in `teardown`.
Rationale: Phase 31's `OperatorReviewGate` is a passive handler that relies on `Pipeline.dispatch_operator → review_gate.handle_command`. `EventDrivenFlow.process_event` provides that routing in production; `RoundSteppedFlow` does not, and `CoachedGameTransport` only consumes the local injected-event queue. Without a dedicated bridge, the coached game hangs at the first review prompt (observed live 2026-06-04 during Run 13 setup — operator typed /state, /status, /approve to no effect). Reusing `TelegramBotTransport.listen()` rather than re-implementing chat-id routing keeps the bridge minimal and consistent with the production path.
Revisit if: A future `RoundSteppedFlow` consumer needs operator-input bridging too — promote `_listen_for_operator` to a flow-level helper or a generic `OperatorBridge` module rather than duplicating in each environment.

D-45: No controlled re-test of Gemini coached-vs-uncoached defection
Date: 2026-06-04 | Status: Closed
Priority: Routine
Decision: Do not run a second uncoached Gemini-flash Water Rights symmetric game to test whether Run 13's R3→R4 defection (γ pivoting from Heavy-Downstream to Shared) is reproducible vs Run 12b's clean Pareto deal on the same model + same BATNAs.
Rationale: Operator 2026-06-04: `I do suspect that these differences are also stochastic and harness-related, not just a property of the model so don't want to pursue this right now.'' Two single-game data points cannot distinguish stochasticity from coached-pathway timing from generation.txt conciseness pressure. A meaningful answer would require N≥3 per condition (uncoached vs coached, with and without conciseness rewrite), which is an experiment, not a debug. Skip until a future Gemini run on this model shows a third defection or until coached-vs-uncoached deltas are themselves the experimental subject.
Revisit if: A future Gemini run on Water Rights or similar shows another R3→R4 defection — at which point the pattern is worth characterizing systematically.

D-46: Toolkit-level Telegram auto-chunking
Date: 2026-06-04 | Status: Closed
Priority: Important
Decision: Move oversized Telegram message splitting out of Diplomat's review gate and into the shared toolkit transport. `TelegramClient.send_message` now auto-chunks oversize content, and `split_message` remains available for explicit chunking use cases.
Rationale: Review-gate chunking duplicated transport concerns and encouraged callsites to own a Telegram-specific limit that belongs in the shared transport layer. Centralizing the behavior makes every consumer get the same 4096-char handling for free and removes a class of review-gate-only bugs.
Revisit if: The shared toolkit transport changes its message-splitting contract or a downstream consumer needs custom chunk boundaries that differ from the toolkit default.

D-47: Coached-game startup drain window
Date: 2026-06-04 | Status: Closed
Priority: Important
Decision: `CoachedGameEnvironment._listen_for_operator` drains stale Telegram updates for one second on startup before it forwards operator-tagged commands into `pipeline.dispatch_operator`.
Rationale: A previously killed coached session can leave stale `/approve`-style updates queued in Telegram. Draining the initial burst avoids poisoning the next round's first review prompt while preserving the normal forwarding path after the window expires.
Revisit if: The Telegram update backlog behavior changes or a future flow needs a different drain duration / start-up policy.

D-48: Phase 33 stays inside existing review-gate and state-manager surfaces
Date: 2026-06-07 | Status: Closed
Priority: Important
Decision: Phase 33 will add `/revise:` and edit-log classification without introducing a new runtime module or changing the ARCHITECTURE implementation-sequence status. The work stays within the existing Pipeline, Review Gate, State Manager, prompt-regression, and CLI surfaces.
Rationale: The requested behavior is a refinement of the current coached review loop, not a platform or transport expansion. Keeping the phase scoped to existing module boundaries avoids unnecessary architecture churn and keeps the build phase testable in place.
Revisit if: The revise/classification work requires a new cross-cutting runtime boundary or module ownership split.

D-49: Raw `/edits-summary` fast-path before coaching parse
Date: 2026-06-07 | Status: Closed
Priority: Important
Decision: Treat `/edits-summary` as an operator command in the orchestrator before passing the message into `TaggedCoachingParser`.
Rationale: The shared coaching parser classifies hyphenated slash commands as free coaching, which would bypass the operator dispatcher. Intercepting the exact raw command preserves the intended slash-command UX without changing the parser contract for other inputs.
Revisit if: The shared parser grows native support for hyphenated operator commands and the fast-path becomes redundant.

D-50: Phase 34 bare-prompt mode stays all-or-none per game
Date: 2026-06-08 | Status: Closed
Priority: Important
Decision: Phase 34 will implement bare-prompt ablation as an all-bare or all-full game-level toggle only. Mixed bare/full factions in the same game stay out of scope, and the implementation remains self-play/ablation only rather than wiring production defaults.
Rationale: The experiment’s question is whether the harness contributes at the game level. Keeping the toggle per-game avoids confounding the comparison with mixed-mode interactions and preserves a clean baseline against the existing full harness.
Revisit if: A later experiment explicitly needs faction-level mixed-mode ablation or production exposure.

D-51: Random-restart hill-climb as scenario search algorithm
Date: 2026-06-10 | Status: Closed (Phase 35 complete 2026-06-10; superseded by D-54 SA improvements)
Priority: Routine
Decision: Phase 35 `scenario_builder.py` uses random-restart hill-climb (single-cell score-table flips, plateau-triggered restarts) as the search algorithm.
Rationale: The fitness landscape over integer scoring tables is discrete and relatively low-dimensional (≤4 factions × ≤4 issues × score range 1–10). Random-restart hill-climb is simple to implement, fully deterministic under a seed, and adequate for this domain. Simulated annealing or genetic algorithms add implementation complexity without clear payoff on a table this small.
Revisit if: Larger scenarios (6+ factions, 6+ issues) produce unacceptably long search times with hill-climb, indicating a need for a better-than-random global strategy.

D-52: Reuse verify_scenario_optimum.py pure functions without refactoring
Date: 2026-06-10 | Status: **Superseded by D-58** (2026-06-21)
Priority: Routine
Decision: Phase 35 imports `enumerate_deals`, `find_pareto_frontier`, `faction_score`, `beats_batna`, and `find_priority_issues` directly from `src/scenario_authoring/verify_scenario_optimum.py` rather than moving them to a shared library.
Rationale: These functions are pure (no I/O, no dependencies), already tested in place, and their home in the test tree is appropriate — they validate game outcomes. Moving them to `src/` would be premature abstraction and would force a test-infrastructure change. The fitness module simply imports from `tests/`.
Revisit if: A third consumer needs the same functions, at which point extracting to a shared utility module is justified.
Update (2026-06-21): superseded by D-58. The revisit trigger fired implicitly when direct-Python entry points (the Phase 3 scale probe) needed the production code to NOT depend on `tests/` to avoid sys.path workarounds. File moved to `src/scenario_authoring/verify_scenario_optimum.py`.

D-53: Logrolling and deception_tactics emitted as stubs in Phase 35
Date: 2026-06-10 | Status: Closed (Phase 35 complete 2026-06-10; stub approach still in place)
Priority: Routine
Decision: Phase 35's `scenario_builder.py` emits empty strings for `logrolling` and `deception_tactics` fields in generated personas. LLM narrative authorship of these fields is deferred to operator follow-up (or a future phase that extends the LLM compiler path).
Rationale: These fields are interpretive narrative, not derivable from scoring tables alone. Attempting LLM generation in the same phase conflates the constraint-satisfaction algorithm (pure, testable) with an LLM authoring step (non-deterministic, requires evaluation). Separating them keeps Phase 35 🔨 PURE BUILD with binary test signal.
Revisit if: A phase explicitly targets narrative quality of generated scenarios and needs integrated LLM authorship rather than post-processing.

D-54: Phase 36 scenario-search algorithm improvements
Date: 2026-06-10 | Status: Closed (Phase 36 complete 2026-06-11; validation PASSED in 3.6s)
Priority: Important
Decision: Phase 36 improves `scenario_builder` search in three orthogonal directions: (a) soft weighted-sum satisfaction replacing strict per-target AND, (b) simulated annealing in the local-move loop to escape plateaus, and (c) biased initialization seeding categorical constraints. These three improvements are implemented in the same phase; LLM-guided proposal is deferred.
Rationale: The strict AND satisfaction (`satisfies(0.10)` requiring every target within tolerance) produces no gradient for categorical targets (logrolling, priority_collision), causing the greedy hill-climb to get stuck in the 6-constraint operator spec. Weighted soft constraints give the optimizer a signal; SA acceptance allows escaping local optima; biased initialization reduces the restarts needed to find a good starting point. Together they are sufficient for 3×3×3 specs — no LLM dependency required, keeping the phase 🔨 PURE BUILD with deterministic test signal.
Revisit if: The improved search still fails on richer specs (4+ factions, 4+ issues), at which point LLM-guided scoring-table proposal becomes the next lever.
Update (2026-06-21): the revisit trigger fired at 4+ issues, but the resolution was NOT the predicted LLM-guided proposal. Phase 42 found the I-axis failure was spec-semantic (fixed absolute count targets, fixed by relative targets — D-59) plus a determinism confound, not a search-power deficit. Single-cell SA is retained; a broadened neighborhood was tried and rejected. See D-59.

D-55: Phase 38 pressure mechanisms stay in a small Build bundle
Date: 2026-06-11 | Status: Open
Priority: Important
Decision: Group round-cost decay, asymmetric clocks, and penalty floor into one build phase. Keep exogenous events and cascade scoring out of the bundle.
Rationale: The three mechanisms share the same pressure schema, persona rendering, and verifier surface, so bundling them minimizes repeated edits while keeping the phase testable. Exogenous events require round-aware BATNA recomputation and a different verifier shape, so they remain deferred.
Revisit if: the shared pressure surface proves larger than expected or Phase 38 starts to blur into the deferred mechanisms.

D-56: Project direction — negotiation benchmark over operator coaching product
Date: 2026-06-16 | Status: Open
Priority: Critical
Decision: Diplomat's primary purpose is now an **LLM negotiation benchmark** — a multi-model, multi-scenario evaluation harness for measuring negotiation skill across model classes. The operator coaching product (live Telegram games, coached self-play with `/revise:`, persona drift management, real-game deployment) is **deferred**, not abandoned: infrastructure stays in tree, but no new investment goes into the coaching loop until benchmark milestones land. Resolves the `RESEARCH_NOTES.md` Note 2 product-direction fork (Diplomat-as-coaching-tool vs Diplomat-as-research-benchmark) in favor of the benchmark direction.
Rationale: Runs 14, 15, 16, 17 were *de facto* benchmark work executed under coaching-product framing. The mismatch produced the agreeableness-bias structural problem (Note 2 §1) and the thrashing pattern (sessions producing surprising findings → new questions → new pivots → no thread closure). Explicitly committing to the benchmark direction (a) gives every queued experiment a yardstick — *does this produce differential model rankings or scenario-discrimination signal?* (b) unlocks work that the coaching framing was implicitly blocking (coalition-exclusion scoring, rank-based scoring lens, tournament harness, mixed-model populations as default rather than experimental), and (c) lets the queued coaching items (Run 13b, §4 Pi coaching loop, §5 Clankmates, §6 pricing audit-as-prod-budget-baseline) drop out of the immediate Tier-1 conversation without abandoning the infrastructure that supports them.

What changes downstream:
- **Promoted to Tier 1.** NEXT_STEPS §11 (competitive scoring — Path B coalition-exclusion engine, rank-based scoring lens, mixed-model populations), Phase 41/42 (scale-matrix verification enabling richer scenarios), scenario-class authoring (zero-sum / distributive / asymmetric-BATNA / hidden-value), provider-matrix expansion (R1 unblocked, Qwen, OpenAI o-series, Gemini-flash tier).
- **Demoted to deferred.** Run 13b (coached game `/revise:` validation), §4 coaching test loop on Pi, §5 Clankmates transport for game traffic, persona-rigidity/drift A/Bs (these were tunings for live-game performance — irrelevant if the benchmark uses fresh per-cell agents).
- **Unchanged.** Module architecture (Pipeline/Flow split), scenario compiler + reverse builder, self-play infrastructure, bare-mode plumbing, all four ASSESSMENT §3 scoring lenses (kept as cooperative measures; competitive measures added alongside, not replacing), toolkit dependency contract.
- **Reframed.** ASSESSMENT §5 workstream blocks: Block C (game creation, scoring, assessment) becomes the primary investment surface; Block A (architecture/memory) stays infrastructure; Block B (prompt tuning) demotes to "tunings that affect benchmark results" only — persona-tuning for live-game performance drops out.

Revisit if: (a) a real game opportunity emerges with a concrete deadline (e.g., Clanker Courts live deployment, a hosted multiplayer Diplomacy event) that makes the coaching product immediately useful, (b) benchmark findings stall — three+ consecutive experimental campaigns produce no new discrimination signal — suggesting the benchmark surface itself has hit a ceiling, or (c) external pressure makes the operator-coaching framing more valuable than the research framing (Meta product use case, paper deadline, etc.).

D-57: Decline `tools/` directory rename to `scripts/`
Date: 2026-06-21 | Status: Closed
Priority: Routine
Decision: The repo's top-level `tools/` directory (shell scripts + helper Python) stays as `tools/`. The Phase 1 motivation for considering a rename — ambiguity between `src/tools/` (the scenario package) and `tools/` (the shell dir) — is now obsolete because Phase 1 Commit 1 deleted `src/tools/`. The remaining `tools/` at root has one unambiguous meaning by convention.
Rationale: The rename's blast radius is ~25 files (17 Python + 8 shell) plus ~133 doc lines across live docs, for a payoff that no longer exists. Better to spend the effort elsewhere.
Revisit if: A second project-internal directory with `tools` in its name appears AND ambiguity becomes a documented friction point.

D-58: Move verify_scenario_optimum.py into scenario_authoring package
Date: 2026-06-21 | Status: Closed (commit 8be36c8)
Priority: Routine
Decision: `verify_scenario_optimum.py` (247 lines: 7 pure library functions + CLI main) moved from `tests/self_play/` to `src/scenario_authoring/`. Filename unchanged; namespace shifts from `tests.self_play.verify_scenario_optimum` to `scenario_authoring.verify_scenario_optimum`.
Rationale: D-52 documented the prior decision to keep this in tests/, expecting a third consumer would justify extraction. The implicit trigger fired during Phase 3 — the scale probe needed direct Python import of the production code, but the `tests.self_play.*` namespace required a project-root sys.path hack to resolve. Moving the file removed the coupling, eliminated the hack, and the CLI now reads naturally as `python -m scenario_authoring.verify_scenario_optimum`.
Revisit if: Some unforeseen consumer in `tests/self_play/` would benefit from a closer co-location, but unlikely given the file's pure-library shape.

D-59: Phase 42 C5b — builder determinism over neighborhood broadening
Date: 2026-06-21 | Status: Closed (commit 8a384c3)
Priority: Important
Decision: The Phase 42 C5b plan was to fix the 4×4×4 / I-axis convergence cliff by broadening the SA move neighborhood (multi-cell flips + issue-scoped / outcome-rank swaps). That hypothesis was REFUTED by clean data. The shipped change is instead a determinism fix: `_seed_scoring_table` now consumes RNG in fixed `spec.factions` order rather than `PYTHONHASHSEED`-dependent set/dict iteration order. The broadening prototype was reverted; the single-cell neighborhood is kept.
Rationale: While prototyping broadening, the scale probe returned different results for the same seed across processes — `_seed_scoring_table` iterated a `set` of faction-name strings whose order Python randomizes per process. The probe (the phase's regression gate) was measuring noise. Once the builder was made deterministic, plain single-cell search already meets the PROJECT.md "4+ factions / 4+ issues" criterion (4×4×4 ≈2/3 acceptance), and every broadening configuration converged *worse* at high D (single-cell 4/6 vs multi-cell 2/6 vs full broadening 1/6 at seeds=6). The real I-axis blocker was spec-semantic (D-59 companion: C5a relative `batna_clearing_count_target`), not search-neighborhood width. Locked by `TestBuilderDeterminism` (cross-process digest) and `test_builds_4x4x4_in_budget`.
Revisit if: A future spec class genuinely stalls single-cell SA at a scale we care about (e.g. 5×5×5+ becomes in-scope); the reverted broadening moves are recoverable from git history (commit 8a384c3's parent) as a starting point, but re-validate against the now-deterministic probe.

D-60: Phase 46 - round-context leaf lives inside scenario_authoring
Date: 2026-06-25 | Status: Closed (Phase 46 complete) | Priority: Important
Decision: To sever the lone `scenario_compiler.py -> modules.persona` coupling (the only load-time import in the package that reaches the pipeline), extract CoachingContext + _ROUND_CONTEXT_MARKER + the 6 private formatting helpers + render_round_context_section (~150 LOC, stdlib-only) out of src/modules/persona/__init__.py into a new leaf module INSIDE the package: src/scenario_authoring/round_context.py. modules/persona/__init__.py then re-imports (re-exports) CoachingContext and render_round_context_section from the new leaf so FileBasedPersona, the package __all__, and existing consumers (orchestrator.py, tests/test_persona.py, tests/self_play/verify_scenario_pressure.py) keep working unchanged.
Rationale: The Phase 46 goal is for scenario_authoring to be liftable as a self-contained unit. The dependency direction pipeline -> authoring is correct and already exists (run_simulation / coached_game import scenario_compiler), so the live persona path (modules.persona) importing FROM the package is acceptable; the reverse (package importing pipeline) is what blocks standalone load and must go. The package already owns persona generation (PERSONA_TEMPLATE + generate_persona), so the round-context renderer is a coherent fit. A neutral top-level src/round_context.py was considered but rejected: it would leave the package depending on an out-of-package sibling, defeating the liftable-unit goal. No drift (one definition, re-exported) is preserved via the back-compat re-export.
Revisit if: scenario_authoring is actually extracted to its own repo and we want the live bot persona rendering to NOT depend on the authoring package - at that point round_context.py would move to a shared leaf both depend on.

D-61: Phase 47 - coalition Path B autonomous slice = lock the scoring contract
Date: 2026-06-25 | Status: Closed | Priority: Important
Decision: The autonomous (loopable Build) slice of the coalition track is to comprehensively unit-test and HARDEN the EXISTING coalition-exclusion scoring contract in tests/self_play/game_environment.py (_resolve_deal_scores + _find_coalition_value) exactly as currently specified - NOT to change its semantics. Locked contract: (1) a partial coalition (coalition_members a strict subset of factions) with a matching coalition_values entry gives members their stated values and assigns BATNA to excluded factions; (2) a partial coalition with no matching entry is recorded as no-deal (deal_reached=False, no_deal_reason, all-BATNA); (3) the grand coalition (members == all factions) intentionally uses the FULL-AGREEMENT scoring path (faction_score on agreed_outcomes), NOT coalition_values; (4) the below-BATNA and deal_reached-without-agreed_outcomes normalizations stand.
Rationale: Reading the scaffold shows the partial-coalition scoring path is already implemented; the genuinely remaining coalition work is decision-heavy and/or supervised - (a) the representation rationalization (three_party_coalition_v1 encodes coalitions BOTH as a synthetic coalition_formation issue AND as coalition_values, which yield DIFFERENT payoffs e.g. a+b = 9/10/1 via the issue vs 6/7/0 via coalition_values), (b) builder emission of coalition_values (needs a characteristic-function generation design), (c) live mixed-model end-to-end validation (paid run, RUN_PROTOCOL). Locking the contract with tests first de-risks all three and is the benchmark-v2 foundation, with zero open decisions for the loop.
Out of scope (separate supervised phases): representation rationalization of the synthetic coalition_formation issue; builder requires_coalition_values emission; runtime partial-coalition detection in RoundSteppedFlow; live mixed-model validation on three_party_coalition_v1.
Revisit if: the test-hardening surfaces a semantic the operator wants changed (e.g. grand coalition should read coalition_values) - that becomes a supervised decision, not an autonomous edit.

D-62: Phase 48 - narrative re-skin = value-isomorphism under relabel
Date: 2026-06-25 | Status: Closed (Phase 48 complete) | Priority: Important
Decision: The narrative-integration re-skin (generalized fill_narrative, Phase 45 Build shell) produces a NEW analysis by applying an LLM-proposed consistent bijection (relabel_map) over faction/issue/outcome identifiers PLUS themed prose (logrolling, deception_tactics, optional persona prose, narrative .md). The deterministic shell APPLIES the relabel and ASSERTS value-isomorphism to the source: identical faction/issue/outcome counts, every score equals the source score under the relabel, BATNAs map by faction relabel, and coalition_values member ids relabel with values unchanged. The guard REJECTS any numeric drift, a non-bijective/incomplete map, or a missing label. "Structure preservation" therefore means value-isomorphism under relabel, NOT byte-identity (keys rename). The LLM emits ONLY relabel_map + prose via one schema-validated structured_call; all numeric structure comes from the source untouched. The catalogue "parser" is a deterministic heading-scoped section extractor over the prose catalogue (Multi-Party Negotiation Scenarios.md), feeding --domain-context.
Rationale: The roadmap's "scoring tables / BATNAs unaltered" goal plus "themed names" can only be reconciled as a relabel that preserves values - byte-identity is impossible once identifiers change. Putting the numeric guarantee in a deterministic, test-backed guard (not in the LLM) makes the shell pure Build/loopable; only the prompt QUALITY (themed-name aptness, prose faithfulness) is Refine and is tuned supervised in a later phase via tests/prompt_regression/.
Out of scope (supervised follow-on phase): LLM re-skin PROMPT quality tuning (Refine, via prompt_regression). The loop authors an initial prompt and stops at the shell+tests boundary.
Revisit if: a consumer needs the themed names to live as a display overlay (generic keys retained in the JSON) rather than a hard relabel of the analysis identifiers.

D-63: Scenario-viz narrative layout - balanced columns, paragraph-atomic
Date: 2026-06-25 | Status: Closed | Priority: Routine
Decision: The deal-explorer narrative (scenario_viz.build_scenario_html) renders as a SINGLE flowing block in a CSS balanced multi-column container (.scenflow; columns:2; column-fill:balance), with reflow breaking at PARAGRAPH boundaries - .scenflow p, bullets, and issue-lists carry break-inside:avoid; headings carry break-after:avoid. It must NOT use a fixed left/right grid that assigns whole sections to fixed columns.
Rationale: The previous .scen2/.scencol grid placed the intro + most sections + issues + game in the left column and ONLY the parties section in the right, leaving a large empty right column whenever the parties section was short. The operator hit this repeatedly across sessions and the preference did not persist (session memory does not carry over). A balanced multi-column flow fills both columns regardless of section sizes; paragraph-atomic breaking keeps a paragraph from being sliced across the column gap. Locked by tests/test_scenario_viz.py::test_narrative_layout_is_balanced so an autonomous worker (or future session) that regresses it fails the suite.

D-64: Phase 49 - per-run cost metadata schema = Option A scalar total
Date: 2026-06-27 | Status: Closed (Phase 49 complete) | Priority: Important
Decision: Per-run self-play results carry a top-level `metadata` block: `{"cost_usd": <float>, "cost_source": "metered" | "estimated_from_log" | "dry_run", "n_llm_calls": <int>}`. Live runs populate `cost_usd` from `accountant.session_total` at write time (metered); dry-run / fake path writes `cost_source: "dry_run"`; historical backfill re-estimates from `llm_call_log` token counts (estimated_from_log). Per-model/per-operation breakdown (`report(since=...)`) and per-faction attribution are explicitly OUT of scope (Option B deferred). Schema is forward-compatible: future extensions add keys under `metadata`.
Rationale: Paper 1 needs $/closed-deal and per-cell cost-coverage metrics — a scalar total is sufficient. The per-model breakdown would require resolving every `config_provider`+`tier` to a priced model per historical run (complex, fragile) for no paper-relevant gain. `session_total` at write time is safe because `run_simulation._run()` runs exactly one `env.run_game()` per process — the ledger total equals that run's spend with no windowing. `cost_source` discriminates precision: "metered" is exact, "estimated_from_log" is approximate (accuracy bounded by toolkit/cost_accountant pricing table), "dry_run" carries zero meaning. Option A is loop-safe: no API calls, fully fake/dry-run testable.
Revisit if: per-faction cost attribution becomes a Paper 1 or Paper 2 need (extend `metadata.by_faction`), or if a multi-game process is ever batched (would need per-game `session_total` reset before `_write_results`).
