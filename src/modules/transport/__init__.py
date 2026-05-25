from __future__ import annotations

import json
from collections.abc import AsyncIterable, Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timezone
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


class CLITransport:
    def __init__(
        self,
        reader: AsyncIterable[str],
        writer: Callable[[str], Awaitable[None]],
        *,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._reader = reader
        self._writer = writer
        self._now = now or (lambda: datetime.now(timezone.utc))

    async def send(self, message: OutboundMessage) -> None:
        payload = {
            "content": message.content,
            "channel": message.channel,
            "recipient": message.recipient,
        }
        try:
            await self._writer(json.dumps(payload, sort_keys=True) + "\n")
        except Exception as exc:
            raise TransportError(f"CLI send failed: {exc}") from exc

    async def listen(self) -> AsyncIterator[InboundEvent]:
        try:
            async for line in self._reader:
                if not line.strip():
                    continue
                yield self._parse_line(line)
        except TransportError:
            raise
        except Exception as exc:
            raise TransportError(f"CLI listen failed: {exc}") from exc

    def _parse_line(self, line: str) -> InboundEvent:
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            raise TransportError(f"CLI inbound line is not valid JSON: {exc}") from exc

        if not isinstance(payload, dict):
            raise TransportError("CLI inbound line must be a JSON object")

        try:
            timestamp = _parse_timestamp(payload.get("timestamp"), self._now)
            return normalize_inbound_event(
                timestamp=timestamp,
                sender_faction=_required_str(payload, "sender_faction"),
                channel=_required_str(payload, "channel"),
                content=_required_str(payload, "content"),
                recipient=_optional_str(payload, "recipient"),
                telegram_msg_id=_optional_int(payload, "telegram_msg_id"),
            )
        except ValueError as exc:
            raise TransportError(f"CLI inbound line is invalid: {exc}") from exc


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


def _parse_timestamp(
    value: object,
    now: Callable[[], datetime],
) -> datetime:
    if value is None:
        return now()
    if not isinstance(value, str):
        raise ValueError("timestamp must be an ISO datetime string")
    try:
        return datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("timestamp must be an ISO datetime string") from exc


def _required_str(payload: dict[object, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str):
        raise ValueError(f"{key} must be a string")
    return value


def _optional_str(payload: dict[object, object], key: str) -> str | None:
    value = payload.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{key} must be a string")
    return value


def _optional_int(payload: dict[object, object], key: str) -> int | None:
    value = payload.get(key)
    if value is None:
        return None
    if not isinstance(value, int):
        raise ValueError(f"{key} must be an integer")
    return value


__all__ = [
    "CLITransport",
    "InboundEvent",
    "OutboundMessage",
    "Transport",
    "TransportError",
    "VALID_CHANNELS",
    "normalize_inbound_event",
    "validate_channel",
]
