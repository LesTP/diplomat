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
