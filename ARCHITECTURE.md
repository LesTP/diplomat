# Diplomat — Architecture

## Component Map

| Component | Responsibility | Dependencies |
|-----------|---------------|--------------|
| Transport | Platform I/O: send messages, receive events (Telegram, CLI) | toolkit/telegram_client |
| Event Store | Append-only raw event log with round tagging | none (SQLite) |
| State Manager | Structured domain state with schema-validated patches, audit log, entity CRUD | none (SQLite) |
| Extraction | Text → structured state patch via LLM (structured_call) | toolkit/structured_llm |
| Reconciliation | Post-round state cleanup: dedup promises, detect fulfillments/broken/inconsistencies, catch missed proposals | toolkit/structured_llm |
| Analyst | State + transcript → intelligence report via LLM. Two instances with different providers. | toolkit/structured_llm |
| Divergence | Compare two analysis outputs against configurable thresholds | none (pure Python, sub-module of Analyst) |
| Persona | Faction identity configuration with hot-reload | none (filesystem) |
| Context Assembler | Assemble all inputs into a Decision Engine context window | none (pure composition) |
| Generation | Context → response text via LLM (structured_call for JSON mode) | toolkit/structured_llm |
| Adversarial | Draft → adversarial analysis via LLM (skippable) | toolkit/structured_llm |
| Coaching | Parse and route operator input by tag | none (pure parsing) |
| Review Gate | Human approval workflow: approve/edit/block | toolkit/telegram_client |
| Scenario Compiler | Narrative scenario → scored persona files with point tables, BATNAs, deception tactics, game-mode | toolkit/structured_llm |
| Pipeline | Per-agent capability surface: event storage, extraction, operator dispatch, round advancement, reconciliation/analysis, response generation, and query APIs | All runtime modules, toolkit/cost_accountant |
| Flow | Scheduling strategies that drive one or more Pipelines; current implementations are EventDrivenFlow and RoundSteppedFlow | Pipeline, Transport or moderator/application driver |
| Orchestrator | Compatibility constructor that builds the old composition core and returns EventDrivenFlow(Pipeline(core)) | Pipeline, Flow, all modules |

## Data Flow

### Core Objects
- **InboundEvent** — {source, channel, content, timestamp, metadata} from Transport
- **StoredEvent** — {event_id, round_number, event} from Event Store
- **StatePatch** — {data} validated against config/schemas/state_patch.json
- **PatchSource** — {trigger_type, trigger_ref} for audit trail
- **AnalysisResult** — {success, provider_id, report, error, timestamp} from Analyst
- **Divergence** — {field, primary_value, secondary_value, note} from divergence comparison
- **CoachingContext** — {priorities, constraints, watch_items, tone_notes} accumulated coaching
- **CoachingEvent** — {coaching_type, content, route} parsed operator input
- **DecisionContext** — {system_prompt, user_prompt, metadata} assembled for Generation
- **GenerationResult** — {success, response_text, reasoning, error} from Generation
- **AdversarialResult** — {success, analysis, error} from Adversarial
- **ReviewDecision** — {action, final_text, edit_notes} from Review Gate
- **OutboundMessage** — {content, channel, recipient} sent via Transport

### Flow

**Message processing (per inbound event):**
```
Transport → InboundEvent → Event Store (append)
  → Extraction (text → StatePatch, via toolkit/llm_client)
  → State Manager (apply_patch with audit)
```

**Operator coaching (per operator message):**
```
Transport → InboundEvent → Coaching Parser
  → If INTEL tag: Extraction (intel_correction) → State Manager
  → If other tag: coaching table (unconsumed, awaits next Generation)
  → If command: dispatch to command handler
```

**Round boundary (on round signal):**
```
State Manager (get_full_state)
  → Analyst Primary (via toolkit/llm_client) → AnalysisResult
  → Analyst Secondary (via toolkit/llm_client) → AnalysisResult
  → Divergence (compare) → List[Divergence]
  → intelligence table (store both + divergences)
```

**Response pipeline (on trigger):**
```
Persona (base_prompt + round_context)
  + intelligence report + divergences
  + recent StoredEvents + unconsumed coaching
  → Context Assembler → DecisionContext
  → Generation (via toolkit/llm_client) → GenerationResult
  → Adversarial (via toolkit/llm_client, if enabled) → AdversarialResult
  → Review Gate (via toolkit/telegram_client) → ReviewDecision
  → Transport (send, if not blocked)
```

**All LLM calls routed through toolkit/cost_accountant for budget enforcement.**

## Interaction Model

### User Actions (Operator)
- `PRIORITY: ...` — set compass for next round
- `CONSTRAINT: ...` — hard boundary or trap detected
- `INTEL: ...` — factual correction routed through Extraction to State Manager
- `TONE: ...` — behavioral adjustment
- `WATCH: ...` — attention direction
- Untagged text — free coaching, included in next Generation call
- `/preview` — trigger response pipeline without posting
- `/approve` — approve draft from review gate
- `/edit: ...` — approve with modifications
- `/block` — reject draft
- `/status` — game state summary
- `/state` — current structured state
- `/ledger` — promise ledger
- `/intel` — latest intelligence report
- `/divergences` — analyst disagreements
- `/edits` — review gate edit log

