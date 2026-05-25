---
phase: 1
blocked: false
state: execute
steps_remaining: 6
---

# Diplomat — Development Plan

## Cold Start Summary

- **What this is** — AI faction agent for a multiplayer diplomacy game, with human coaching via Telegram review gate.
- **Key constraints** — Raspberry Pi deployment, all LLM calls via toolkit/llm_client, all Telegram I/O via toolkit/telegram_client, cost governance via toolkit/cost_accountant, SQLite persistence.
- **Gotchas** —
  - Bot vs. user account question must be resolved with game moderator before Transport implementation
  - Round structure (signal vs. time-based) must be confirmed before Orchestrator event loop
  - toolkit/llm_client returns plain text — Extraction module needs to handle JSON schema enforcement locally

## Current Status

- **Phase** — Phase 1 (Event Store + State Manager)
- **Focus** — Step 1.3: Event Store tests
- **Blocked/Broken** — None

## Phase 1: Event Store + State Manager

### Steps

| Step | Description | Status |
|------|-------------|--------|
| 1.1 | Shared types: `InboundEvent`, `StoredEvent`, `EventFilter`, `StatePatch`, `PatchSource` in `src/modules/types.py` | ✅ Complete |
| 1.2 | SQLiteEventStore: implement `append()` and `query()` with WAL mode in `src/modules/event_store/` | ✅ Complete |
| 1.3 | Event Store tests: `tests/test_event_store.py` covering append, query filters, edge cases | ⬜ Not started |
| 1.4 | State patch JSON schema: `config/schemas/state_patch.json` for faction_state, promises, coalitions, inconsistencies | ⬜ Not started |
| 1.5 | SQLiteStateManager: implement `get()`, `query()`, `apply_patch()`, `get_full_state()` with schema validation and audit log | ⬜ Not started |
| 1.6 | State Manager tests: `tests/test_state_manager.py` covering all public API + patch validation + audit log | ⬜ Not started |

### Design Notes (from ARCH files)

- Both modules share a single SQLite file (`data/game.db`) with WAL mode — no code dependency between them, separate table ownership.
- `InboundEvent` is owned by Transport but referenced by Event Store; define it in shared `types.py` to avoid circular imports.
- State Manager's `apply_patch()` validates against `state_patch.json` at apply time, writes audit entry to `state_change_log`, then applies changes to domain tables.
- `get_full_state()` returns a snapshot of all faction_state rows, pending promises, coalitions, and unspent inconsistencies — formatted for the Analyst prompt.
- All queries parameterised; no raw string interpolation into SQL.
