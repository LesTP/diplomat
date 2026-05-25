from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime, timezone
import json

import pytest

from modules.transport import (
    CLITransport,
    InboundEvent,
    OutboundMessage,
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
