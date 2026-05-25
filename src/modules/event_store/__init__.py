from __future__ import annotations

import sqlite3
import uuid
from pathlib import Path

from modules.types import EventFilter, InboundEvent, StoredEvent


class SQLiteEventStore:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _initialize(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS messages (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id        TEXT NOT NULL UNIQUE,
                    round_number    INTEGER NOT NULL,
                    timestamp       TEXT NOT NULL,
                    sender_faction  TEXT NOT NULL,
                    channel         TEXT NOT NULL,
                    recipient       TEXT,
                    content         TEXT NOT NULL,
                    telegram_msg_id INTEGER
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_messages_round_timestamp
                ON messages(round_number, timestamp)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_messages_sender_timestamp
                ON messages(sender_faction, timestamp)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_messages_channel_timestamp
                ON messages(channel, timestamp)
                """
            )

    async def append(self, event: InboundEvent, round_number: int) -> str:
        event_id = str(uuid.uuid4())
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO messages (
                    event_id,
                    round_number,
                    timestamp,
                    sender_faction,
                    channel,
                    recipient,
                    content,
                    telegram_msg_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_id,
                    round_number,
                    event.timestamp.isoformat(),
                    event.sender_faction,
                    event.channel,
                    event.recipient,
                    event.content,
                    event.telegram_msg_id,
                ),
            )
        return event_id

    async def query(self, filters: EventFilter) -> list[StoredEvent]:
        where: list[str] = []
        params: list[object] = []

        if filters.round_number is not None:
            where.append("round_number = ?")
            params.append(filters.round_number)
        if filters.source is not None:
            where.append("sender_faction = ?")
            params.append(filters.source)
        if filters.channel is not None:
            where.append("channel = ?")
            params.append(filters.channel)
        if filters.since is not None:
            where.append("timestamp >= ?")
            params.append(filters.since.isoformat())

        sql = "SELECT * FROM messages"
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY timestamp ASC, id ASC LIMIT ?"
        params.append(max(filters.limit, 0))

        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()

        return [self._row_to_stored_event(row) for row in rows]

    @staticmethod
    def _row_to_stored_event(row: sqlite3.Row) -> StoredEvent:
        return StoredEvent(
            event_id=row["event_id"],
            round_number=row["round_number"],
            event=InboundEvent(
                timestamp=_parse_timestamp(row["timestamp"]),
                sender_faction=row["sender_faction"],
                channel=row["channel"],
                recipient=row["recipient"],
                content=row["content"],
                telegram_msg_id=row["telegram_msg_id"],
            ),
        )


def _parse_timestamp(value: str):
    from datetime import datetime

    return datetime.fromisoformat(value)


__all__ = ["EventFilter", "InboundEvent", "SQLiteEventStore", "StoredEvent"]
