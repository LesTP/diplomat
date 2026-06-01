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
