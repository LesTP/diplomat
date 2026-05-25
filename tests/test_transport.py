from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime, timezone

from modules.transport import (
    InboundEvent,
    OutboundMessage,
    Transport,
    TransportError,
)


def test_public_exports_include_transport_contract_types():
    import modules.transport as transport

    assert transport.InboundEvent is InboundEvent
    assert transport.OutboundMessage is OutboundMessage
    assert transport.Transport is Transport
    assert transport.TransportError is TransportError


def test_outbound_message_defaults_to_no_recipient():
    message = OutboundMessage(
        content="We propose a non-aggression pact.",
        channel="public",
    )

    assert message.content == "We propose a non-aggression pact."
    assert message.channel == "public"
    assert message.recipient is None


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
