# ARCH: Orchestrator

## Purpose
Pipeline topology and wiring. The Orchestrator is the only component that knows the full pipeline. It is not a module — it is the composition layer that instantiates all modules from pipeline.yaml, owns the event loop, manages round boundaries, routes coaching events, triggers the response pipeline, handles per-module failures, and wraps all LLM calls through toolkit/cost_accountant for budget enforcement.

## Responsibilities

1. **Startup:** Load pipeline.yaml, build LLMConfig objects, construct CostAccountant, instantiate all modules, validate API credentials, start Transport listener.
2. **Event loop:** Process each InboundEvent — append to Event Store, route through Coaching or Extraction, check response triggers.
3. **Round management:** Detect round boundaries (signal or time-based), trigger dual-analyst analysis, store intelligence records, increment round counter.
4. **Response pipeline:** Orchestrate Persona → Context Assembler → Generation → Adversarial → Review Gate → Transport.send().
5. **Failure handling:** Check each module's success flag, apply per-module failure strategy (skip, retry, alert, fallback).
6. **Cost governance:** Route all LLM calls through toolkit/cost_accountant with per-round CostBudget.
7. **Command dispatch:** Handle operator slash commands (/status, /state, /ledger, /intel, /divergences, /edits).

## Event Loop

On each InboundEvent from Transport:

```
1. Event Store: append(event)
2. Coaching Parser: check if source == 'operator'
   a. If Command: dispatch to command handler
   b. If CoachingEvent with route='state_updater':
      - Extraction: extract(content, current_state, 'intel_correction')
      - State Manager: apply_patch(patch, PatchSource('intel_coaching', coaching_id))
   c. If CoachingEvent with route='coaching_queue':
      - Store in coaching table, mark unconsumed
3. If source != 'operator':
   - Extraction: extract(content, current_state, 'message') [debounced]
   - State Manager: apply_patch(patch, PatchSource('message', event_id))
4. Check if response needed:
   - If direct address to our faction -> trigger response pipeline
   - If operator /preview command -> trigger response pipeline
   - If scheduled response time -> trigger response pipeline
```

On round boundary:

```
1. Analyst Primary: analyze(state_manager.get_full_state())
2. Analyst Secondary: analyze(state_manager.get_full_state())
3. Divergence: compare(primary_result, secondary_result)
4. Store intelligence record (both outputs + divergences)
5. Increment round counter
```

On response trigger:

```
1. Persona: get_base_prompt(), build_round_context(...)
2. Context Assembler: assemble(...)
3. Generation: generate(context)
4. Adversarial: read(draft) [if enabled]
5. Review Gate: submit(draft, adversarial_result)
6. If ReviewDecision.action != 'blocked':
   Transport: send(OutboundMessage(final_text, 'public'))
7. Store adversarial_read record
8. Mark coaching entries consumed
```

## Failure Handling

| Step | On failure |
|---|---|
| Extraction (message) | Log, skip patch for this batch, continue |
| Extraction (INTEL) | Log, retain coaching entry, retry at round boundary |
| Analyst Primary | Log, skip round analysis, alert operator |
| Analyst Secondary | Log, proceed with primary only, flag in intelligence record |
| Generation | Retry once with exponential backoff, then alert operator |
| Adversarial | Log, pass empty result to Review Gate with warning flag |
| Review Gate | Log, hold response, alert operator |
| Transport send | Retry three times, then log and discard |
| Cost budget exceeded | Log, alert operator, skip the LLM call (hard limit) |
| Rate limit (via Cost Accountant) | If abort_on_rate_limit, stop and alert. Otherwise fall through to provider rotation. |

## Startup Sequence

1. Load .env and pipeline.yaml
2. Build toolkit.llm_client.LLMConfig objects from llm_providers section
3. Construct toolkit.cost_accountant.CostAccountant from cost section
4. Instantiate module implementations from registry, injecting LLMConfig + CostAccountant
5. Initialise SQLite (WAL mode, schema if new)
6. Load prompt files (fail fast if missing)
7. Validate all API credentials with a lightweight test call (via toolkit/llm_client)
8. Start Transport listener (via toolkit/telegram_client)
9. Start event loop
10. Log: DIPLOMAT ONLINE - Round {n} - {faction_id} - session budget ${X.XX}

## Configuration

All wiring comes from `config/pipeline.yaml`. The Orchestrator reads:
- Module implementation class names (resolved via registry.py)
- LLM provider configs (mapped to toolkit.llm_client.LLMConfig)
- Cost budgets (mapped to toolkit.cost_accountant.CostBudget)
- Round detection mode (signal pattern or time-based duration)
- Feature flags (adversarial.enabled, review_gate.enabled)

## Provisional Contract
Budget lifecycle: the Orchestrator creates a CostBudget per round from pipeline.yaml config. Whether the budget resets per round or accumulates with a session cap is unresolved. Resolve during implementation.

## Inputs
- pipeline.yaml — all configuration
- InboundEvent stream from Transport
- Module outputs from every module in the pipeline

## Outputs
- OutboundMessage via Transport (approved responses)
- Operator notifications via Transport coaching channel (alerts, status responses)
- Side effects: all database writes flow through Event Store and State Manager

## Construction — OrchestrationOptions

`Orchestrator(config_path, options=OrchestrationOptions(...), ...)` accepts an `OrchestrationOptions` dataclass:

```python
@dataclass
class OrchestrationOptions:
    auto_response_enabled: bool = True   # False in self-play (explicit round stepping)
    total_rounds: int | None = None      # None = production (endgame-blind)
```

Pass `options=OrchestrationOptions(auto_response_enabled=False, total_rounds=4)` to override defaults. These are NOT attributes on `Orchestrator` itself — only the `options` object is stored.

## Public Round Management

`advance_to_round(n: int)` — sets `current_round` to `n` and resets the per-round budget. Used by self-play harnesses to step through rounds. Replaces direct `orchestrator.current_round = n` pokes.

## State
- Round counter (persisted in game_state table)
- `options.total_rounds: int | None` — Default `None` (production games don't know the count). Persona uses this for "Round N of M" rendering and penultimate/final-round endgame reminders.
- `options.auto_response_enabled: bool` — Default `True` (production reacts to direct-address messages). Self-play sets `False` so `_is_direct_address` triggers don't auto-fire response pipelines.
- Module instances (in-memory, reconstructed on restart)
- CostAccountant session totals (in-memory, ledger persisted to data/cost_ledger.jsonl)
- Coaching queue consumption tracking (in coaching table, managed via State Manager)

## Usage Example

```python
from orchestrator import Orchestrator

orch = Orchestrator(config_path="config/pipeline.yaml")
await orch.start()   # runs until shutdown signal
await orch.shutdown() # graceful cleanup
```
