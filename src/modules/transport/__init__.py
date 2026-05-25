from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import AsyncIterator, Protocol, runtime_checkable

from modules.types import InboundEvent


VALID_CHANNELS = frozenset({"public", "private", "coaching"})


@dataclass(frozen=True)
class OutboundMessage:
    content: str
    channel: str
    recipient: str | None = None

    def __post_init__(self) -> None:
        validate_channel(self.channel)
        if self.channel == "private" and not _has_text(self.recipient):
            raise ValueError("Private outbound messages require recipient")
        if self.channel != "private" and self.recipient is not None:
            raise ValueError("Only private outbound messages may set recipient")


class TransportError(RuntimeError):
    pass


@runtime_checkable
class Transport(Protocol):
    async def send(self, message: OutboundMessage) -> None:
        ...

    def listen(self) -> AsyncIterator[InboundEvent]:
        ...


def validate_channel(channel: str) -> None:
    if channel not in VALID_CHANNELS:
        allowed = ", ".join(sorted(VALID_CHANNELS))
        raise ValueError(
            f"Unsupported transport channel: {channel!r}; expected {allowed}"
        )


def normalize_inbound_event(
    *,
    timestamp: datetime,
    sender_faction: str,
    channel: str,
    content: str,
    recipient: str | None = None,
    telegram_msg_id: int | None = None,
) -> InboundEvent:
    validate_channel(channel)
    if not _has_text(sender_faction):
        raise ValueError("Inbound events require sender_faction")
    return InboundEvent(
        timestamp=timestamp,
        sender_faction=sender_faction.strip(),
        channel=channel,
        content=content,
        recipient=recipient,
        telegram_msg_id=telegram_msg_id,
    )


def _has_text(value: str | None) -> bool:
    return isinstance(value, str) and bool(value.strip())


__all__ = [
    "InboundEvent",
    "OutboundMessage",
    "Transport",
    "TransportError",
    "VALID_CHANNELS",
    "normalize_inbound_event",
    "validate_channel",
]
