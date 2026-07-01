# ARCH: Event Store

## Purpose
Append-only raw event log. Every inbound message (game messages, operator coaching, system signals) is stored with its round number before any processing. Provides query access for the Context Assembler (recent transcript) and for operator commands (`/status`, `/ledger`). Owns the `messages` table. No other module writes to this table.

## Public API

### append
- **Signature:** `async def append(self, event: InboundEvent, round_number: int) -> str`
- **Parameters:**
  - event: InboundEvent — the raw event from Transport
  - round_number: int — current round (from Orchestrator)
- **Returns:** str — the generated event_id (UUID)
- **Errors:** sqlite3.OperationalError if database write fails

### query
- **Signature:** `async def query(self, filters: EventFilter) -> list[StoredEvent]`
- **Parameters:**
  - filters: EventFilter — optional filters (round_number, source, channel, since, limit)
- **Returns:** list[StoredEvent] — matching events, ordered by timestamp ascending
- **Errors:** none — returns empty list on no match

## Types

```python
@dataclass
class EventFilter:
    round_number: int | None = None
    source: str | None = None
    channel: str | None = None
    since: datetime | None = None
    limit: int = 100

@dataclass
class StoredEvent:
    event_id: str
    round_number: int
    event: InboundEvent
```

## Inputs
- InboundEvent objects from Transport (via Orchestrator)
- Round number from Orchestrator

## Outputs
- event_id (str) on append
- list[StoredEvent] on query — used by Context Assembler for recent transcript
- per-agent `event_log` in the self-play result JSON — `collect_results()` dumps `query()` output for replay/audit (see §"Phase 50")

## State
Owns the `messages` table in the shared SQLite database:

```sql
CREATE TABLE messages (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id        TEXT NOT NULL UNIQUE,
    round_number    INTEGER NOT NULL,
    timestamp       TEXT NOT NULL,
    sender_faction  TEXT NOT NULL,
    channel         TEXT NOT NULL,
    recipient       TEXT,
    content         TEXT NOT NULL,
    telegram_msg_id INTEGER
);
```

WAL mode enabled on first connection. All queries parameterised.

## Usage Example

```python
from modules.event_store import SQLiteEventStore, EventFilter

store = SQLiteEventStore(db_path="data/game.db")

# Append
event_id = await store.append(inbound_event, round_number=3)

# Query recent events for Context Assembler
recent = await store.query(EventFilter(limit=30))

# Query by round
round_events = await store.query(EventFilter(round_number=3))

# Query by source
operator_msgs = await store.query(EventFilter(source="operator"))
```

---

## Phase 50 — Result-persistence of the raw event log (complete)

> Phase 50 is complete. `collect_results()` in `tests/self_play/game_environment.py`
> now queries each agent's event store and persists `event_log` into the result JSON.
> Regime was: **Build** (AI-evaluable). Small: one function + its tests. Additive only.

**Intent.** Persist each faction's authoritative raw event log into the self-play
result JSON so a game is fully replayable/auditable from the durable results alone.

**Why.** In self-play each faction's `SQLiteEventStore` lives in a per-faction temp
`.db` (`tmp_dir/{faction_id}.db`) that is **discarded** when the run's
`TemporaryDirectory` is torn down. `collect_results()`
(`tests/self_play/game_environment.py`) persists the transcript from the in-memory
`channel_log` and **never queries `event_store`**, so the append-only raw message
log — the audit-trail substrate — is lost from the durable `results/*.json`. This
also underpins the product "audit trail" claim (`OFFERING.md` §1).

**Scope (additive only).**
- In `collect_results()`, for each agent, query its event store —
  `event_store.query(EventFilter(limit=<full game>))` — **before** the
  `TemporaryDirectory` is torn down, and add the serialized events to that agent's
  result block under a new `event_log` key.
- Serialize each `StoredEvent` to a JSON-safe dict:
  `{event_id, round_number, timestamp, sender_faction, channel, recipient,
  content, telegram_msg_id}`. Query order is timestamp-ascending — preserve it.
- **Do not** change scoring, the `transcript` / `channel_log`, or any existing
  result field. `event_log` is purely additive.
- Works in both full and bare mode: bare overrides Extraction/Analyst/etc., but the
  event store is still a required module and still appends every message.

**Contract change.** Each per-agent result block gains:
`event_log: [ {event_id, round_number, timestamp, sender_faction, channel,
recipient, content, telegram_msg_id}, … ]`. (Reflected in Outputs above; propagate
to `ARCHITECTURE.md` Data Flow if a Contract-Change scan flags it.)

**Acceptance criteria (tests-first — specify before implementing).**
1. After a short fake-backed self-play game, each agent's result block contains a
   non-empty `event_log` whose entries match the messages appended to that agent's
   event store (round numbers present; content matches the broadcast messages).
2. **Additivity:** all pre-existing result fields (`transcript`, `scores`,
   `promises`, …) are unchanged and the existing self-play tests still pass.
3. **Edge:** a faction that received no messages yields `event_log: []` (present,
   empty) — not a missing key, not an error.
4. **Ordering:** `event_log` is timestamp-ascending.

**Out of scope.** No changes to the temp-`.db` lifecycle beyond reading before
teardown; no continuous-value/scoring changes; no schema changes to the `messages`
table.

**Gotcha.** `collect_results()` must query `event_store` **before** the run's
`TemporaryDirectory` is cleaned up (the per-faction `.db`s live inside it).
