from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime, timezone
import json

import pytest

from modules.transport import (
    CLITransport,
    InboundEvent,
    OutboundMessage,
    TelegramBotTransport,
    Transport,
    TransportError,
    VALID_CHANNELS,
    normalize_inbound_event,
    validate_channel,
)


def test_public_exports_include_transport_contract_types():
    import modules.transport as transport

    assert transport.CLITransport is CLITransport
    assert transport.InboundEvent is InboundEvent
    assert transport.OutboundMessage is OutboundMessage
    assert transport.TelegramBotTransport is TelegramBotTransport
    assert transport.Transport is Transport
    assert transport.TransportError is TransportError
    assert transport.VALID_CHANNELS is VALID_CHANNELS
    assert transport.normalize_inbound_event is normalize_inbound_event
    assert transport.validate_channel is validate_channel


def test_outbound_message_defaults_to_no_recipient():
    message = OutboundMessage(
        content="We propose a non-aggression pact.",
        channel="public",
    )

    assert message.content == "We propose a non-aggression pact."
    assert message.channel == "public"
    assert message.recipient is None


def test_outbound_message_validates_channel_and_recipient_rules():
    assert OutboundMessage(
        content="Private offer",
        channel="private",
        recipient="france",
    ).recipient == "france"

    with pytest.raises(ValueError, match="Unsupported transport channel"):
        OutboundMessage(content="No route", channel="invalid")
    with pytest.raises(ValueError, match="Private outbound messages require recipient"):
        OutboundMessage(content="No recipient", channel="private")
    with pytest.raises(ValueError, match="Only private outbound messages"):
        OutboundMessage(content="Wrong route", channel="public", recipient="france")


def test_transport_protocol_accepts_send_and_listen_implementation():
    class FakeTransport:
        async def send(self, message: OutboundMessage) -> None:
            self.message = message

        async def listen(self) -> AsyncIterator[InboundEvent]:
            yield InboundEvent(
                timestamp=datetime(1901, 1, 1, tzinfo=timezone.utc),
                sender_faction="france",
                channel="private",
                recipient="england",
                content="Support me into Belgium.",
                telegram_msg_id=42,
            )

    fake = FakeTransport()

    assert isinstance(fake, Transport)
    assert isinstance(CLITransport(_reader([]), _writer([])), Transport)
    assert isinstance(_telegram_transport(_FakeTelegramClient()), Transport)


def test_transport_reuses_shared_inbound_event_type():
    event = InboundEvent(
        timestamp=datetime(1901, 1, 1, 12, 0),
        sender_faction="operator",
        channel="coaching",
        content="WATCH: France is stalling.",
    )

    assert event.timestamp.tzinfo is timezone.utc
    assert event.sender_faction == "operator"
    assert event.channel == "coaching"
    assert event.recipient is None


def test_validate_channel_accepts_only_transport_channels():
    assert VALID_CHANNELS == frozenset({"public", "private", "coaching"})
    validate_channel("public")
    validate_channel("private")
    validate_channel("coaching")

    with pytest.raises(ValueError, match="Unsupported transport channel"):
        validate_channel("press")


def test_normalize_inbound_event_validates_and_uses_shared_type():
    event = normalize_inbound_event(
        timestamp=datetime(1901, 1, 1, 12, 0),
        sender_faction=" france ",
        channel="private",
        recipient="england",
        content="Support me into Belgium.",
        telegram_msg_id=42,
    )

    assert event == InboundEvent(
        timestamp=datetime(1901, 1, 1, 12, 0, tzinfo=timezone.utc),
        sender_faction="france",
        channel="private",
        recipient="england",
        content="Support me into Belgium.",
        telegram_msg_id=42,
    )

    with pytest.raises(ValueError, match="Inbound events require sender_faction"):
        normalize_inbound_event(
            timestamp=datetime(1901, 1, 1, 12, 0, tzinfo=timezone.utc),
            sender_faction=" ",
            channel="public",
            content="No source",
        )


@pytest.mark.asyncio
async def test_cli_transport_send_writes_json_line():
    lines: list[str] = []
    transport = CLITransport(_reader([]), _writer(lines))

    await transport.send(
        OutboundMessage(
            content="Support me into Belgium.",
            channel="private",
            recipient="france",
        )
    )

    assert len(lines) == 1
    assert lines[0].endswith("\n")
    assert json.loads(lines[0]) == {
        "content": "Support me into Belgium.",
        "channel": "private",
        "recipient": "france",
    }


@pytest.mark.asyncio
async def test_cli_transport_listen_yields_inbound_events_from_json_lines():
    transport = CLITransport(
        _reader(
            [
                "\n",
                json.dumps(
                    {
                        "timestamp": "1901-01-01T12:00:00+00:00",
                        "sender_faction": "france",
                        "channel": "private",
                        "recipient": "england",
                        "content": "Support me into Belgium.",
                        "telegram_msg_id": 42,
                    }
                ),
            ]
        ),
        _writer([]),
    )

    events = [event async for event in transport.listen()]

    assert events == [
        InboundEvent(
            timestamp=datetime(1901, 1, 1, 12, 0, tzinfo=timezone.utc),
            sender_faction="france",
            channel="private",
            recipient="england",
            content="Support me into Belgium.",
            telegram_msg_id=42,
        )
    ]