### UI States
- **Listening** — Transport receiving events, Extraction processing, no active response
- **Analyzing** — Round boundary triggered, Analyst calls in flight
- **Generating** — Response pipeline active, draft being produced
- **Awaiting review** — Draft + adversarial analysis sent to operator, waiting for command
- **Posting** — Approved response being sent via Transport

### Layout Zones
N/A — Telegram chat is the sole interface; all output is sequential message-based.

## Implementation Sequence

| Order | Module | Rationale | Status |
|-------|--------|-----------|--------|
| 1 | Event Store | Leaf dependency. Append-only SQLite, simplest module. Everything downstream needs stored events. | Complete |
| 2 | State Manager | Leaf dependency. Domain tables, schema validation, audit log. Extraction and Analyst depend on it. | Complete |
| 3 | Extraction | First LLM-consuming module. Validates toolkit/llm_client integration. Feeds State Manager. | Phase 2 complete |
| 4 | Coaching | Pure parsing, no external deps. Needed before operator input can be processed. | Phase 3 complete |
| 5 | Transport | Platform I/O. Validates toolkit/telegram_client integration. Needed for end-to-end. | Phase 4 complete |
| 6 | Persona | File-based, simple. Needed before Generation. | Phase 5 complete |
| 7 | Analyst + Divergence | Two LLM calls + pure comparison. High value — intelligence drives decision quality. | Phase 6 complete |
| 8 | Context Assembler | Pure composition. Wires persona + intelligence + coaching + events into DecisionContext. | Phase 7 complete |
| 9 | Generation | LLM call with assembled context. Core output path. | Phase 8 complete |
| 10 | Review Gate | Human approval workflow via Telegram. Needed before any posting. | Phase 9 complete |
| 11 | Adversarial | Optional LLM call. Valuable but skippable — Review Gate catches issues manually. | Phase 10 complete |
| 12 | Orchestrator | Wires everything. Event loop, round management, cost accountant, failure handling. Last because it requires all modules. | Complete |
| 13 | Reconciliation | Post-round state cleanup via LLM. Merges duplicate promises, detects fulfillments and broken commitments, flags inconsistencies. | Phase 18 complete |
| 14 | Scenario Compiler | Pre-game tool. Narrative → scored personas. Not a pipeline module — operator runs it before game start. | Phase 18 complete |
| 15 | Pipeline | Per-agent capability surface extracted from Orchestrator: persistence, extraction, coaching dispatch, round advancement, reconciliation/analysis, response generation, and query APIs. | Phase 22 complete |
| 16 | Flow | Scheduling strategies that drive one or more Pipelines, starting with event-driven production and round-stepped self-play. | Phase 22 complete |

## Testing Status

| Layer | Status |
|-------|--------|
| Unit and regression tests | Complete — 346 tests across the regression suite |
| Pipeline integration | Complete — 23 fake-backed Orchestrator integration tests (Phase 18 path coverage added Phase 20) |
| Transcript replay | Complete — 2 transcript fixtures, 5 replay tests |
| Prompt regression | Complete — 6 starter scenarios (4 extraction free, 2 generation require live LLM) |
| Multi-agent self-play | Phase 18 — GameEnvironment, scenario compiler, post-game scoring, state reconciliation, 41 infrastructure tests, 7 simulation runs across 4 scenario types. See `TUNING_LOG.md`. |

## Coupling Notes

