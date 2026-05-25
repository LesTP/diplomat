from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

import pytest

from modules.event_store import EventFilter, SQLiteEventStore
from modules.types import InboundEvent


def event(
    sender: str,
    channel: str,
    content: str,
    timestamp: datetime,
    recipient: str | None = None,
    telegram_msg_id: int | None = None,
) -> InboundEvent:
    return InboundEvent(
        timestamp=timestamp,
        sender_faction=sender,
        channel=channel,
        recipient=recipient,
        content=content,
        telegram_msg_id=telegram_msg_id,
    )


@pytest.mark.asyncio
async def test_append_persists_event_and_enables_wal(tmp_path):
    db_path = tmp_path / "game.db"
    store = SQLiteEventStore(db_path)
    inbound = event(
        sender="england",
        channel="press",
        recipient="france",
        content="Support me into Belgium.",
        timestamp=datetime(1901, 1, 1, 12, 0, tzinfo=timezone.utc),
        telegram_msg_id=42,
    )

    event_id = await store.append(inbound, round_number=1)
    results = await store.query(EventFilter())

    assert len(results) == 1
    assert results[0].event_id == event_id
    assert results[0].round_number == 1
    assert results[0].event == inbound

    with sqlite3.connect(db_path) as conn:
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
    assert mode == "wal"


@pytest.mark.asyncio
async def test_query_filters_by_round_source_channel_and_since(tmp_path):
    store = SQLiteEventStore(tmp_path / "game.db")
    first = event(
        "england",
        "press",
        "First",
        datetime(1901, 1, 1, 12, 0, tzinfo=timezone.utc),
    )
    second = event(
        "france",
        "press",
        "Second",
        datetime(1901, 1, 1, 12, 5, tzinfo=timezone.utc),
    )
    third = event(
        "england",
        "operator",
        "Third",
        datetime(1901, 1, 1, 12, 10, tzinfo=timezone.utc),
    )

    await store.append(first, round_number=1)
    await store.append(second, round_number=1)
    await store.append(third, round_number=2)

    results = await store.query(
        EventFilter(
            round_number=2,
            source="england",
            channel="operator",
            since=datetime(1901, 1, 1, 12, 6, tzinfo=timezone.utc),
        )
    )

    assert [stored.event.content for stored in results] == ["Third"]


@pytest.mark.asyncio
async def test_query_orders_by_timestamp_and_applies_limit(tmp_path):
    store = SQLiteEventStore(tmp_path / "game.db")
    late = event(
        "england",
        "press",
        "Late",
        datetime(1901, 1, 1, 12, 10, tzinfo=timezone.utc),
    )
    early = event(
        "france",
        "press",
        "Early",
        datetime(1901, 1, 1, 12, 0, tzinfo=timezone.utc),
    )

    await store.append(late, round_number=1)
    await store.append(early, round_number=1)

    results = await store.query(EventFilter(limit=1))

    assert [stored.event.content for stored in results] == ["Early"]


@pytest.mark.asyncio
async def test_query_returns_empty_list_for_no_matches_and_zero_limit(tmp_path):
    store = SQLiteEventStore(tmp_path / "game.db")
    await store.append(
        event(
            "england",
            "press",
            "Message",
            datetime(1901, 1, 1, 12, 0, tzinfo=timezone.utc),
        ),
        round_number=1,
    )

    assert await store.query(EventFilter(source="italy")) == []
    assert await store.query(EventFilter(limit=0)) == []
