---
phase: 1
blocked: false
state: plan
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

- **Phase** — Not started
- **Focus** — Initial setup
- **Blocked/Broken** — None

## Phase 1: Event Store + State Manager

<!-- Break into steps during the Phase Plan action. These are the leaf
     dependencies — everything else builds on top of them. -->

