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
| Coaching | Parse and route operator input by tag | toolkit/coaching |
| Review Gate | Human approval workflow: approve/edit/revise/block (lazy-fetch reasoning/adversarial; `/revise:` LLM-rewrite with cap) | Transport (coaching channel), Pipeline (regenerate_with_directive) |
| Edit Classifier | Classify review-gate edits into six categories via LLM for prompt-tuning signal | toolkit/edit_classifier (extracted 2026-06-07; project-side `build_edit_classifier` factory only) |
| Scenario Authoring | Pre-game subsystem: narrative → analysis (compiler) + spec → analysis (builder) + fitness + verify utilities + coalition_values support. See [`ARCH_scenario_authoring.md`](ARCH_scenario_authoring.md); operator walkthrough in [`SCENARIO_GUIDE.md`](guides/SCENARIO_GUIDE.md). | toolkit/structured_llm |
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
- **EditClassification** — {category, confidence, rationale, classifier_model, classified_at} from Edit Classifier; category ∈ {tone_softer, tone_harder, commitment_removed, ambiguity_added, constraint_enforcement, persona_correction}
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
- `/revise: <directive>` — regenerate pending draft with operator directive (capped at 3 per review)
- `/edits-summary` — lazy-classify unclassified edits and render markdown summary table mid-game

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
| 4 | Coaching | Pure parsing, no external deps. Needed before operator input can be processed. | Phase 3 complete; extracted to `toolkit.coaching` 2026-06-05 (Diplomat consumes the toolkit module unchanged) |
| 5 | Transport | Platform I/O. Validates toolkit/telegram_client integration. Needed for end-to-end. | Phase 4 complete |
| 6 | Persona | File-based, simple. Needed before Generation. | Phase 5 complete |
| 7 | Analyst + Divergence | Two LLM calls + pure comparison. High value — intelligence drives decision quality. | Phase 6 complete |
| 8 | Context Assembler | Pure composition. Wires persona + intelligence + coaching + events into DecisionContext. | Phase 7 complete |
| 9 | Generation | LLM call with assembled context. Core output path. | Phase 8 complete |
| 10 | Review Gate | Human approval workflow via Telegram. Needed before any posting. | Phase 9 complete; Phase 31 refactored to OperatorReviewGate (transport-routed, chunked, lazy-fetch) |
| 11 | Adversarial | Optional LLM call. Valuable but skippable — Review Gate catches issues manually. | Phase 10 complete |
| 12 | Orchestrator | Wires everything. Event loop, round management, cost accountant, failure handling. Last because it requires all modules. | Complete |
| 13 | Reconciliation | Post-round state cleanup via LLM. Merges duplicate promises, detects fulfillments and broken commitments, flags inconsistencies. | Phase 18 complete |
| 14 | Scenario Compiler | Pre-game tool. Narrative → scored personas. Not a pipeline module — operator runs it before game start. | Phase 39 complete |
| 15 | Pipeline | Per-agent capability surface extracted from Orchestrator: persistence, extraction, coaching dispatch, round advancement, reconciliation/analysis, response generation, and query APIs. | Phase 22 complete |
| 16 | Flow | Scheduling strategies that drive one or more Pipelines, starting with event-driven production and round-stepped self-play. | Phase 22 complete |
| 17 | Scenario Builder | Constraint-driven reverse scenario generator. Operator writes a `ScenarioSpec`; tool searches scoring-table space via simulated-annealing hill-climb and emits `scenario_analysis.json` + per-faction `.txt` personas, including the scenario `pressure` object. Not a pipeline module — design tool only. | Complete |
| 18 | Scenario Viz | Deal-explorer HTML renderer extracted from `tools/viz.py` into `src/scenario_authoring/scenario_viz.py`. Reuses `find_pareto_frontier` from `verify_scenario_optimum` (no math duplication). Wired into `verify_scenario_optimum --viz` and `scenario_builder --viz`; exported on public API. `tools/viz.py` slimmed to run-discovery wrapper. | Phase 43 complete |
| 19 | Scenario Authoring Standalone | `scenario_authoring` package made self-contained (Phase 46): round-context renderer moved to `src/scenario_authoring/round_context.py` (stdlib-only leaf), severing the lone `modules.persona` load-time coupling; standalone contract locked by test; unified `python -m scenario_authoring build|compile|verify|brief` CLI added; package README written. `modules/persona` re-exports `CoachingContext` + `render_round_context_section` for back-compat. | Phase 46 complete |
| 20 | Coalition Scoring Contract | Coalition-exclusion scoring contract in `tests/self_play/game_environment.py` locked with 23 unit tests (Phase 47): `_find_coalition_value` sorted-set semantics, all `_resolve_deal_scores` paths (partial coalition, grand coalition full-agreement, no-deal, below-BATNA, malformed-input edges). Docstrings updated. `ARCH_scenario_authoring.md` updated with Path B scoring contract section. D-61 closed. | Phase 47 complete |
| 21 | Narrative Re-skin Shell | `src/scenario_authoring/scenario_narrative.py` (Phase 48): `apply_relabel` (bijective faction/issue/outcome identifier relabeling, numeric values preserved) + `assert_structure_preserved` (value-isomorphism guard: rejects numeric drift, non-bijective/incomplete maps) + `extract_catalogue_entry` (deterministic heading-scoped catalogue slicer) + `reskin_scenario` (one `structured_call` → relabeled analysis + themed prose) + `main()` CLI. Wired into `scenario_authoring` package public API and `narrative` subcommand. 37 new tests. D-62 closed. | Phase 48 complete |

