# Claude Worker Adapter — Diplomat

> **Contract:** Backend-specific mechanics for Claude workers. The universal loop
> contract (identity, main loop, escalation, output contract, prohibitions) lives
> in `WORKER_SPEC.md` and arrives in your prompt pre-assembled — you do not read
> it. Action procedures live in `instructions/$ACTION.md` and also arrive
> pre-assembled. This adapter covers what is Claude-specific plus project-specific.

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

## Claude-Specific Tool Rules

- **Edit tool requires fresh reads.** Before editing any source or test file,
  read it immediately before the edit — not at the start of the iteration.
  Governance state arrived fresh in your prompt; this applies to source files.
- **No subagent spawning for routine work.** Do NOT spawn `Agent(Explore)` for
  simple file discovery — use `bash find` / `bash ls`. Subagents are for
  genuinely open-ended research.
- **Non-interactive shell only.** The loop has no stdin. Commands that open
  editors (`git commit` without `-m`, `git rebase -i`, `vim`), prompt for input
  (`read`, `sudo` without `-n`), or page (`git log` without `--no-pager`,
  `less`) will hang. Use discrete edits or `git restore`; `git add -p` is
  interactive-only.
- **State writes go through `i2c state`.** Never `sed` / `echo >` / direct edits
  on `.state/` files — the CLI guarantees atomic, schema-validated writes.
- **Use `i2c state --from-file` for multi-line or `$`-laden payloads.** Write
  the JSON to a temp file and pass `--from-file <path>`.

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
