# ARCH: Context Assembler

## Purpose
Assemble all inputs into a single DecisionContext for the Generation module. The only module that knows the shape of the Decision Engine's context window. Combines persona prompt, round context, intelligence report, divergences, recent transcript, and coaching into a structured system+user prompt pair. If the context structure changes, this is the only module that changes.

INTEL coaching notes are deliberately excluded from the assembled context — they have already been applied to the database by the Extraction module and appear in the Analyst output. This prevents double-counting corrections.

## Public API

### assemble
- **Signature:** `async def assemble(self, persona_prompt: str, round_context: str, intelligence: dict, divergences: list[Divergence], recent_events: list[StoredEvent], free_coaching: list[CoachingEntry], review_gate_enabled: bool, bare_mode: bool = False) -> DecisionContext`
- **Parameters:**
  - persona_prompt: str — from Persona.get_base_prompt()
  - round_context: str — from Persona.build_round_context()
  - intelligence: dict — primary analyst report (validated against intelligence.json schema)
  - divergences: list[Divergence] — from Divergence.compare()
  - recent_events: list[StoredEvent] — from Event Store (last N messages)
  - free_coaching: list[CoachingEntry] — unconsumed coaching queue entries (PRIORITY, CONSTRAINT, TONE, WATCH, FREE — not INTEL)
  - review_gate_enabled: bool — controls output format instruction (JSON vs plain text)
  - bare_mode: bool = False — when True, delegates to bare path (see §Bare Mode below)
- **Returns:** DecisionContext
- **Errors:** none

## Types

```python
@dataclass
class DecisionContext:
    system_prompt: str
    user_prompt: str
    metadata: dict        # round_number, event_count, coaching_count — for logging

@dataclass
class CoachingEntry:
    coaching_type: str    # 'PRIORITY' | 'CONSTRAINT' | 'TONE' | 'WATCH' | 'FREE'
    content: str
    timestamp: datetime
```

## Context Template

Assembled in this order:

```
[Persona.get_base_prompt()]

[Persona.build_round_context()]

--- INTELLIGENCE SUMMARY ---
[Primary intelligence report, pretty-printed]

--- ANALYST DIVERGENCES ---
[divergence_flags if any | 'No divergences. Both analysts agree.']

--- RECENT TRANSCRIPT (last {n} messages) ---
[Round N | Faction | channel — content]

--- COACHING FROM OPERATOR ---
[Unconsumed PRIORITY / CONSTRAINT / TONE / WATCH / FREE entries]
[INTEL notes excluded — already applied to database]
['No additional coaching this round.' if queue empty]

--- TASK ---
Generate your faction's next message for the diplomatic channel.
Treat analyst divergences as genuinely uncertain.
{JSON output instruction if review gate enabled | plain text instruction if not}
```

## Bare Mode

When `bare_mode=True`, `assemble()` delegates to `_assemble_bare()` and produces a stripped `DecisionContext` suitable for the ablation experiment (Phase 34):

- **system_prompt:** `persona_prompt` only (includes BATNA, scoring table, strategic notes — these are scenario inputs, not harness output)
- **user_prompt:** raw concatenated transcript of all `recent_events` (no limit applied) + minimal task instruction
- **Omitted:** round context, intelligence report, divergences, coaching, recent-events filtering
- **metadata:** includes `bare_mode: True` and `coaching_count: 0`

Bare mode is only reachable via the self-play `--bare-prompt` flag. The production pipeline never passes `bare_mode=True`. Its purpose is ablation: removing the harness layers lets you compare bare-prompt vs full-harness outcomes on identical scenarios.

## Inputs
- All parameters listed above, provided by the Orchestrator from their respective modules

## Outputs
- DecisionContext — consumed by Generation module

## State
None. Pure composition function.

## Usage Example

```python
from modules.context_assembler import DefaultContextAssembler

assembler = DefaultContextAssembler(recent_events_limit=30)

context = await assembler.assemble(
    persona_prompt=base_prompt,
    round_context=round_ctx,
    intelligence=primary_report,
    divergences=divergence_list,
    recent_events=recent_stored_events,
    free_coaching=unconsumed_coaching,
    review_gate_enabled=True,
)

# context.system_prompt and context.user_prompt are ready for Generation
```
