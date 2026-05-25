# Claude Worker Adapter — Diplomat

> **Contract:** Follow `WORKER_SPEC.md` for iteration lifecycle, allowed actions,
> step budget, escalation conditions, and output contract. This file covers
> Claude-specific mechanics only.

## Framework
This project follows the From Idea to Code governance framework.

## Required Reading — Every Iteration

### Tier 1 — Always (mandatory, every iteration)

Auto-loaded via @-references:

- @DEVPLAN.md — current status, cold start summary, gotchas
- @WORKER_SPEC.md — backend-agnostic worker contract

### Tier 2 — Current module (mandatory for EXECUTE / REVIEW / CLOSE)

After determining the active module from DEVPLAN's Current Status, read the
relevant ARCH file using the lookup table below.

| Module | ARCH file |
|--------|----------|
| Event Store | `ARCH_event_store.md` |
| State Manager | `ARCH_state_manager.md` |
| Extraction | `ARCH_extraction.md` |
| Coaching | `ARCH_coaching.md` |
| Transport | `ARCH_transport.md` |
| Persona | `ARCH_persona.md` |
| Analyst + Divergence | `ARCH_analyst.md` |
| Context Assembler | `ARCH_context_assembler.md` |
| Generation | `ARCH_generation.md` |
| Review Gate | `ARCH_review_gate.md` |
| Adversarial | `ARCH_adversarial.md` |
| Orchestrator | `ARCH_orchestrator.md` |

### Tier 3 — On demand (read only when needed)

Do NOT load these unconditionally. Read only when the action requires them:

- `PROJECT.md` — only during Phase Plan (scope, constraints, success criteria)
- `ARCHITECTURE.md` — only during Phase Plan, or when reasoning about cross-module wiring
- `GOVERNANCE.md` — only if uncertain about process (regimes, modes, escalation rules)

### Tier 4 — Reference only (load explicitly when relevant)

- `DECISIONS.md` — read during Phase Review to verify no contract drift since prior decisions; otherwise on demand
- `DEVLOG.md` / `DEVLOG_archive.md` — read during Phase Complete (DEVLOG learning review per GOVERNANCE.md)
- `diplomat-system-spec.md` — detailed system specification; reference for schema details, prompt templates, deployment config

**DEVLOG.md convention:** Append new entries at the bottom (newest last).
During phase close, archive the previous phase's entries to `DEVLOG_archive.md`.

This file (CLAUDE.md) provides Available Modules and Project-Specific Notes
inline so non-plan iters don't need to load PROJECT or ARCHITECTURE for
high-level orientation.

## Available Modules

**Storage (leaf dependencies):**
- Event Store: Append-only raw event log (SQLite)
- State Manager: Structured domain state with schema-validated patches (SQLite)

**Processing:**
- Extraction: Text → structured state patch via toolkit/llm_client
- Coaching: Parse and route operator input by tag
- Persona: Faction identity configuration with hot-reload

**Intelligence:**
- Analyst + Divergence: Dual-provider strategic analysis with divergence detection

**Response pipeline:**
- Context Assembler: Assemble all inputs into Decision Engine context
- Generation: Context → response text via toolkit/llm_client
- Adversarial: Draft → adversarial analysis via toolkit/llm_client (optional)

**Platform:**
- Transport: Platform I/O via toolkit/telegram_client
- Review Gate: Human approval workflow via toolkit/telegram_client

**Composition:**
- Orchestrator: Pipeline topology, event loop, cost accountant wiring

## Project-Specific Notes
- **Language:** Python 3, async throughout (asyncio)
- **Persistence:** SQLite with WAL mode, single file at data/game.db
- **External dependencies:** toolkit project (llm_client, telegram_client, cost_accountant). No direct provider SDK imports.
- **Test strategy:** pytest, one test file per module. Fakes for toolkit dependencies.
- **Key constraint:** toolkit/llm_client returns plain text — Extraction must handle JSON schema enforcement locally (prompt + parse + validate)
- **Config-driven:** All domain logic in config/ directory (prompts, schemas, routing rules, pipeline.yaml)

## Claude-Specific Tool Rules
- **Edit tool requires fresh reads:** Before editing any file (especially DEVPLAN.md), read it immediately before the edit — not at the start of the iteration.
- **No subagent spawning for simple tasks:** Do NOT spawn Agent(Explore) subagents for simple file discovery — use `bash find` or `bash ls` instead.

## Claude-Specific Runner Info
**Runner:** `run-iteration.sh` — runs `claude -p` per iteration, logs to `logs/loop/`.

**Slash commands:** Project commands in `.claude/commands/` — these are NOT
Skill-tool skills. To use them, read the `.md` file and follow its instructions.
Do NOT call them via the Skill tool.

| Action (from WORKER_SPEC) | Claude command file |
|---------------------------|---------------------|
| Phase Plan | `.claude/commands/phase-plan.md` |
| Step Execution | `.claude/commands/step-done.md` |
| Phase Review | `.claude/commands/phase-review.md` |
| Phase Complete | `.claude/commands/phase-complete.md` |

## Autonomy
This project supports autonomous execution. When invoked with
`autonomous: true` in the prompt, commands auto-proceed and the agent follows
`WORKER_SPEC.md`. Otherwise, commands pause for human approval.

See WORKER_SPEC.md §8 for mode definitions (autonomous vs. supervised).
