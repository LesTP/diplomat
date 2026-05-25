# ARCH: Transport

## Purpose
Platform I/O. Sends outbound messages and receives inbound events from the game platform. The interface is platform-agnostic; implementations handle platform-specific details. Outgoing messages include configurable delay jitter applied inside the Transport, not in the Orchestrator.

## Public API

### send
- **Signature:** `async def send(self, message: OutboundMessage) -> None`
- **Parameters:**
  - message: OutboundMessage — content, channel, and optional recipient
- **Returns:** None
- **Errors:** TransportError on send failure (after retries)

### listen
- **Signature:** `async def listen(self) -> AsyncIterator[InboundEvent]`
- **Parameters:** none
- **Returns:** AsyncIterator yielding InboundEvent objects as they arrive
- **Errors:** TransportError on persistent connection failure

## Types

```python
@dataclass
class OutboundMessage:
    content: str
    channel: str          # 'public' | 'private' | 'coaching'
    recipient: str | None # faction_id for private, None for public

@dataclass
class InboundEvent:
    timestamp: datetime
    sender_faction: str   # faction_id | 'operator' | 'system'
    channel: str          # 'public' | 'private' | 'coaching'
    content: str
    recipient: str | None = None
    telegram_msg_id: int | None = None
```

`InboundEvent` is the shared project type from `modules.types`, already used by
Event Store. Transport implementations normalize platform metadata into its
stable fields and should keep implementation-specific payloads inside their own
adapter boundary unless a downstream module needs them.

Valid channel values are `public`, `private`, and `coaching`. Shared helpers in
`modules.transport` validate channel names and normalize inbound platform data
into the shared `InboundEvent` type.

## Implementations

**TelegramBotTransport** — wraps `toolkit/telegram_client.TelegramClient` via
dependency injection. Uses `start_polling()` / `get_next_update()` for inbound,
`send_message(chat_id, content)` for outbound. Maps public/coaching channel
names and private recipients to Telegram chat IDs from pipeline.yaml config.
Applies delay jitter (default 50-200ms) before each send attempt and retries
send failures before raising `TransportError`. Inbound updates are normalized
from dict-like or object-like toolkit payloads. Chat IDs determine channel,
configured user IDs map to factions or operator, private chat IDs fall back to
their configured faction, and unmatched public senders are `system`.

**TelethonUserTransport** — wraps `Telethon` library. Required if bot-to-bot messaging is unavailable. Same interface; different platform client.

**CLITransport** — reads JSON lines from an async line source and writes JSON
lines to an async writer. For local testing without a live platform. Inbound
JSON objects use the shared `InboundEvent` field names.

## Inputs
- OutboundMessage objects from Orchestrator (after Review Gate approval)
- Platform credentials and channel IDs from pipeline.yaml

## Outputs
- InboundEvent stream consumed by Orchestrator event loop

## State
- Polling offset (for Telegram, persisted via toolkit/telegram_client.next_update_offset)
- Connection state (in-memory, re-established on restart)

## Usage Example

```python
from modules.transport import TelegramBotTransport, OutboundMessage

transport = TelegramBotTransport(
    bot_token="bot123:ABC...",
    public_channel_id="-100xxx",
    coaching_channel_id="-100yyy",
    faction_map={"user1": "alpha", "user2": "beta"},
)

# Send
await transport.send(OutboundMessage(
    content="We propose a non-aggression pact for rounds 4-6.",
    channel="public",
    recipient=None,
))

# Listen
async for event in transport.listen():
    # event: InboundEvent
    orchestrator.handle(event)
```