- **Event Store ↔ State Manager:** loose — both use the same SQLite file but own separate tables. No code dependency. Event Store writes messages; State Manager writes domain tables.
- **Extraction ↔ State Manager:** moderate — Extraction produces StatePatch objects validated against State Manager's schema. Schema is loaded from config, not hardcoded in either module.
- **Extraction ↔ Coaching:** loose — Coaching routes INTEL notes to Extraction with `trigger_type='intel_correction'`. Same Extraction interface, different trigger.
- **Analyst ↔ State Manager + Event Store:** read-only — Analyst consumes `get_full_state()` output and recent events (transcript). Never writes. Recent events added in Phase 18 to give the analyst conversation context alongside structured state.
- **Context Assembler ↔ everything:** read-only fan-in — assembles from Persona, Analyst, Event Store, Coaching outputs. The only module that knows the shape of the Generation context window.
- **Generation ↔ Context Assembler:** tight — Generation consumes DecisionContext directly. Changes to context structure affect both.
- **Review Gate ↔ Transport:** moderate — Review Gate uses toolkit/telegram_client for its own UI (sending drafts, receiving commands). Separate from the main Transport instance.
- **Orchestrator ↔ all modules:** tight by design — it is the composition layer. Changes to pipeline topology affect only the Orchestrator.
- **All LLM modules ↔ toolkit:** two-layer via adapter — All four modules (Extraction, Analyst, Generation, Adversarial) call `toolkit.structured_llm.structured_call()` for schema-enforced JSON output with retry. This goes through the injected `llm_client.complete(messages, config, tier)` interface. In production, `ToolkitLLMAdapter` (in `src/adapters.py`) wraps toolkit's real `complete()` and optionally routes through `CostAccountant.complete()` for budget enforcement and ledger tracking. In tests, fakes implement the same dict/str interface. Modules never import from toolkit directly.
- **ToolkitLLMAdapter ↔ CostAccountant:** optional coupling — when a `cost_accountant` is injected, the adapter routes every LLM call through `accountant.complete()` which estimates cost, checks budgets, calls the underlying LLM, and writes a ledger entry. Without an accountant, the adapter calls `llm_client.complete()` directly (test/offline mode). The `DiplomatCostGate` provides the Orchestrator's check-before-call budget pattern using the same accountant instance.
- **Orchestrator ↔ State Manager:** write path — Orchestrator calls the 5 persistence methods (`store_coaching`, `store_intelligence`, `set_game_state`, `store_adversarial_read`, `mark_coaching_consumed`) added in Phase 12.
- **Scenario Compiler ↔ structured_call:** the compiler (`src/tools/scenario_compiler.py`) uses `structured_call` to parse narrative scenarios into scoring tables. It generates persona files consumed by `FileBasedPersona`. No runtime dependency — it's a pre-game preparation tool.
- **Reconciliation factory:** `build_reconciler(llm_client, llm_providers_config, tier, attribution)` in `src/modules/reconciliation/__init__.py` is the canonical way to construct a `StateReconciler`. Both `src/main.py` (`_attach_reconciler`) and self-play (`game_environment.py`) use it. `subsystem_llm_config(primary, tier)` converts a pipeline.yaml provider config dict to the `{provider, models, api_key}` format used by `structured_call`.
- **Extension: new Transport implementation** → additive (new class, config change). No other modules affected.
- **Extension: new LLM provider** → toolkit config change only. No Diplomat code changes.
- **Extension: different game domain** → replace config/ directory and persona files. Scenario compiler can auto-generate personas from a narrative description.

## Key Decisions

D-1: Toolkit integration over direct SDK dependencies
Date: 2026-05-24 | Status: Closed
Decision: All LLM calls go through toolkit/llm_client. All Telegram I/O goes through toolkit/telegram_client. Cost governance via toolkit/cost_accountant. No direct provider SDK imports.
Rationale: Sibling projects already consume toolkit. Eliminates redundant integrations, gains provider rotation, rate-limit handling, and cost tracking.
Revisit if: Diplomat needs structured output enforcement or another capability that toolkit doesn't support and extending toolkit is too costly.

D-2: Single LLMAnalyst implementation parameterised by provider
Date: 2026-05-24 | Status: Closed
Decision: One LLMAnalyst class, configured with different LLMConfig objects for primary and secondary. Not separate per-provider classes.
Rationale: Analysis logic is identical across providers. Provider selection is config, not code. Adding a third analyst is a pipeline.yaml change.
Revisit if: Provider-specific features (extended thinking, tool use) become important for analysis quality.

D-3: Python (async) as implementation language
Date: 2026-05-24 | Status: Closed
Decision: Python for all modules, async throughout.
Rationale: Consistent with toolkit. Good Telegram/SQLite libraries. Same as all sibling projects.
Revisit if: Performance on Pi becomes a problem.

D-4: SQLite as sole persistence layer
Date: 2026-05-24 | Status: Closed
Decision: Single SQLite file with WAL mode for all state.
Rationale: Simplest option that survives restarts. No external dependencies. Same pattern as Codexbot.
Revisit if: Concurrent write contention or multi-machine state sharing needed.

D-5: Review gate enabled by default
Date: 2026-05-24 | Status: Closed
Decision: No autonomous posting for the first game. review_gate.enabled: true.
Rationale: First game calibrates the faction prompt. Edit log is the primary feedback mechanism.
Revisit if: Operator consistently approves without edit.

## Provisional Contracts

- **Extraction ↔ toolkit/llm_client structured output** — Resolved during Phase 2. Extraction handles JSON schema enforcement locally: prompt engineering + response parsing + jsonschema validation. No toolkit extension needed. Empty root object (`{}`) is a valid patch.
- **Orchestrator ↔ toolkit/cost_accountant budget lifecycle** — Resolved during Phase 11. The Orchestrator resets a strict per-round budget from `pipeline.yaml` and checks `available_budget()` before every LLM-backed call it owns; session totals remain the cost accountant ledger's responsibility.
- **Debounce strategy for Extraction** — Resolved during Phase 11. Game-message extraction uses per-message cooldown: each new message cancels and replaces the pending extraction task.
