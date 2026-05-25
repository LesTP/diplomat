from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class InboundEvent:
    timestamp: datetime
    sender_faction: str
    channel: str
    content: str
    recipient: str | None = None
    telegram_msg_id: int | None = None

    def __post_init__(self) -> None:
        if self.timestamp.tzinfo is None:
            object.__setattr__(
                self, "timestamp", self.timestamp.replace(tzinfo=timezone.utc)
            )


@dataclass(frozen=True)
class EventFilter:
    round_number: int | None = None
    source: str | None = None
    channel: str | None = None
    since: datetime | None = None
    limit: int = 100


@dataclass(frozen=True)
class StoredEvent:
    event_id: str
    round_number: int
    event: InboundEvent


@dataclass(frozen=True)
class StatePatch:
    data: dict[str, Any]


@dataclass(frozen=True)
class PatchSource:
    trigger_type: str
    trigger_ref: str
