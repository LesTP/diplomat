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
- **Megareads can fragment context.** Single `cat`/`sed` commands producing >40k chars of output sometimes trigger an internal "let me reorient" moment where the temptation is to re-call `state_machine.sh`. **Don't dispatch — peek.** Use `bash tools/state_machine.sh --peek` to re-validate state mid-action without burning budget. Reserve the bare `bash tools/state_machine.sh` (dispatch) for the top of each LOOP iteration, paired with the action it returns. See `WORKER_SPEC.md` §3 "Loop discipline" — iter 53 lost its final step before `--peek` existed; iter 102 burned a full 6-step budget on defensive dispatches and is the reason `--peek` was added.
- **Only call dispatch when you are about to write code or commit. Anything else is `--peek`.** This covers post-megaread reorientation AND pre-batch preflight. Anti-pattern from iter 105: chaining `bash tools/state_machine.sh && cat WORKER_SPEC.md && cat DEVPLAN.md && cat .claude/commands/*.md` to "ping the controller before loading docs" — the dispatch decrements budget but the work that follows is just context loading, not the kind of action state_machine handed off. **Same bug recurred at iter 138 and 139** with the variant `bash tools/state_machine.sh && cat CODEX.md` then `bash tools/state_machine.sh && cat WORKER_SPEC.md && cat DEVPLAN.md` — both iterations exited with `STEPS_COMPLETED: 0`. **See "⚠️ ONE DISPATCH PER ITERATION" section below for the explicit anti-pattern + correct pattern.** Load the docs first, then dispatch right before you write code.
- **Scope recursive greps narrowly — never include `.` at the repo root.** The repo contains very large files that will blow the context window if matched: `DEVLOG_archive.md` (~194KB), `TUNING_LOG.md` (~107KB), `diplomat-testing-doc.md` (~67KB), `NEXT_STEPS.md` (~62KB), `DEVLOG.md` (~46KB), plus multi-MB self-play result JSONs in `tests/self_play/results/` (some >3MB) and multi-MB iteration logs in `logs/loop/`. A single `grep -RIn 'foo' .` can stream 30+MB into the codex process and trigger a SIGKILL (OOM / response-size limit) — this killed iter 103 mid-action.
  - **Default:** `grep -RIn 'foo' src tests` (source + tests only).
  - **Need ARCH docs:** `grep -n 'foo' ARCH_*.md` (glob, not recursive).
  - **Need DEVPLAN/PROJECT:** name them explicitly.
  - **Always pipe broad results through `head -n 100` or `wc -l`** before reading the full match list.
  - **Never** include any of: `DEVLOG*.md`, `TUNING_LOG*.md`, `NEXT_STEPS.md`, `tests/self_play/results/`, `logs/`. If you need to search history, read the specific file directly with `grep -n` (no `-R`) and a bounded line range.

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
| Pipeline + Flow | `ARCH_flow.md` |

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
- **Non-interactive shell only.** No interactive editors, pagers, or git
  prompts. `git add -p`, `git commit` without `-m`, `git rebase -i`, and any
  `$EDITOR`-opening command will hang the loop (iter 80 lost ~35 min this way).
  See `WORKER_SPEC.md` §3 "Shell command discipline (non-interactive only)"
  for the full list and recommended alternatives.

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

### ⚠️ ONE DISPATCH PER ITERATION

**Step 1 of LOOP is the ONLY time you may call `bash tools/state_machine.sh` (dispatch) in an iteration.** Every subsequent state-machine call in the same iteration MUST use `--peek`. The state machine decrements the step budget on every dispatch — a second dispatch burns the budget that was reserved for your actual work, and the iteration exits with `STEPS_COMPLETED: 0`.

This bug has now wasted iters **102, 105, 138, 139**. Read the patterns below before composing your first shell command:

**WRONG (iter 138, 139, 105, 102):** chaining dispatch with a context load —

```bash
# At iteration top:
$ bash tools/state_machine.sh                                          # 1st dispatch: ACTION=EXECUTE

# Then in the SAME iteration:
$ bash tools/state_machine.sh && cat CODEX.md                          # 2nd dispatch: budget exhausted → ACTION=EXIT
# OR:
$ bash tools/state_machine.sh && cat WORKER_SPEC.md && cat DEVPLAN.md  # also 2nd dispatch — same outcome
# Result: STEPS_COMPLETED: 0, no commit, iteration wasted.
```

The ampersand-chain pattern is the trap. Even though it *feels* like "check state, then load context," the shell runs `bash tools/state_machine.sh` FIRST and that single call drains the budget. The subsequent `cat` happens but its output is irrelevant — the iteration is already over.

**RIGHT:** load context first, dispatch when about to act, peek for re-orientation —

```bash
# Step 1 (LOOP) — dispatch ONCE, capture the action:
$ bash tools/state_machine.sh
ACTION: EXECUTE
NEXT: execute

# NOW load context (no dispatch — plain reads):
$ cat CODEX.md && echo '---SPLIT---' && cat WORKER_SPEC.md && echo '---SPLIT---' && cat DEVPLAN.md

# Re-validate state mid-work without burning budget (use --peek freely):
$ bash tools/state_machine.sh --peek

# Do the work — edit files, run tests, commit:
$ ...

# Step 7 (LOOP) — write next state:
$ sed -i "s/^state:.*/state: $NEXT/" DEVPLAN.md
```

**Rule of thumb:** Dispatch (`bash tools/state_machine.sh`) means **"I am about to write code or commit RIGHT NOW."** Anything else — reading docs, exploring source, post-megaread reorientation, preflight checks — is either no state-machine call at all, or `--peek`.

**Mechanical check before any shell command:** If your command line contains `bash tools/state_machine.sh` (without `--peek`) AND you have already called it once this iteration, **delete the dispatch** and rerun with just the rest. If the rest is just a `cat`, you don't need the state-machine call at all.

**CRITICAL — state-write command (step 7).** Copy-paste this **exactly**:

```bash
sed -i "s/^state:.*/state: execute/" DEVPLAN.md
```

Replace `execute` with the value from `NEXT:` in the state-machine output.
Use **double quotes** around the full sed expression. Do NOT use single quotes
with embedded double quotes — the pattern `'s/"'^state:...'` does not match
and silently fails. This bug has wasted multiple iterations (iters 81, 86).

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
