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
