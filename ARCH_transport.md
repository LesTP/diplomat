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
    source: str           # faction_id | 'operator' | 'system'
    channel: str          # 'public' | 'private' | 'coaching'
    content: str
    timestamp: datetime
    metadata: dict        # platform-specific, opaque to other modules
```

## Implementations

**TelegramBotTransport** — wraps `toolkit/telegram_client.TelegramClient`. Uses `start_polling()` / `get_next_update()` for inbound, `send_message()` for outbound. Maps channel names to Telegram chat IDs from pipeline.yaml config. Applies delay jitter (default 50-200ms) before each send.

**TelethonUserTransport** — wraps `Telethon` library. Required if bot-to-bot messaging is unavailable. Same interface; different platform client.

**CLITransport** — reads from stdin, writes to stdout. For local testing without a live platform.

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
