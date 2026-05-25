# Diplomat

## Spark
> An AI faction agent for a multiplayer diplomacy game — autonomous negotiation, promise tracking, and strategic analysis, coached by a human operator through a review gate.

## What This Is
A modular AI agent that plays a faction in the AI Life Diplomacy game. Receives game messages via Telegram, extracts structured state (factions, promises, coalitions, inconsistencies), runs dual-provider strategic analysis, generates diplomatic responses shaped by a faction persona, and submits them through a human review gate before posting. The human operator coaches the agent with sparse, high-signal input rather than playing the game directly. Runs on a Raspberry Pi as a long-running Python service.

## Audience
The human operator coaching the faction. The system handles the cognitive load of tracking promises, detecting inconsistencies, modeling coalitions, and drafting responses. The operator focuses on what only a human can see: the behavior of coaches behind opposing agents, judgment calls outside the prompt's scope, and systematic biases in the heuristics.

## Scope

### Core
- Transport layer for Telegram I/O (send/receive via toolkit/telegram_client)
- Append-only event store for raw game messages
- Structured state manager with schema-validated patches and audit log
- LLM-based extraction: text → structured state patches (via toolkit/llm_client)
- Dual-provider strategic analysis with divergence detection
- Faction persona configuration with hot-reload
- Context assembly: persona + intelligence + coaching + transcript → decision context
- LLM-based response generation (via toolkit/llm_client)
- Adversarial self-read of draft responses before posting
- Human review gate with approve/edit/block workflow
- Coaching system with tagged input routing (PRIORITY, CONSTRAINT, INTEL, TONE, WATCH)
- Cost governance via toolkit/cost_accountant
- Pipeline configuration via single YAML file

### Flexible
- [in] TelethonUserTransport for user-account mode (if bot-to-bot blocked)
- [in] Provider rotation via toolkit/llm_client.complete_with_rotation()
- [deferred] Slack or Discord transport
- [deferred] Multi-game support (multiple faction_prompt.txt files, per-game state)
- [deferred] Post-game analytics dashboard

### Exclusions
- Not a general-purpose chatbot or assistant
- No local inference — all LLM calls are API-based
- No autonomous posting without review gate (at least for the first game)
- No real-time voice or video interaction
- No multi-agent coordination (single faction agent only)

## Constraints
- **Hardware:** Raspberry Pi 4 (4GB min) or Pi 5 (8GB recommended), Ethernet, SSD preferred
- **OS:** Raspberry Pi OS Lite 64-bit
- **Language:** Python (async)
- **Persistence:** SQLite with WAL mode, single file
- **LLM inference:** API-based via toolkit/llm_client (Anthropic Claude, OpenAI GPT-4o)
- **Telegram:** Bot API via toolkit/telegram_client (or Telethon for user accounts)
- **Cost governance:** toolkit/cost_accountant with per-round and per-session budgets
- **Shared dependencies:** toolkit project (llm_client, telegram_client, cost_accountant)
- **No monorepo tooling:** Each module has typed interfaces, wired by the Orchestrator

## Prior Art
- **Phosphene** (sibling project) — autonomous personality-driven agent on Pi. Shares toolkit dependencies, similar module architecture (Gateway ↔ Transport, Generator ↔ Generation). Different domain: content generation vs. strategic negotiation.
- **Codexbot** (sibling project) — Telegram bot wrapping Codex. Shares toolkit/telegram_client, similar State Store pattern. Different domain: development workflow vs. game play.
- **Generative Agents (Park et al.)** — memory stream + reflection for believable agents. Relevant: structured memory and reflection. Limited: no adversarial environment, no coaching.
- **AI Diplomacy (Meta CICERO)** — state-of-the-art AI for Diplomacy board game. Different scale (full board game AI with planning), but same domain of strategic communication and trust modeling.

## Success Criteria
- The system receives game messages and extracts structured state updates within seconds
- Dual-analyst reports surface meaningful divergences that inform decision-making
- Generated responses are strategically coherent and consistent with the faction persona
- The adversarial reader catches exploitable commitments before they are posted
- The review gate enables the operator to approve, edit, or block with minimal friction
- Coaching input decreases over rounds as the faction prompt improves from edit log feedback
- The promise ledger and inconsistency tracker accurately reflect the game state
- The system runs unattended for the duration of a game (hours to days) without manual restart
- Cost stays within the configured per-round and per-session budgets

## MVP Definition

MVP is the configuration that closes the core loop: messages arrive → state updates → analysis runs → response generated → adversarial check → human review → message posted. The operator can coach between rounds and refine the faction prompt based on the edit log.

### Required Modules

| Module | MVP Scope |
|--------|-----------|
| Transport | TelegramBotTransport (via toolkit/telegram_client) |
| Event Store | SQLiteEventStore — append-only message log |
| State Manager | SQLiteStateManager — domain tables, schema validation, audit log |
| Extraction | LLM-based structured extraction (via toolkit/llm_client) |
| Analyst | Single-provider analysis (primary only, secondary deferred) |
| Persona | FileBasedPersona with hot-reload |
| Context Assembler | DefaultContextAssembler |
| Generation | LLM-based generation (via toolkit/llm_client) |
| Review Gate | TelegramReviewGate — approve/edit/block |
| Coaching | TaggedCoachingParser with routing |
| Orchestrator | Full event loop, round management, cost accountant wiring |

### Deferred for MVP
- **Adversarial Reader** — valuable but not blocking; operator catches issues via review gate
- **Secondary Analyst** — dual-provider divergence adds quality but primary alone is functional
- **Provider rotation** — single provider per role is sufficient for a first game
- **TelethonUserTransport** — only needed if bot-to-bot is blocked

## Risks and Open Questions
- [must-resolve] **Bot vs. user accounts** — determines Transport implementation; resolve with game moderator before build
- [must-resolve] **Round structure** — time-based or signal-based; sets pipeline.yaml config
- [implementation] **Structured output enforcement** — toolkit/llm_client returns plain text; Extraction needs JSON schema enforcement. Handle in the module or extend toolkit.
- [implementation] **Debounce strategy** — time-window batching vs. per-message cooldown for extraction
- [implementation] **Review gate timeout** — what happens if the operator doesn't respond before round boundary
- [watch] **Response rate** — if posts are capped per round, affects Orchestrator response trigger logic
- [watch] **Total round count** — unknown at start; affects spend schedule in Analyst output
- [watch] **Win condition mechanics** — may require late-game prompt updates

## Extension Points
- Additional Transport implementations (Slack, Discord, CLI already spec'd)
- Additional LLM providers via toolkit/llm_client (Google, OpenRouter already supported)
- Different game domains: replace config/ directory for customer service, contract negotiation, etc.
- Post-game replay and analysis from the append-only event store + state_change_log
- Multi-faction support: run multiple instances with different faction_prompt.txt files

## Size Estimate
Multi-module. 12 modules with defined interfaces, single Orchestrator wiring layer. Similar scope to Phosphene (10+ modules), though individual modules are simpler (no memory tiers, no distillation).

---

## Change History
| Date | What Changed | Why |
|------|-------------|-----|
| 2026-05-24 | Initial PROJECT.md created from diplomat-system-spec.md v0.5 | Project setup |
