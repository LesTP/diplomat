# Codex Worker Adapter — Diplomat

> **Contract:** Follow `WORKER_SPEC.md` for iteration lifecycle, allowed actions,
> step budget, escalation conditions, and output contract. This file covers
> Codex-specific mechanics only.

## Framework
This project follows the From Idea to Code governance framework.

## Required Reading — Every Iteration

You do not have `@`-reference loading. You must explicitly read these files at
the start of every iteration before taking any action.

**CRITICAL: Minimize tool calls.** Each tool call round-trips through the full
context window. Combine reads into as few shell commands as possible.

### Tier 1 — Always (mandatory, every iteration)

Read this file, WORKER_SPEC.md, and DEVPLAN.md in a **single command**:

```bash
cat CODEX.md && echo '---SPLIT---' && cat WORKER_SPEC.md && echo '---SPLIT---' && cat DEVPLAN.md
```

**DEVLOG.md convention:** Append new entries at the bottom (newest last).
During phase close, archive the previous phase's entries to `DEVLOG_archive.md`.

### Tier 2 — Current module (mandatory for step/review/complete actions)

After determining the active module from DEVPLAN's Current Status, read the
relevant ARCH file. Combine with source files in the **same command**:

```bash
cat ARCH_module.md && echo '---SPLIT---' && cat src/modules/module/impl.py
```

### Tier 3 — On demand (read only when needed)
- `PROJECT.md` — only during Phase Plan actions
- `ARCHITECTURE.md` — only during Phase Plan or cross-module wiring
- `GOVERNANCE.md` — only if unsure about process

### Read efficiency rules
- **Combine related reads** into one `cat A && echo '---' && cat B` command
- **Never read one file per tool call** when you need multiple files
- **Combine source + test reads**: `cat src/foo.py && echo '---' && cat tests/test_foo.py`
- **Fresh reads before edits** — re-read immediately before editing, not at iteration start

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

When updating a doc, **read it fresh first** (it may have changed since the last iteration) and combine the read with the edit in one tool round-trip where possible.

## Load for Current Module

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
- **Key constraint:** toolkit/llm_client returns plain text — Extraction must handle JSON schema enforcement locally
- **Config-driven:** All domain logic in config/ directory

## Codex-Specific Tool Rules
- **No `@` references.** Read files explicitly using CLI.
  When a file contains `@FILENAME` references, treat them as file paths to read.
- **Minimize tool calls.** Every tool call re-processes the full context. Combine
  multiple file reads, greps, and short commands into single shell invocations.
- **Command files shared with Claude.** Action procedures live in
  `.claude/commands/*.md`. Read these files and follow their instructions the
  same way Claude does — the content is backend-agnostic.
- **Fresh reads before edits.** Before editing any file (especially DEVPLAN.md),
  read it immediately before the edit — not at the start of the iteration.
- **Shell usage.** Use CLI tools directly for builds, tests, git operations,
  file discovery, and search.
- **Search tool availability.** This loop environment may not have `rg`
  installed. Before using `rg`, check availability with `command -v rg`. If it
  is absent, use portable fallbacks instead: `find` for file discovery,
  `grep -RIn` for text search, and `sed -n` for bounded file reads.

## Action Instructions

Follow the main loop from WORKER_SPEC.md §3:

```
LOOP:
  1. output=$(bash tools/state_machine.sh)
  2. ACTION = parse "ACTION:" from output
     NEXT   = parse "NEXT:" from output
  3. if ACTION == "EXIT" → emit exit signal, stop
  4. perform the action (see below)
  5. if error → emit exit signal with EXIT 2, stop
  6. commit, update DEVLOG/DEVPLAN
  7. sed -i "s/^state:.*/state: $NEXT/" DEVPLAN.md
  8. goto LOOP
```

### PLAN
Read `.claude/commands/phase-plan.md` and follow its instructions.

### EXECUTE
Pick the next unchecked step from DEVPLAN. Do the work, run tests.
Read `.claude/commands/step-done.md` and follow its instructions.

### REVIEW
Read `.claude/commands/phase-review.md` and follow its instructions.

### CLOSE
Read `.claude/commands/phase-complete.md` and follow its instructions.

## Output Contract

End every invocation with exactly these five lines — no additional text after:

```
EXIT: 0 | 1 | 2
REASON: <one-line summary>
ACTION_TYPE: PLAN | EXECUTE | REVIEW | CLOSE
ACTION_ID: <phase.step>
STEPS_COMPLETED: <number of actions performed in this invocation>
```

## Autonomy

When invoked in autonomous mode, execute the action and emit the exit signal
without waiting for human input. In supervised mode, surface proposed changes
for approval before committing.

See WORKER_SPEC.md §7 for full mode definitions.
