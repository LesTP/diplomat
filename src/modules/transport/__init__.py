from __future__ import annotations

import json
import random
from collections.abc import AsyncIterable, Awaitable, Callable, Iterable
from dataclasses import dataclass
from datetime import datetime, timezone
from inspect import isawaitable
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
        faction_map: dict[str, str] | None = None,
        operator_user_ids: Iterable[str | int] | None = None,
        jitter_seconds: tuple[float, float] = (0.05, 0.2),
        sleep: Callable[[float], Awaitable[None]] | None = None,
        random_between: Callable[[float, float], float] | None = None,
        max_send_attempts: int = 3,
        now: Callable[[], datetime] | None = None,
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
        self._private_factions_by_chat = {
            _chat_key(chat_id): faction
            for faction, chat_id in self._private_channel_ids.items()
        }
        self._faction_map = {
            str(user_id): faction for user_id, faction in (faction_map or {}).items()
        }
        self._operator_user_ids = {
            str(user_id) for user_id in (operator_user_ids or set())
        }
        self._jitter_seconds = jitter_seconds
        self._sleep = sleep or _asyncio_sleep
        self._random_between = random_between or random.uniform
        self._max_send_attempts = max_send_attempts
        self._now = now or (lambda: datetime.now(timezone.utc))

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
        try:
            start_polling = getattr(self._client, "start_polling", None)
            if start_polling is not None:
                await _maybe_await(start_polling())

            while True:
                update = await _maybe_await(self._client.get_next_update())
                if update is None:
                    return
                yield self._event_from_update(update)
        except TransportError:
            raise
        except Exception as exc:
            raise TransportError(f"Telegram listen failed: {exc}") from exc

    def _chat_id_for(self, message: OutboundMessage) -> ChatId:
        if message.channel == "public":
            return self._public_channel_id
        if message.channel == "coaching":
            return self._coaching_channel_id
        if message.recipient in self._private_channel_ids:
            return self._private_channel_ids[message.recipient]
        raise TransportError(
            f"No private Telegram chat configured for {message.recipient}"
        )

    def _event_from_update(self, update: object) -> InboundEvent:
        chat_id = _get_value(update, "chat_id", "chat.id")
        chat_key = _chat_key(chat_id)
        channel = self._channel_for_chat(chat_key)
        user_id = _get_value(
            update,
            "user_id",
            "sender_id",
            "from_user_id",
            default=None,
        )
        sender_faction = self._sender_for(channel, chat_key, user_id)

        try:
            return normalize_inbound_event(
                timestamp=_telegram_timestamp(
                    _get_value(update, "timestamp", "date", default=None),
                    self._now,
                ),
                sender_faction=sender_faction,
                channel=channel,
                content=_required_update_str(update, "content", "text", "message"),
                telegram_msg_id=_optional_update_int(
                    update,
                    "telegram_msg_id",
                    "message_id",
                    "id",
                ),
            )
        except ValueError as exc:
            raise TransportError(f"Telegram update is invalid: {exc}") from exc

    def _channel_for_chat(self, chat_key: str) -> str:
        if chat_key == _chat_key(self._public_channel_id):
            return "public"
        if chat_key == _chat_key(self._coaching_channel_id):
            return "coaching"
        if chat_key in self._private_factions_by_chat:
            return "private"
        raise TransportError(f"No Telegram channel configured for chat {chat_key}")

    def _sender_for(
        self,
        channel: str,
        chat_key: str,
        user_id: object,
    ) -> str:
        if user_id is not None:
            user_key = str(user_id)
            if user_key in self._operator_user_ids:
                return "operator"
            if user_key in self._faction_map:
                return self._faction_map[user_key]
        if channel == "coaching":
            return "operator"
        if channel == "private":
            return self._private_factions_by_chat[chat_key]
        return "system"


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


def _chat_key(chat_id: object) -> str:
    if chat_id is None:
        raise TransportError("Telegram update is missing chat_id")
    return str(chat_id)


def _get_value(update: object, *keys: str, default: object = ...):
    for key in keys:
        current = update
        found = True
        for part in key.split("."):
            if isinstance(current, dict) and part in current:
                current = current[part]
            elif hasattr(current, part):
                current = getattr(current, part)
            else:
                found = False
                break
        if found:
            return current
    if default is not ...:
        return default
    raise ValueError(f"Telegram update requires one of: {', '.join(keys)}")


def _required_update_str(update: object, *keys: str) -> str:
    value = _get_value(update, *keys)
    if not isinstance(value, str):
        raise ValueError(f"{keys[0]} must be a string")
    return value


def _optional_update_int(update: object, *keys: str) -> int | None:
    value = _get_value(update, *keys, default=None)
    if value is None:
        return None
    if not isinstance(value, int):
        raise ValueError(f"{keys[0]} must be an integer")
    return value


def _telegram_timestamp(
    value: object,
    now: Callable[[], datetime],
) -> datetime:
    if value is None:
        return now()
    if isinstance(value, datetime):
        return value
    if isinstance(value, int | float):
        return datetime.fromtimestamp(value, tz=timezone.utc)
    return _parse_timestamp(value, now)


async def _maybe_await(value: object):
    if isawaitable(value):
        return await value
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
