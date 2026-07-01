# Codex Worker Adapter — Diplomat

> **Contract:** Backend-specific mechanics for Codex workers. The universal loop
> contract (identity, main loop, escalation, output contract, prohibitions) lives
> in `WORKER_SPEC.md` and arrives in your prompt pre-assembled — you do not read
> it. Action procedures live in `instructions/$ACTION.md` and also arrive
> pre-assembled. This adapter covers what is Codex-specific plus project-specific.

## Framework
i2c.

## Available Modules

**Storage (leaf):**
- `event_store`: append-only raw event log (SQLite)
- `state_manager`: structured domain state with schema-validated patches (SQLite)

**Processing:**
- `extraction`: text → structured state patch via toolkit/llm_client
- `coaching`: parse and route operator input by tag
- `persona`: faction identity configuration with hot-reload

**Intelligence:**
- `analyst` + `divergence`: dual-provider strategic analysis with divergence detection

**Response pipeline:**
- `context_assembler`: assemble all inputs into Decision Engine context
- `generation`: context → response text via toolkit/llm_client
- `adversarial`: draft → adversarial analysis via toolkit/llm_client (optional)

**Platform:**
- `transport`: platform I/O via toolkit/telegram_client
- `review_gate`: human approval workflow via toolkit/telegram_client

**Composition:**
- `pipeline`: per-agent capability surface (start/shutdown, store_event, extract_from, run_response, advance_to_round)
- `flow`: scheduling strategy — `EventDrivenFlow` (production), `RoundSteppedFlow` (self-play)
- `orchestrator`: compat factory returning `EventDrivenFlow` (see `ARCH_flow.md`)

## Project-Specific Notes
- **Language:** Python 3, async throughout (asyncio).
- **Persistence:** SQLite (WAL mode), single file at `data/game.db`.
- **External dependencies:** `toolkit/` (sibling project) — `llm_client`,
  `telegram_client`, `cost_accountant`. No direct provider SDK imports.
- **Test strategy:** pytest, one test file per module; fakes for toolkit deps.
  The suite is hermetic (runs offline).
- **Key constraint:** `toolkit/llm_client` returns plain text — Extraction must
  enforce JSON schema locally (prompt + parse + validate).
- **Config-driven:** all domain logic in `config/` (prompts, schemas, routing,
  `pipeline.yaml`).
- **Doc-sync discipline:** each Build phase's step list must include a "doc
  update" step naming which reference docs it touched (or "none") before phase
  review — `CLI_REFERENCE.md`, `ASSESSMENT.md`, `ARCHITECTURE.md`,
  `ARCH_<module>.md`, `diplomat-testing-doc.md`, `TUNING.md`, `SMOKE_RUNBOOK.md`,
  `RUN_PROTOCOL.md`, `TUNING_LOG.md`, `DECISIONS.md`.

## Codex-Specific Tool Rules

- **No `@`-reference loading.** Read files explicitly with shell commands; treat
  any `@FILENAME` markers in prose as paths to `cat` / `sed -n`.
- **Minimize tool calls.** Combine reads/greps into single shell invocations
  (`cat A && echo --- && cat B`; `grep -n foo A B`).
- **Search-tool fallback.** Check `command -v rg` before using `rg`; if absent,
  use `find` / `grep -RIn` / `sed -n`. Do not retry `rg` after it fails.
- **Fresh reads before edits.** Re-read any source/test file immediately before
  editing it. Governance arrived fresh in your prompt; this applies to source.
- **Non-interactive shell only.** No editors (`git commit` without `-m`,
  `git rebase -i`), input prompts (`read`, `sudo` without `-n`), or pagers
  (`git log` without `--no-pager`, `less`). `git add -p` is interactive-only.
- **State writes go through `i2c state`.** Never `sed` / `echo >` / direct edits
  on `.state/` files.
- **Use `i2c state --from-file` for multi-line or `$`-laden payloads.**

## Turn Health Check (Codex-specific safety)

A circuit breaker, separate from the step budget. When the runner provides
`ITERATION_JSONL`, after each completed action check:

```bash
grep -c '"item.completed"' "$ITERATION_JSONL"
```

If `total_turns > actions_performed * 50`, emit `EXIT 2` with reason
`"turn health check exceeded"`. Cross-repo steps (editing both diplomat and
`toolkit/`) legitimately need more calls — if you trip the ceiling there, log
the cause in the devlog `summary`.

## Output Contract

End every invocation with exactly these two lines — no text after:

```
EXIT: 0 | 2
REASON: <one-line summary>
```

| Code | Meaning |
|------|---------|
| 0 | Normal completion — runner reads `.state/project.json` for next dispatch |
| 2 | Error — judgment-based escalation or health check tripped |

Do not omit it — prose-only output makes the runner report
`exit=2 "signal missing or malformed"` even when the work landed in `.state/`
and the commit.

## Mode

Mode (autonomous vs. supervised) is set by the runner via the assembler's
`--mode` flag; the assembled prompt's framing reflects it. Autonomous (default):
apply, commit, transition, emit the signal. Supervised: surface changes before
committing. You do not choose the mode.
