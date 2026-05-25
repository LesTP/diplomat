from __future__ import annotations

from dataclasses import dataclass
from typing import AsyncIterator, Protocol, runtime_checkable

from modules.types import InboundEvent


@dataclass(frozen=True)
class OutboundMessage:
    content: str
    channel: str
    recipient: str | None = None


class TransportError(RuntimeError):
    pass


@runtime_checkable
class Transport(Protocol):
    async def send(self, message: OutboundMessage) -> None:
        ...

    def listen(self) -> AsyncIterator[InboundEvent]:
        ...


__all__ = [
    "InboundEvent",
    "OutboundMessage",
    "Transport",
    "TransportError",
]
