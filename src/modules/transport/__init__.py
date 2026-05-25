from __future__ import annotations

import json
import random
from collections.abc import AsyncIterable, Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import AsyncIterator, Protocol, runtime_checkable

from modules.types import InboundEvent


VALID_CHANNELS = frozenset({"public", "private", "coaching"})
ChatId = str | int


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


class TelegramBotTransport:
    def __init__(
        self,
        client: object,
        *,
        public_channel_id: ChatId,
        coaching_channel_id: ChatId,
        private_channel_ids: dict[str, ChatId] | None = None,
        jitter_seconds: tuple[float, float] = (0.05, 0.2),
        sleep: Callable[[float], Awaitable[None]] | None = None,
        random_between: Callable[[float, float], float] | None = None,
        max_send_attempts: int = 3,
    ) -> None:
        if max_send_attempts < 1:
            raise ValueError("max_send_attempts must be at least 1")
        min_jitter, max_jitter = jitter_seconds
        if min_jitter < 0 or max_jitter < min_jitter:
            raise ValueError("jitter_seconds must be a non-negative min/max pair")

        self._client = client
        self._public_channel_id = public_channel_id
        self._coaching_channel_id = coaching_channel_id
        self._private_channel_ids = dict(private_channel_ids or {})
        self._jitter_seconds = jitter_seconds
        self._sleep = sleep or _asyncio_sleep
        self._random_between = random_between or random.uniform
        self._max_send_attempts = max_send_attempts

    async def send(self, message: OutboundMessage) -> None:
        chat_id = self._chat_id_for(message)
        last_error: Exception | None = None
        for _attempt in range(self._max_send_attempts):
            try:
                await self._sleep(self._random_between(*self._jitter_seconds))
                await self._client.send_message(chat_id, message.content)
                return
            except Exception as exc:
                last_error = exc

        raise TransportError(f"Telegram send failed: {last_error}") from last_error

    async def listen(self) -> AsyncIterator[InboundEvent]:
        raise TransportError("Telegram listen is not implemented yet")

    def _chat_id_for(self, message: OutboundMessage) -> ChatId:
        if message.channel == "public":
            return self._public_channel_id
        if message.channel == "coaching":
            return self._coaching_channel_id
        if message.recipient in self._private_channel_ids:
            return self._private_channel_ids[message.recipient]
        raise TransportError(f"No private Telegram chat configured for {message.recipient}")


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


async def _asyncio_sleep(delay: float) -> None:
    import asyncio

    await asyncio.sleep(delay)


__all__ = [
    "CLITransport",
    "InboundEvent",
    "OutboundMessage",
    "TelegramBotTransport",
    "Transport",
    "TransportError",
    "VALID_CHANNELS",
    "normalize_inbound_event",
    "validate_channel",
]
