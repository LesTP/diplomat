# ARCH: Coaching

## Purpose
Parse and route operator input. Operator messages arrive as free text with optional tag prefixes (PRIORITY:, CONSTRAINT:, INTEL:, etc.) or slash commands (/preview, /approve, /status, etc.). The parser classifies each input and returns either a CoachingEvent (routed to the coaching queue or state updater) or a Command (dispatched by the Orchestrator). Routing rules are loaded from `config/coaching_routes.yaml` — no routing logic is hardcoded.

## Public API

### parse
- **Signature:** `def parse(self, raw_input: str) -> CoachingEvent | Command`
- **Parameters:**
  - raw_input: str — the operator's message text
- **Returns:** CoachingEvent or Command
- **Errors:** none — unrecognised input returns CoachingEvent with coaching_type='FREE'

## Types

```python
@dataclass
class CoachingEvent:
    coaching_type: str    # 'PRIORITY' | 'CONSTRAINT' | 'INTEL' | 'TONE' | 'WATCH' | 'FREE'
    content: str          # the text after the tag prefix (or full text if untagged)
    route: str            # 'state_updater' | 'coaching_queue'

@dataclass
class Command:
    name: str             # 'preview' | 'approve' | 'edit' | 'block' | 'status' | etc.
    args: dict            # parsed arguments (e.g., edit text for /edit: ...)
```

## Configuration

`config/coaching_routes.yaml`:

```yaml
tags:
  PRIORITY:
    route: coaching_queue
    coaching_type: PRIORITY
  CONSTRAINT:
    route: coaching_queue
    coaching_type: CONSTRAINT
  INTEL:
    route: state_updater
    coaching_type: INTEL
  TONE:
    route: coaching_queue
    coaching_type: TONE
  WATCH:
    route: coaching_queue
    coaching_type: WATCH
  default:
    route: coaching_queue
    coaching_type: FREE

commands:
  - /preview
  - /approve
  - /edit
  - /block
  - /status
  - /state
  - /ledger
  - /intel
  - /divergences
  - /edits
```

## Inputs
- Raw operator message text (str)
- Routing rules from config/coaching_routes.yaml (loaded at startup)

## Outputs
- CoachingEvent — consumed by Orchestrator:
  - route='state_updater' → forwarded to Extraction with trigger_type='intel_correction'
  - route='coaching_queue' → stored in coaching table, consumed by next Generation call
- Command — dispatched by Orchestrator to the appropriate command handler

## State
None. Pure parsing function. Routing rules loaded once at startup from config file.

## Usage Example

```python
from modules.coaching import TaggedCoachingParser

parser = TaggedCoachingParser(routes_path="config/coaching_routes.yaml")

# Tagged coaching
result = parser.parse("PRIORITY: Secure alliance with Beta before round 5")
# → CoachingEvent(coaching_type='PRIORITY', content='Secure alliance...', route='coaching_queue')

# INTEL coaching (routes to state updater)
result = parser.parse("INTEL: Alpha broke promise to Gamma in round 3")
# → CoachingEvent(coaching_type='INTEL', content='Alpha broke...', route='state_updater')

# Command
result = parser.parse("/preview")
# → Command(name='preview', args={})

# Edit command with args
result = parser.parse("/edit: Soften the tone in the second paragraph")
# → Command(name='edit', args={'text': 'Soften the tone...'})

# Untagged (free coaching)
result = parser.parse("Be careful with Delta, their coach seems aggressive")
# → CoachingEvent(coaching_type='FREE', content='Be careful...', route='coaching_queue')
```

## Philosophy & Operational Notes

> Originally diplomat-system-spec.md §7. Migrated here 2026-06-02 when the spec was retired.

### Philosophy

Coaching is an **intervention, not a feed.** Frequent low-signal coaching
creates noise in the Context Assembler's input and makes agent behavior
erratic. The goal is sparse, high-signal input that steers without replacing
the agent's judgment.

The agent executes negotiation, promise tracking, and faction heuristics.
Coaching addresses what only the operator can see: the behavior of human
coaches behind opposing agents, judgment calls outside the faction prompt's
scope, and systematic biases in the configured heuristics.

Coaching should **decrease over the game** as the faction prompt improves
from review gate feedback. Heavy coaching in final rounds indicates a prompt
that needs updating, not a coaching cadence that needs increasing.

### Cadence

Typical round:
- *Pre-round:* one `PRIORITY`, one `CONSTRAINT` if a trap is visible
- *Mid-round:* zero to one targeted correction
- *Pre-response:* approve, edit, or block via the review gate

More than two or three inputs per round signals that either the faction
prompt needs tightening or the operator is playing the game rather than
coaching an agent.

### Review Gate Edit Log → Prompt Refinement

Every review gate decision is written to `review_gate_edits`. At each round
boundary, `/edits` returns this log. Recurring edit patterns — consistently
softening tone, consistently removing a specific type of commitment —
should be written into `config/faction_prompt.txt` directly. The coaching
note correcting for a recurring pattern should eventually become unnecessary.

**Target state:** by mid-game, the review gate is mostly approving without edit.

### What Coaching Does NOT Affect

- Messages already posted (the event log is append-only — there is no recall)
- Analyst outputs already written for the current round (regenerate only on the next round boundary)
- INTEL corrections do **not** backfill past intelligence records — they update state forward from the point of correction, and the next Analyst run will reflect them

This forward-only behavior is intentional: it keeps the audit trail clean
and prevents the operator from rewriting history mid-game.
