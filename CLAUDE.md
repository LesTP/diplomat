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
| Pipeline + Flow | `ARCH_flow.md` |

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

## Reference Docs to Keep in Sync

These docs are not loaded by default but **MUST** be updated when their listed triggers fire. Each Build phase's step list should include an explicit "doc update" step before phase-review that names which of these the phase touched (or "none" if no doc impact). Doc updates are part of every phase's definition-of-done — not optional follow-up.

| Doc | Update trigger |
|---|---|
| `CLI_REFERENCE.md` | Any new/changed/removed CLI flag, env var, or invocation pattern |
| `ASSESSMENT.md` | Scoring lens status changes (§3.x ✓ / partial / NOT YET); Block A/B/C tech-debt list changes; new workstream items; new scoring or skill insights |
| `ARCHITECTURE.md` | Component additions/removals; coupling note changes; key decisions added |
| `ARCH_<module>.md` | Any change to that module's public interface, internals worth documenting, or data shapes |
| `diplomat-testing-doc.md` | New test layers/tools; test infrastructure changes; deployment doc changes |
| `TUNING.md` | BATNA semantics, provider defaults, prompt-tuning practice changes |
| `SMOKE_RUNBOOK.md` | Bot lifecycle or smoke-checklist change |
| `RUN_PROTOCOL.md` | Self-play pre-flight or live-run procedure change |
| `TUNING_LOG.md` | Each live run produces an entry (run number, scenario, providers, cost, observations, decisions) |
| `DECISIONS.md` | New architectural decision or status change to an existing one |

Phase step examples: Phase 24 (Build) lists a "doc update" step that names `CLI_REFERENCE.md` (3 new flags), `TUNING.md` (asymmetric BATNA fractions + force-clamp semantics), `diplomat-testing-doc.md` (Layer 2 extraction examples location moved). Phase 22 lists `ARCHITECTURE.md` (Pipeline + Flow rows added), `ARCH_orchestrator.md` (compat shim), `ARCH_flow.md` (new, created in 22.7), `ASSESSMENT.md` (Pipeline/Flow tech-debt → ✓).

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
- Pipeline: Per-agent capability surface (start/shutdown, store_event, extract_from, run_response, advance_to_round, etc.)
- Flow: Scheduling strategy — `EventDrivenFlow` (production Telegram/CLI), `RoundSteppedFlow` (self-play)
- Orchestrator: Compat factory returning `EventDrivenFlow`; see `ARCH_orchestrator.md` → `ARCH_flow.md`

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
- **Never self-judge budget.** Do NOT decide "STEP_BUDGET of N is exhausted (used M actions)" based on your own count. Call `state_machine.sh` after every completed action and do exactly what it returns. The script decrements deterministically and decides EXIT/EXECUTE/REVIEW — your arithmetic may be off (iter 54 lost 2 actions to a wrong `5 - 3 = exhausted`). See `WORKER_SPEC.md` §3 "Loop discipline."

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
