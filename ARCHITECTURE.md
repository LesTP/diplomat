# Diplomat — Architecture

## Component Map

| Component | Responsibility | Dependencies |
|-----------|---------------|--------------|
| Transport | Platform I/O: send messages, receive events (Telegram, CLI) | toolkit/telegram_client |
| Event Store | Append-only raw event log with round tagging | none (SQLite) |
| State Manager | Structured domain state: factions, promises, coalitions, inconsistencies. Schema-validated patches, audit log. | none (SQLite) |
| Extraction | Text → structured state patch via LLM | toolkit/llm_client |
| Analyst | Structured state → intelligence report via LLM. Two instances (primary + secondary) with different providers. | toolkit/llm_client |
| Divergence | Compare two analysis outputs against configurable thresholds | none (pure Python, sub-module of Analyst) |
| Persona | Faction identity configuration with hot-reload | none (filesystem) |
| Context Assembler | Assemble all inputs into a Decision Engine context window | none (pure composition) |
| Generation | Context → response text via LLM | toolkit/llm_client |
| Adversarial | Draft → adversarial analysis via LLM (skippable) | toolkit/llm_client |
| Coaching | Parse and route operator input by tag | none (pure parsing) |
| Review Gate | Human approval workflow: approve/edit/block | toolkit/telegram_client |
| Orchestrator | Pipeline topology, event loop, round management, cost accountant wiring | All modules, toolkit/cost_accountant |

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
| 7 | Analyst + Divergence | Two LLM calls + pure comparison. High value — intelligence drives decision quality. | Not started |
| 8 | Context Assembler | Pure composition. Wires persona + intelligence + coaching + events into DecisionContext. | Not started |
| 9 | Generation | LLM call with assembled context. Core output path. | Not started |
| 10 | Review Gate | Human approval workflow via Telegram. Needed before any posting. | Not started |
| 11 | Adversarial | Optional LLM call. Valuable but skippable — Review Gate catches issues manually. | Not started |
| 12 | Orchestrator | Wires everything. Event loop, round management, cost accountant, failure handling. Last because it requires all modules. | Not started |

## Coupling Notes

- **Event Store ↔ State Manager:** loose — both use the same SQLite file but own separate tables. No code dependency. Event Store writes messages; State Manager writes domain tables.
- **Extraction ↔ State Manager:** moderate — Extraction produces StatePatch objects validated against State Manager's schema. Schema is loaded from config, not hardcoded in either module.
- **Extraction ↔ Coaching:** loose — Coaching routes INTEL notes to Extraction with `trigger_type='intel_correction'`. Same Extraction interface, different trigger.
- **Analyst ↔ State Manager:** read-only — Analyst consumes `get_full_state()` output. Never writes.
- **Context Assembler ↔ everything:** read-only fan-in — assembles from Persona, Analyst, Event Store, Coaching outputs. The only module that knows the shape of the Generation context window.
- **Generation ↔ Context Assembler:** tight — Generation consumes DecisionContext directly. Changes to context structure affect both.
- **Review Gate ↔ Transport:** moderate — Review Gate uses toolkit/telegram_client for its own UI (sending drafts, receiving commands). Separate from the main Transport instance.
- **Orchestrator ↔ all modules:** tight by design — it is the composition layer. Changes to pipeline topology affect only the Orchestrator.
- **All LLM modules ↔ toolkit:** one-way — Extraction, Analyst, Generation, Adversarial import from toolkit/llm_client. Toolkit never imports from Diplomat.
- **Extension: new Transport implementation** → additive (new class, config change). No other modules affected.
- **Extension: new LLM provider** → toolkit config change only. No Diplomat code changes.
- **Extension: different game domain** → replace config/ directory. No code changes.

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
- **Orchestrator ↔ toolkit/cost_accountant budget lifecycle** — the Orchestrator creates a CostBudget per round from pipeline.yaml config. Unclear whether the budget should reset per round (strict) or accumulate across rounds (flexible with session cap). Resolve during Module 12.
- **Review Gate timeout** — what happens if the operator doesn't respond before the next round boundary. Options: auto-block after N minutes, carry draft forward, alert and wait. Resolve during Module 10.
- **Debounce strategy for Extraction** — pipeline.yaml specifies `debounce_seconds: 2` but the batching semantics (time-window batch vs. per-message cooldown) are unspecified. Resolve during Module 12.