@pytest.mark.asyncio
async def test_cli_transport_listen_uses_clock_when_timestamp_is_absent():
    now = datetime(1901, 1, 1, 12, 0, tzinfo=timezone.utc)
    transport = CLITransport(
        _reader(
            [
                json.dumps(
                    {
                        "sender_faction": "operator",
                        "channel": "coaching",
                        "content": "WATCH: France is stalling.",
                    }
                )
            ]
        ),
        _writer([]),
        now=lambda: now,
    )

    events = [event async for event in transport.listen()]

    assert events == [
        InboundEvent(
            timestamp=now,
            sender_faction="operator",
            channel="coaching",
            content="WATCH: France is stalling.",
        )
    ]


@pytest.mark.asyncio
async def test_cli_transport_listen_stops_on_reader_eof():
    transport = CLITransport(_reader([]), _writer([]))

    assert [event async for event in transport.listen()] == []


@pytest.mark.asyncio
async def test_cli_transport_wraps_writer_and_reader_errors():
    async def broken_writer(line: str) -> None:
        raise OSError("pipe closed")

    async def broken_reader() -> AsyncIterator[str]:
        raise OSError("input closed")
        yield ""

    with pytest.raises(TransportError, match="CLI send failed"):
        await CLITransport(_reader([]), broken_writer).send(
            OutboundMessage(content="Hello", channel="public")
        )

    with pytest.raises(TransportError, match="CLI listen failed"):
        [event async for event in CLITransport(broken_reader(), _writer([])).listen()]


@pytest.mark.asyncio
async def test_cli_transport_rejects_malformed_inbound_lines():
    invalid_payloads = [
        "not-json",
        json.dumps(["not", "object"]),
        json.dumps({"sender_faction": "france", "channel": "public"}),
        json.dumps(
            {
                "sender_faction": "france",
                "channel": "press",
                "content": "Wrong channel",
            }
        ),
    ]

    for payload in invalid_payloads:
        transport = CLITransport(_reader([payload]), _writer([]))
        with pytest.raises(TransportError, match="CLI inbound line"):
            [event async for event in transport.listen()]


async def _reader(lines: list[str]) -> AsyncIterator[str]:
    for line in lines:
        yield line


def _writer(lines: list[str]):
    async def write(line: str) -> None:
        lines.append(line)

    return write


@pytest.mark.asyncio
async def test_telegram_transport_send_routes_public_private_and_coaching_messages():
    client = _FakeTelegramClient()
    sleeps: list[float] = []
    transport = _telegram_transport(client, sleeps=sleeps)

    await transport.send(OutboundMessage(content="Public offer", channel="public"))
    await transport.send(
        OutboundMessage(
            content="Private offer",
            channel="private",
            recipient="france",
        )
    )
    await transport.send(OutboundMessage(content="Operator note", channel="coaching"))

    assert client.sent == [
        ("public-chat", "Public offer"),
        ("france-chat", "Private offer"),
        ("coaching-chat", "Operator note"),
    ]
    assert sleeps == [0.1, 0.1, 0.1]


@pytest.mark.asyncio
async def test_telegram_transport_retries_failed_sends():
    client = _FakeTelegramClient(failures_before_success=2)
    sleeps: list[float] = []
    transport = _telegram_transport(client, sleeps=sleeps)

    await transport.send(OutboundMessage(content="Retry me", channel="public"))

    assert client.sent == [("public-chat", "Retry me")]
    assert client.attempts == [
        ("public-chat", "Retry me"),
        ("public-chat", "Retry me"),
        ("public-chat", "Retry me"),
    ]
    assert sleeps == [0.1, 0.1, 0.1]


@pytest.mark.asyncio
async def test_telegram_transport_raises_transport_error_for_send_failures():
    client = _FakeTelegramClient(failures_before_success=3)
    transport = _telegram_transport(client, max_send_attempts=2)

    with pytest.raises(TransportError, match="Telegram send failed"):
        await transport.send(OutboundMessage(content="Fail me", channel="public"))


@pytest.mark.asyncio
async def test_telegram_transport_rejects_unconfigured_private_recipient():
    client = _FakeTelegramClient()
    transport = _telegram_transport(client)

    with pytest.raises(TransportError, match="No private Telegram chat configured"):
        await transport.send(
            OutboundMessage(
                content="No route",
                channel="private",
                recipient="italy",
            )
        )

    assert client.attempts == []


def test_telegram_transport_validates_send_configuration():
    with pytest.raises(ValueError, match="max_send_attempts"):
        _telegram_transport(_FakeTelegramClient(), max_send_attempts=0)
    with pytest.raises(ValueError, match="jitter_seconds"):
        _telegram_transport(_FakeTelegramClient(), jitter_seconds=(0.2, 0.1))


