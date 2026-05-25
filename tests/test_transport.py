from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime, timezone

import pytest

from modules.transport import (
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
