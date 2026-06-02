# Diplomat

> AI faction agent for a multiplayer diplomacy game. Autonomous negotiation,
> promise tracking, and strategic analysis, coached by a human operator
> through a review gate.

For the project's scope, audience, success criteria, and constraints, read
[`PROJECT.md`](PROJECT.md). For the architectural component map and module
contracts, read [`ARCHITECTURE.md`](ARCHITECTURE.md). To pick up active
work, read [`DEVPLAN.md`](DEVPLAN.md).

---

## Quick-start

| I want to... | Go to |
|---|---|
| Understand what the project does | [`PROJECT.md`](PROJECT.md) |
| Run the production Telegram bot | [`CLI_REFERENCE.md`](CLI_REFERENCE.md) → `tools/service.sh` |
| Run a multi-agent self-play game | [`CLI_REFERENCE.md`](CLI_REFERENCE.md) → `tests.self_play.run_simulation` + [`RUN_PROTOCOL.md`](RUN_PROTOCOL.md) for the pre-flight |
| Smoke-test the Pi deployment | [`SMOKE_RUNBOOK.md`](SMOKE_RUNBOOK.md) |
| Set up a coaching-test loop on Pi | [`NEXT_STEPS.md`](NEXT_STEPS.md) §4 (pending) |
| Tune BATNAs, providers, prompts | [`TUNING.md`](TUNING.md) |
| See what experiments have run | [`TUNING_LOG.md`](TUNING_LOG.md) (active arc) + [`TUNING_LOG_archive.md`](TUNING_LOG_archive.md) (early runs) |
| Find work to do | [`NEXT_STEPS.md`](NEXT_STEPS.md) |
| Understand how skill is measured | [`ASSESSMENT.md`](ASSESSMENT.md) |

---

## Documentation Inventory

Active docs (excluding governance — see bottom). Sorted by area of work.

### Experimental design — the *why*

| Doc | What it is | Status |
|---|---|---|
| [`ASSESSMENT.md`](ASSESSMENT.md) | Conceptual framework: the calculation-vs-negotiation tension, skill dimensions, four scoring lenses, and the A/B/C/X workstream tags used throughout NEXT_STEPS. The "why we measure what we measure" doc. | CURRENT — canonical |

### Planning — the *what next*

| Doc | What it is | Status |
|---|---|---|
| [`NEXT_STEPS.md`](NEXT_STEPS.md) | Forward backlog with A/B/C/X workstream tags and 🔨/🔀/👁 loop-readiness classification. Includes pressure-mechanism ideas, conversation-model upgrades, coached test loop, Clankmates, pricing audit, per-role model strategy, reverse scenario builder, voice templates. Run 10 findings folded in 2026-06-01. | CURRENT — canonical |

### Operations — the *how to run it*

| Doc | What it is | Status |
|---|---|---|
| [`CLI_REFERENCE.md`](CLI_REFERENCE.md) | Single-page index of every CLI entry point (production, self-play, tools, inspection) with flags, defaults, working examples, common workflows. Includes ad-hoc SQL inspection queries (migrated from the retired spec). | CURRENT — canonical |
| [`RUN_PROTOCOL.md`](RUN_PROTOCOL.md) | Canonical pre-flight sequence for live multi-agent self-play (define inputs → verify scenario → probe providers → dry-run → live → verify → document). Born from Run 8's silent-failure loss. | CURRENT — canonical |
| [`SMOKE_RUNBOOK.md`](SMOKE_RUNBOOK.md) | Telegram coaching/review smoke playbook for Pi deployment. Closed for coaching scope 2026-05-31; remains the playbook for re-smokes and the upcoming coached self-play. | CURRENT — playbook ready for re-use |
| [`TUNING.md`](TUNING.md) | Living deployment / tuning guide: provider assignments (production target vs self-play actuals — distinguished 2026-06-02), BATNA semantics, prompt-design notes, tuning changelog. | CURRENT — distinguishes aspirational production config from actual self-play config |

### Testing — the *how to know it works*

| Doc | What it is | Status |
|---|---|---|
| [`diplomat-testing-doc.md`](diplomat-testing-doc.md) | Testing strategy + tuning workflow: 4-layer test taxonomy (unit, prompt regression, integration, self-play), Pi smoke checklists, post-game report references, scenario library pointer. | CURRENT — canonical |

### Experimental records — the *what we tried, what we learned*

| Doc | What it is | Status |
|---|---|---|
| [`TUNING_LOG.md`](TUNING_LOG.md) | Active run-by-run record. Runs 7-10 with hypothesis / config / observations / learning / decisions / open items, plus a Summary of All Changes table covering all runs and a master Open Items list. | CURRENT — active log |
| [`TUNING_LOG_archive.md`](TUNING_LOG_archive.md) | Archived Runs 1-6 (infrastructure + extraction quality + scenario compiler arc). Moved out of the active log 2026-06-02 to keep it focused on the current experimental arc. | ARCHIVE — preserved for replay / regression |

### Domain knowledge — the *what we negotiate about*