def _telegram_transport(
    client: "_FakeTelegramClient",
    *,
    sleeps: list[float] | None = None,
    max_send_attempts: int = 3,
    jitter_seconds: tuple[float, float] = (0.05, 0.2),
) -> TelegramBotTransport:
    sleeps = sleeps if sleeps is not None else []

    async def sleep(delay: float) -> None:
        sleeps.append(delay)

    return TelegramBotTransport(
        client,
        public_channel_id="public-chat",
        coaching_channel_id="coaching-chat",
        private_channel_ids={"france": "france-chat"},
        faction_map={"100": "england", "200": "france"},
        operator_user_ids={"900"},
        jitter_seconds=jitter_seconds,
        sleep=sleep,
        random_between=lambda _minimum, _maximum: 0.1,
        max_send_attempts=max_send_attempts,
        now=lambda: datetime(1901, 1, 1, 12, 0, tzinfo=timezone.utc),
    )


class _FakeTelegramClient:
    def __init__(
        self,
        failures_before_success: int = 0,
        updates: list[object] | None = None,
    ) -> None:
        self.failures_before_success = failures_before_success
        self.updates = list(updates or [])
        self.attempts: list[tuple[str, str]] = []
        self.sent: list[tuple[str, str]] = []
        self.polling_started = False

    async def send_message(self, chat_id: str, content: str) -> None:
        self.attempts.append((chat_id, content))
        if len(self.attempts) <= self.failures_before_success:
            raise OSError("telegram unavailable")
        self.sent.append((chat_id, content))

    async def start_polling(self) -> None:
        self.polling_started = True

    async def get_next_update(self):
        if self.updates:
            return self.updates.pop(0)
        return None


@pytest.mark.asyncio
async def test_telegram_transport_listen_normalizes_public_private_and_coaching_updates():
    client = _FakeTelegramClient(
        updates=[
            {
                "chat_id": "public-chat",
                "user_id": "100",
                "timestamp": "1901-01-01T12:00:00+00:00",
                "text": "Public press",
                "message_id": 1,
            },
            {
                "chat": {"id": "france-chat"},
                "sender_id": "200",
                "date": datetime(1901, 1, 1, 12, 5, tzinfo=timezone.utc),
                "content": "Private press",
                "telegram_msg_id": 2,
            },
            {
                "chat_id": "coaching-chat",
                "from_user_id": "900",
                "timestamp": 978350700,
                "message": "WATCH: France is stalling.",
                "id": 3,
            },
        ]
    )
    transport = _telegram_transport(client)

    events = [event async for event in transport.listen()]

    assert client.polling_started is True
    assert events == [
        InboundEvent(
            timestamp=datetime(1901, 1, 1, 12, 0, tzinfo=timezone.utc),
            sender_faction="england",
            channel="public",
            content="Public press",
            telegram_msg_id=1,
        ),
        InboundEvent(
            timestamp=datetime(1901, 1, 1, 12, 5, tzinfo=timezone.utc),
            sender_faction="france",
            channel="private",
            content="Private press",
            telegram_msg_id=2,
        ),
        InboundEvent(
            timestamp=datetime(2001, 1, 1, 12, 5, tzinfo=timezone.utc),
            sender_faction="operator",
            channel="coaching",
            content="WATCH: France is stalling.",
            telegram_msg_id=3,
        ),
    ]


@pytest.mark.asyncio
async def test_telegram_transport_listen_uses_fallback_sources_and_clock():
    client = _FakeTelegramClient(
        updates=[
            {
                "chat_id": "public-chat",
                "text": "System message",
            },
            {
                "chat_id": "france-chat",
                "text": "Private fallback",
            },
            {
                "chat_id": "coaching-chat",
                "text": "Operator fallback",
            },
        ]
    )
    transport = _telegram_transport(client)

    events = [event async for event in transport.listen()]

    assert [event.sender_faction for event in events] == [
        "system",
        "france",
        "operator",
    ]
    assert [event.timestamp for event in events] == [
        datetime(1901, 1, 1, 12, 0, tzinfo=timezone.utc),
        datetime(1901, 1, 1, 12, 0, tzinfo=timezone.utc),
        datetime(1901, 1, 1, 12, 0, tzinfo=timezone.utc),
    ]


@pytest.mark.asyncio
async def test_telegram_transport_listen_wraps_polling_and_update_errors():
    class BrokenPollingClient(_FakeTelegramClient):
        async def start_polling(self) -> None:
            raise OSError("polling failed")

    with pytest.raises(TransportError, match="Telegram listen failed"):
        [event async for event in _telegram_transport(BrokenPollingClient()).listen()]

    unknown_chat = _FakeTelegramClient(
        updates=[
            {
                "chat_id": "unknown-chat",
                "text": "No route",
            }
        ]
    )
    with pytest.raises(TransportError, match="No Telegram channel configured"):
        [event async for event in _telegram_transport(unknown_chat).listen()]

    malformed = _FakeTelegramClient(
        updates=[
            {
                "chat_id": "public-chat",
                "text": 123,
            }
        ]
    )
    with pytest.raises(TransportError, match="Telegram update is invalid"):
        [event async for event in _telegram_transport(malformed).listen()]