## Testing Status

| Layer | Status |
|-------|--------|
| Unit and regression tests | Complete — 620 passed after Phase 48 (Phase 48 added 37 narrative re-skin tests; 1 replay test is flaky in full-suite ordering, passes in isolation) |
| Pipeline integration | Complete — 23 fake-backed Orchestrator integration tests (Phase 18 path coverage added Phase 20) |
| Transcript replay | Complete — 2 transcript fixtures, 5 replay tests |
| Prompt regression | Complete — 6 starter scenarios (4 extraction free, 2 generation require live LLM) |
| Multi-agent self-play | Phase 29 — GameEnvironment, scenario compiler, post-game scoring, state reconciliation, game-mode, baseline scorers, 41 infrastructure tests, 7 simulation runs across 4 scenario types. See `TUNING_LOG.md`. |

## Coupling Notes

- **Event Store ↔ State Manager:** loose — both use the same SQLite file but own separate tables. No code dependency. Event Store writes messages; State Manager writes domain tables.
- **Extraction ↔ State Manager:** moderate — Extraction produces StatePatch objects validated against State Manager's schema. Schema is loaded from config, not hardcoded in either module.
- **Extraction ↔ Coaching:** loose — Coaching routes INTEL notes to Extraction with `trigger_type='intel_correction'`. Same Extraction interface, different trigger.
- **Analyst ↔ State Manager + Event Store:** read-only — Analyst consumes `get_full_state()` output and recent events (transcript). Never writes. Recent events added in Phase 18 to give the analyst conversation context alongside structured state.
- **Context Assembler ↔ everything:** read-only fan-in — assembles from Persona, Analyst, Event Store, Coaching outputs. The only module that knows the shape of the Generation context window.
- **Generation ↔ Context Assembler:** tight — Generation consumes DecisionContext directly. Changes to context structure affect both.
- **Review Gate ↔ Transport:** tight — `OperatorReviewGate` consumes the pipeline's `Transport` for coaching-channel I/O and now sends one full coaching message per section while the shared toolkit transport handles oversize auto-chunking. No direct `toolkit/telegram_client` dependency. The orchestrator factory passes the already-built transport module when constructing the review gate.
- **Review Gate ↔ Pipeline.dispatch_operator:** passive handler — `handle_command()` is called by `dispatch_operator()` on every slash command before falling through to the normal operator router. The gate never polls `get_next_update()` directly.
- **Flow ↔ operator-input routing:** `EventDrivenFlow.process_event()` consumes `Transport.listen()` and routes operator-tagged events through `Pipeline.dispatch_operator()`. **Any other flow that drives a passive `OperatorReviewGate` must provide its own operator-input bridge** — `RoundSteppedFlow` does not have a listen-loop, so coached self-play uses `CoachedGameEnvironment._listen_for_operator(tg_transport, pipeline)` to forward operator events from a real `TelegramBotTransport.listen()` into `dispatch_operator()`. Without this bridge the gate hangs at the first review prompt. See D-44 + `ARCH_review_gate.md` "Flow Wiring Requirement".
- **Scenario Authoring ↔ Persona (Phase 46):** `modules/persona/__init__.py` imports `CoachingContext` + `render_round_context_section` FROM `scenario_authoring.round_context` (pipeline → package, same direction as `run_simulation`/`coached_game`). The `scenario_authoring` package has zero load-time pipeline imports. This coupling is intentional: the round-context renderer lives in the package as a liftable stdlib-only leaf.
- **Orchestrator ↔ all modules:** tight by design — it is the composition layer. Changes to pipeline topology affect only the Orchestrator.
- **All LLM modules ↔ toolkit:** two-layer via adapter — All four modules (Extraction, Analyst, Generation, Adversarial) call `toolkit.structured_llm.structured_call()` for schema-enforced JSON output with retry. This goes through the injected `llm_client.complete(messages, config, tier)` interface. In production, `ToolkitLLMAdapter` (in `src/adapters.py`) wraps toolkit's real `complete()` and optionally routes through `CostAccountant.complete()` for budget enforcement and ledger tracking. In tests, fakes implement the same dict/str interface. Modules never import from toolkit directly.
- **ToolkitLLMAdapter ↔ CostAccountant:** optional coupling — when a `cost_accountant` is injected, the adapter routes every LLM call through `accountant.complete()` which estimates cost, checks budgets, calls the underlying LLM, and writes a ledger entry. Without an accountant, the adapter calls `llm_client.complete()` directly (test/offline mode). The `DiplomatCostGate` provides the Orchestrator's check-before-call budget pattern using the same accountant instance.
- **Orchestrator ↔ State Manager:** write path — Orchestrator calls the 5 persistence methods (`store_coaching`, `store_intelligence`, `set_game_state`, `store_adversarial_read`, `mark_coaching_consumed`) added in Phase 12.
- **Edit Classifier ↔ State Manager:** write path — `LLMEditClassifier.classify()` results are stored via `StateManager.store_edit_classification(review_gate_edit_id, classification)`. `get_edit_classifications()` returns a joined view with `review_gate_edits` metadata. FK constraint: `edit_classifications.review_gate_edit_id → review_gate_edits.id`.
- **Edit Classifier ↔ toolkit/edit_classifier:** the classifier primitive lives in `toolkit.edit_classifier` (extracted from Diplomat 2026-06-07; see `toolkit/ARCH_edit_classifier.md`). Diplomat's `src/modules/edit_classifier/` keeps only the project-side `build_edit_classifier(...)` factory that reads `pipeline.yaml`'s `{"primary": {...}}` provider shape and the local `DEFAULT_PROMPT_PATH` constant pointing at `config/prompts/edit_classifier.txt`. The toolkit primitive itself calls `toolkit.structured_llm.structured_call(tier="commodity", purpose="edit_classification")` with a six-category JSON schema enforced at the toolkit layer — same integration pattern as Extraction, Generation, Adversarial.
- **Scenario Authoring ↔ structured_call:** the subsystem (`src/scenario_authoring/`, see [`ARCH_scenario_authoring.md`](ARCH_scenario_authoring.md)) routes all LLM calls through `toolkit.structured_llm.structured_call` at the `commodity` tier. Three LLM-consuming entry points: `scenario_compiler.analyze_scenario` (narrative → structured analysis), `scenario_compiler.fill_narrative` (overlay prose onto builder-emitted stubs), and `scenario_narrative.reskin_scenario` (themed relabel + prose via bijective relabel_map). Pure-Python modules (`scenario_builder`, `scenario_fitness`, `scenario_spec`) consume no LLM. `verify_scenario_optimum` is a pure CLI + library that reads an analysis and reports its payoff structure. No runtime pipeline dependency — the subsystem produces files; `GameEnvironment.score_game` reads them.
- **Reconciliation factory:** `build_reconciler(llm_client, llm_providers_config, tier, attribution)` in `src/modules/reconciliation/__init__.py` is the canonical way to construct a `StateReconciler`. Both `src/main.py` (`_attach_reconciler`) and self-play (`game_environment.py`) use it. `subsystem_llm_config(primary, tier)` converts a pipeline.yaml provider config dict to the `{provider, models, api_key}` format used by `structured_call`.
- **Extension: new Transport implementation** → additive (new class, config change). No other modules affected.
- **Extension: new LLM provider** → toolkit config change only. No Diplomat code changes.
- **Extension: different game domain** → replace config/ directory and persona files. Scenario compiler can auto-generate personas from a narrative description.
- **Bare-prompt ablation mode** → use `GameEnvironment(bare_mode=True)` (or pass `bare_module_overrides()` as `extra_module_overrides`) to disable Extraction/Analyst/Divergence/Reconciliation/Adversarial/Coaching for ablation experiments. See `tests/self_play/bare_mode.py`.

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