| Doc | What it is | Status |
|---|---|---|
| [`Multi-Party Negotiation Scenarios.md`](Multi-Party%20Negotiation%20Scenarios.md) | Source catalogue: Harvard PON exercises (Harborco, Three-Party Coalition, Chestnut Village), historical congresses (Vienna, Camp David, Six-Party Talks), game-theoretic coalition templates. Provenance for Water Rights and Three-Party Coalition scenarios. | REFERENCE — static catalogue, used as input to scenario design |
| [`for-clankers.md`](for-clankers.md) | Clankmates platform agent setup guide. Describes inbox, channel posting, key handoff for the eventual `ClankmatesTransport`. | PROSPECTIVE — will become CURRENT when Clankmates work starts (NEXT_STEPS §5) |

---

## Module specs

One per pipeline module, in implementation order. Each ARCH file documents
the module's interface, types, inputs/outputs, state, and a usage example.
Several also carry schema (`ARCH_state_manager.md` SQL DDL,
`ARCH_event_store.md` messages table) and operational philosophy
(`ARCH_coaching.md` philosophy + cadence + edit-log workflow).

- [`ARCH_event_store.md`](ARCH_event_store.md) — append-only message log + schema
- [`ARCH_state_manager.md`](ARCH_state_manager.md) — domain state tables + schema (10 tables)
- [`ARCH_extraction.md`](ARCH_extraction.md) — text → structured state patches
- [`ARCH_reconciliation.md`](ARCH_reconciliation.md) — post-round dedup, fulfillment detection, inconsistency flagging
- [`ARCH_analyst.md`](ARCH_analyst.md) — state → intelligence reports
- [`ARCH_persona.md`](ARCH_persona.md) — faction identity loader with hot-reload
- [`ARCH_context_assembler.md`](ARCH_context_assembler.md) — assembles Decision Engine context (includes prompt-block layout)
- [`ARCH_generation.md`](ARCH_generation.md) — context → response text
- [`ARCH_adversarial.md`](ARCH_adversarial.md) — draft → adversarial analysis (skippable)
- [`ARCH_review_gate.md`](ARCH_review_gate.md) — approve / edit / block workflow
- [`ARCH_coaching.md`](ARCH_coaching.md) — operator input parsing + routing + coaching philosophy
- [`ARCH_transport.md`](ARCH_transport.md) — Telegram / CLI I/O
- [`ARCH_orchestrator.md`](ARCH_orchestrator.md) — composition + event loop (also covers `Pipeline` until that gets its own ARCH file)
- [`ARCH_flow.md`](ARCH_flow.md) — EventDrivenFlow / RoundSteppedFlow scheduling strategies
- [`ARCH_conversation_model.md`](ARCH_conversation_model.md) — staged migration plan (Stage 1 / 2a / 2b / 3)

---

## Governance (process / loop / contracts)

These docs control *how the project is worked on*, not the project itself.
Read them when working on phase planning, decisions, or autonomous-loop
discipline — otherwise leave them alone.

- [`GOVERNANCE.md`](GOVERNANCE.md) — Layer 0: universal process rules (regimes, modes, escalation)
- [`WORKER_SPEC.md`](WORKER_SPEC.md) — autonomous loop contract (only loaded in loop runs)
- [`DEVPLAN.md`](DEVPLAN.md) — phase plan + current status + cold-start summary (frontmatter drives the state machine)
- [`DEVLOG.md`](DEVLOG.md) / [`DEVLOG_archive.md`](DEVLOG_archive.md) — append-only execution journal
- [`DECISIONS.md`](DECISIONS.md) — non-trivial decisions with rationale; cross-checked at phase review
- [`PROJECT.md`](PROJECT.md) — scope / constraints / success criteria
- [`ARCHITECTURE.md`](ARCHITECTURE.md) — component map + coupling notes + key decisions
- [`CLAUDE.md`](CLAUDE.md) / [`CODEX.md`](CODEX.md) — agent adapters (which docs to load per task)

---

## Last reorganization: 2026-06-02

This session's documentation moves:

- **Deleted** `diplomat-system-spec.md` (1034-line v0.5 project-genesis spec). Four unique content blocks migrated to `ARCH_state_manager.md` (SQL DDL), `ARCH_coaching.md` (philosophy + cadence + edit-log workflow), `CLI_REFERENCE.md` (ad-hoc SQL inspection queries), `ARCH_context_assembler.md` (already present as Context Template, verified pre-migration).
- **Created** `TUNING_LOG_archive.md` and moved Runs 1-6 there. Active `TUNING_LOG.md` shrunk 1073 → 640 lines and now focuses on Runs 7-10 + active backlog.
- **Updated** `TUNING.md` §1 with explicit production-target-vs-self-play-actual distinction, including Run 10 finding on provider consistency.
- **Updated** `NEXT_STEPS.md` with Run 10 findings (§1.7 provider consistency, §1.8 cross-scenario defection test, §1.9 near-miss diagnostic), refreshed Suggested Sequencing, refreshed Open Items.
- **Created** this README.
