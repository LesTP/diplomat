# ARCH: State Manager

## Purpose
Structured domain state for the game. Owns all domain tables: factions, promises, coalitions, inconsistencies, and supporting tables (intelligence, coaching, adversarial_reads, review_gate_edits, game_state). Every write goes through `apply_patch()`, which validates the patch against the JSON schema and writes an audit entry to `state_change_log` before applying changes. No other module writes to domain tables directly.

## Public API

### get
- **Signature:** `async def get(self, entity_type: str, entity_id: str) -> dict | None`
- **Parameters:**
  - entity_type: str — table name ("faction_state", "promises", "coalitions", etc.)
  - entity_id: str — primary key value
- **Returns:** dict of entity fields, or None if not found
- **Errors:** ValueError if entity_type is unknown

### query
- **Signature:** `async def query(self, entity_type: str, filters: dict) -> list[dict]`
- **Parameters:**
  - entity_type: str — table name
  - filters: dict — column-value pairs for WHERE clause
- **Returns:** list[dict] — matching rows
- **Errors:** ValueError if entity_type is unknown

### apply_patch
- **Signature:** `async def apply_patch(self, patch: StatePatch, source: PatchSource) -> None`
- **Parameters:**
  - patch: StatePatch — data dict validated against config/schemas/state_patch.json
  - source: PatchSource — {trigger_type, trigger_ref} for audit trail
- **Returns:** None
- **Errors:**
  - ValidationError if patch.data fails schema validation
  - sqlite3.OperationalError on database write failure

### get_full_state
- **Signature:** `async def get_full_state(self) -> dict`
- **Parameters:** none
- **Returns:** dict — serialised snapshot of all current entity states (all faction_state rows, all pending promises, all coalitions, all unspent inconsistencies). Format matches what the Analyst prompt expects.
- **Errors:** none

### store_coaching
- **Signature:** `async def store_coaching(self, coaching_id: str, tag: str, content: str, consumed: bool) -> None`
- **Parameters:** coaching_id, tag, content, consumed flag
- **Returns:** None
- **Errors:** sqlite3.OperationalError on database write failure

### store_intelligence
- **Signature:** `async def store_intelligence(self, round_number: int, provider: str, analysis: dict) -> None`
- **Parameters:** round_number, provider id, analysis payload
- **Returns:** None
- **Errors:** sqlite3.OperationalError on database write failure

### set_game_state
- **Signature:** `async def set_game_state(self, key: str, value: str) -> None`
- **Parameters:** key, value
- **Returns:** None
- **Errors:** sqlite3.OperationalError on database write failure

### store_adversarial_read
- **Signature:** `async def store_adversarial_read(self, round_number: int, analysis: dict) -> None`
- **Parameters:** round_number, adversarial analysis payload
- **Returns:** None
- **Errors:** sqlite3.OperationalError on database write failure

### mark_coaching_consumed
- **Signature:** `async def mark_coaching_consumed(self) -> None`
- **Parameters:** none
- **Returns:** None
- **Errors:** sqlite3.OperationalError on database write failure

## Types

```python
@dataclass
class StatePatch:
    data: dict            # validated against schema at apply time

@dataclass
class PatchSource:
    trigger_type: str     # 'message' | 'intel_coaching'
    trigger_ref: str      # event_id or coaching_id
```

## Inputs
- StatePatch objects from Extraction module
- PatchSource metadata from Orchestrator
- Entity queries from Orchestrator, Analyst, and command handlers

## Outputs
- Entity dicts from get/query
- Full state snapshot from get_full_state (consumed by Analyst)
- Audit entries written to state_change_log (consumed by `/edits` and `/state` commands)

## State
Owns the following tables in the shared SQLite database:

- `faction_state` — per-faction profile (goals, credibility, behavioral notes)
- `promises` — promise ledger (from, to, content, status, resolution)
- `coalitions` — pairwise faction relationships (strength, confidence, basis)
- `inconsistencies` — detected contradictions with leverage value and spent flag
- `state_change_log` — audit trail for every patch applied
- `intelligence` — per-round analyst outputs and divergence flags
- `adversarial_reads` — draft analysis records
- `coaching` — operator coaching entries with consumed flag
- `review_gate_edits` — review gate decision log
- `game_state` — key-value pairs (current_round, total_rounds, game_status)

Schema validation uses `config/schemas/state_patch.json` loaded at startup.

## Usage Example

```python
from modules.state_manager import SQLiteStateManager, StatePatch, PatchSource

sm = SQLiteStateManager(db_path="data/game.db", schema_path="config/schemas/state_patch.json")

# Apply a patch from extraction
await sm.apply_patch(
    patch=StatePatch(data={"faction_state": [{"faction_id": "alpha", "credibility_score": 0.7}]}),
    source=PatchSource(trigger_type="message", trigger_ref="evt-123"),
)

# Get full state for Analyst
state = await sm.get_full_state()

# Query promises
pending = await sm.query("promises", {"status": "pending"})

# Get a specific faction
faction = await sm.get("faction_state", "alpha")
```
