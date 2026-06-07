from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from modules.types import PatchSource, StatePatch


class SQLiteStateManager:
    _PRIMARY_KEYS = {
        "faction_state": "faction_id",
        "promises": "promise_id",
        "coalitions": "coalition_id",
        "inconsistencies": "inconsistency_id",
        "state_change_log": "id",
        "intelligence": "id",
        "adversarial_reads": "id",
        "coaching": "coaching_id",
        "review_gate_edits": "id",
        "game_state": "key",
    }
    _COLUMNS = {
        "faction_state": {
            "faction_id",
            "goals",
            "credibility_score",
            "behavioral_notes",
            "updated_at",
        },
        "promises": {
            "promise_id",
            "from_faction",
            "to_faction",
            "content",
            "status",
            "resolution",
            "updated_at",
        },
        "coalitions": {
            "coalition_id",
            "faction_a",
            "faction_b",
            "strength",
            "confidence",
            "basis",
            "updated_at",
        },
        "inconsistencies": {
            "inconsistency_id",
            "faction_id",
            "description",
            "leverage_value",
            "spent",
            "updated_at",
        },
        "state_change_log": {
            "id",
            "changed_at",
            "trigger_type",
            "trigger_ref",
            "patch_json",
        },
        "intelligence": {"id", "round_number", "provider", "analysis_json", "created_at"},
        "adversarial_reads": {"id", "round_number", "analysis_json", "created_at"},
        "coaching": {"coaching_id", "tag", "content", "consumed", "created_at"},
        "review_gate_edits": {
            "id",
            "event_id",
            "decision",
            "edit_text",
            "revise_directives",
            "created_at",
        },
        "game_state": {"key", "value"},
    }

    def __init__(self, db_path: str | Path, schema_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.schema_path = Path(schema_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.validator = Draft202012Validator(
            json.loads(self.schema_path.read_text(encoding="utf-8"))
        )
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _initialize(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS faction_state (
                    faction_id        TEXT PRIMARY KEY,
                    goals             TEXT NOT NULL DEFAULT '[]',
                    credibility_score REAL,
                    behavioral_notes  TEXT NOT NULL DEFAULT '[]',
                    updated_at        TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS promises (
                    promise_id   TEXT PRIMARY KEY,
                    from_faction TEXT NOT NULL,
                    to_faction   TEXT NOT NULL,
                    content      TEXT NOT NULL,
                    status       TEXT NOT NULL DEFAULT 'pending',
                    resolution   TEXT,
                    updated_at   TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS coalitions (
                    coalition_id TEXT PRIMARY KEY,
                    faction_a    TEXT NOT NULL,
                    faction_b    TEXT NOT NULL,
                    strength     REAL,
                    confidence   REAL,
                    basis        TEXT,
                    updated_at   TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS inconsistencies (
                    inconsistency_id TEXT PRIMARY KEY,
                    faction_id       TEXT NOT NULL,
                    description      TEXT NOT NULL,
                    leverage_value   REAL,
                    spent            INTEGER NOT NULL DEFAULT 0,
                    updated_at       TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS state_change_log (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    changed_at   TEXT NOT NULL,
                    trigger_type TEXT NOT NULL,
                    trigger_ref  TEXT NOT NULL,
                    patch_json   TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS intelligence (
                    id            INTEGER PRIMARY KEY AUTOINCREMENT,
                    round_number  INTEGER NOT NULL,
                    provider      TEXT NOT NULL,
                    analysis_json TEXT NOT NULL,
                    created_at    TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS adversarial_reads (
                    id            INTEGER PRIMARY KEY AUTOINCREMENT,
                    round_number  INTEGER NOT NULL,
                    analysis_json TEXT NOT NULL,
                    created_at    TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS coaching (
                    coaching_id TEXT PRIMARY KEY,
                    tag         TEXT NOT NULL,
                    content     TEXT NOT NULL,
                    consumed    INTEGER NOT NULL DEFAULT 0,
                    created_at  TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS review_gate_edits (
                    id        INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id  TEXT NOT NULL,
                    decision  TEXT NOT NULL,
                    edit_text TEXT,
                    revise_directives TEXT,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS game_state (
                    key   TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                """
            )
            self._migrate_review_gate_edits(conn)

    async def get(self, entity_type: str, entity_id: str) -> dict[str, Any] | None:
        table = self._table(entity_type)
        primary_key = self._PRIMARY_KEYS[table]
        with self._connect() as conn:
            row = conn.execute(
                f"SELECT * FROM {table} WHERE {primary_key} = ?", (entity_id,)
            ).fetchone()
        return self._serialize_row(table, row) if row else None

    async def query(
        self, entity_type: str, filters: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        table = self._table(entity_type)
        filters = filters or {}
        where: list[str] = []
        params: list[Any] = []
        for column, value in filters.items():
            self._column(table, column)
            where.append(f"{column} = ?")
            params.append(self._to_db_value(column, value))

        sql = f"SELECT * FROM {table}"
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += f" ORDER BY {self._PRIMARY_KEYS[table]} ASC"

        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [self._serialize_row(table, row) for row in rows]

    async def apply_patch(self, patch: StatePatch, source: PatchSource) -> None:
        self.validator.validate(patch.data)
        changed_at = self._now()
        with self._connect() as conn:
            conn.execute("BEGIN")
            conn.execute(
                """
                INSERT INTO state_change_log (
                    changed_at,
                    trigger_type,
                    trigger_ref,
                    patch_json
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    changed_at,
                    source.trigger_type,
                    source.trigger_ref,
                    json.dumps(patch.data, sort_keys=True),
                ),
            )
            for item in patch.data.get("faction_state", []):
                self._upsert_faction_state(conn, item, changed_at)
            for item in patch.data.get("promises", []):
                self._upsert_promise(conn, item, changed_at)
            for item in patch.data.get("coalitions", []):
                self._upsert_coalition(conn, item, changed_at)
            for item in patch.data.get("inconsistencies", []):
                self._upsert_inconsistency(conn, item, changed_at)
            conn.commit()

    async def get_full_state(self) -> dict[str, list[dict[str, Any]]]:
        return {
            "faction_state": await self.query("faction_state", {}),
            "promises": await self.query("promises", {"status": "pending"}),
            "coalitions": await self.query("coalitions", {}),
            "inconsistencies": await self.query("inconsistencies", {"spent": False}),
        }

    async def store_coaching(
        self, coaching_id: str, tag: str, content: str, consumed: bool
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO coaching (coaching_id, tag, content, consumed, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (coaching_id, tag, content, int(consumed), self._now()),
            )

    async def store_intelligence(
        self, round_number: int, provider: str, analysis: dict[str, Any]
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO intelligence (
                    round_number,
                    provider,
                    analysis_json,
                    created_at
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    round_number,
                    provider,
                    json.dumps(analysis, sort_keys=True),
                    self._now(),
                ),
            )

    async def set_game_state(self, key: str, value: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO game_state (key, value)
                VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (key, value),
            )

    async def store_adversarial_read(
        self, round_number: int, analysis: dict[str, Any]
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO adversarial_reads (
                    round_number,
                    analysis_json,
                    created_at
                )
                VALUES (?, ?, ?)
                """,
                (round_number, json.dumps(analysis, sort_keys=True), self._now()),
            )

    async def mark_coaching_consumed(self) -> None:
        with self._connect() as conn:
            conn.execute("UPDATE coaching SET consumed = 1 WHERE consumed = 0")
            conn.commit()

    async def log_review_decision(
        self,
        *,
        round_number: int,
        decision: Any,
        draft_text: str | None,
        revise_directives: list[str] | None = None,
    ) -> None:
        event_id = f"round-{round_number}"
        edit_text = getattr(decision, "final_text", None)
        if edit_text is None:
            edit_text = draft_text
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO review_gate_edits (
                    event_id,
                    decision,
                    edit_text,
                    revise_directives,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    event_id,
                    getattr(decision, "action", "unknown"),
                    edit_text,
                    json.dumps(revise_directives) if revise_directives is not None else None,
                    self._now(),
                ),
            )
            conn.commit()

    async def delete_entity(self, entity_type: str, entity_id: str) -> None:
        """Delete an entity by its primary key (e.g., promise_id, coalition_id)."""
        id_column = {
            "promises": "promise_id",
            "coalitions": "coalition_id",
            "inconsistencies": "inconsistency_id",
        }.get(entity_type)
        if id_column is None:
            return
        with self._connect() as conn:
            conn.execute(
                f"DELETE FROM {entity_type} WHERE {id_column} = ?",
                (entity_id,),
            )
            conn.commit()

    async def update_promise_status(
        self, promise_id: str, status: str, resolution: str = ""
    ) -> None:
        """Update a promise's status and resolution."""
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE promises
                SET status = ?, resolution = ?, updated_at = ?
                WHERE promise_id = ?
                """,
                (status, resolution, self._now(), promise_id),
            )
            conn.commit()

    def _upsert_faction_state(
        self, conn: sqlite3.Connection, item: dict[str, Any], updated_at: str
    ) -> None:
        existing = conn.execute(
            "SELECT * FROM faction_state WHERE faction_id = ?", (item["faction_id"],)
        ).fetchone()
        current = self._serialize_row("faction_state", existing) if existing else {}
        goals = item.get("goals", current.get("goals", []))
        behavioral_notes = item.get(
            "behavioral_notes", current.get("behavioral_notes", [])
        )
        credibility_score = item.get(
            "credibility_score", current.get("credibility_score")
        )
        conn.execute(
            """
            INSERT INTO faction_state (
                faction_id,
                goals,
                credibility_score,
                behavioral_notes,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(faction_id) DO UPDATE SET
                goals = excluded.goals,
                credibility_score = excluded.credibility_score,
                behavioral_notes = excluded.behavioral_notes,
                updated_at = excluded.updated_at
            """,
            (
                item["faction_id"],
                json.dumps(goals),
                credibility_score,
                json.dumps(behavioral_notes),
                updated_at,
            ),
        )

    def _upsert_promise(
        self, conn: sqlite3.Connection, item: dict[str, Any], updated_at: str
    ) -> None:
        existing = conn.execute(
            "SELECT * FROM promises WHERE promise_id = ?", (item["promise_id"],)
        ).fetchone()
        current = self._serialize_row("promises", existing) if existing else {}
        conn.execute(
            """
            INSERT INTO promises (
                promise_id,
                from_faction,
                to_faction,
                content,
                status,
                resolution,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(promise_id) DO UPDATE SET
                from_faction = excluded.from_faction,
                to_faction = excluded.to_faction,
                content = excluded.content,
                status = excluded.status,
                resolution = excluded.resolution,
                updated_at = excluded.updated_at
            """,
            (
                item["promise_id"],
                item["from_faction"],
                item["to_faction"],
                item["content"],
                item.get("status", current.get("status", "pending")),
                item.get("resolution", current.get("resolution")),
                updated_at,
            ),
        )

    def _upsert_coalition(
        self, conn: sqlite3.Connection, item: dict[str, Any], updated_at: str
    ) -> None:
        existing = conn.execute(
            "SELECT * FROM coalitions WHERE coalition_id = ?", (item["coalition_id"],)
        ).fetchone()
        current = self._serialize_row("coalitions", existing) if existing else {}
        conn.execute(
            """
            INSERT INTO coalitions (
                coalition_id,
                faction_a,
                faction_b,
                strength,
                confidence,
                basis,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(coalition_id) DO UPDATE SET
                faction_a = excluded.faction_a,
                faction_b = excluded.faction_b,
                strength = excluded.strength,
                confidence = excluded.confidence,
                basis = excluded.basis,
                updated_at = excluded.updated_at
            """,
            (
                item["coalition_id"],
                item["faction_a"],
                item["faction_b"],
                item.get("strength", current.get("strength")),
                item.get("confidence", current.get("confidence")),
                item.get("basis", current.get("basis")),
                updated_at,
            ),
        )

    def _upsert_inconsistency(
        self, conn: sqlite3.Connection, item: dict[str, Any], updated_at: str
    ) -> None:
        existing = conn.execute(
            "SELECT * FROM inconsistencies WHERE inconsistency_id = ?",
            (item["inconsistency_id"],),
        ).fetchone()
        current = self._serialize_row("inconsistencies", existing) if existing else {}
        conn.execute(
            """
            INSERT INTO inconsistencies (
                inconsistency_id,
                faction_id,
                description,
                leverage_value,
                spent,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(inconsistency_id) DO UPDATE SET
                faction_id = excluded.faction_id,
                description = excluded.description,
                leverage_value = excluded.leverage_value,
                spent = excluded.spent,
                updated_at = excluded.updated_at
            """,
            (
                item["inconsistency_id"],
                item["faction_id"],
                item["description"],
                item.get("leverage_value", current.get("leverage_value")),
                int(item.get("spent", current.get("spent", False))),
                updated_at,
            ),
        )

    def _table(self, entity_type: str) -> str:
        if entity_type not in self._PRIMARY_KEYS:
            raise ValueError(f"Unknown entity_type: {entity_type}")
        return entity_type

    def _column(self, table: str, column: str) -> str:
        if column not in self._COLUMNS[table]:
            raise ValueError(f"Unknown column for {table}: {column}")
        return column

    @staticmethod
    def _to_db_value(column: str, value: Any) -> Any:
        if isinstance(value, bool):
            return int(value)
        if column in {"goals", "behavioral_notes"}:
            return json.dumps(value)
        return value

    @staticmethod
    def _serialize_row(table: str, row: sqlite3.Row) -> dict[str, Any]:
        data = dict(row)
        if table == "faction_state":
            data["goals"] = json.loads(data["goals"])
            data["behavioral_notes"] = json.loads(data["behavioral_notes"])
        if table == "review_gate_edits" and data.get("revise_directives") is not None:
            try:
                data["revise_directives"] = json.loads(data["revise_directives"])
            except json.JSONDecodeError:
                pass
        if table in {"inconsistencies", "coaching"} and "spent" in data:
            data["spent"] = bool(data["spent"])
        if table == "coaching" and "consumed" in data:
            data["consumed"] = bool(data["consumed"])
        return data

    def _migrate_review_gate_edits(self, conn: sqlite3.Connection) -> None:
        columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(review_gate_edits)").fetchall()
        }
        if "revise_directives" not in columns:
            conn.execute(
                "ALTER TABLE review_gate_edits ADD COLUMN revise_directives TEXT"
            )
            conn.commit()

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()


__all__ = ["PatchSource", "SQLiteStateManager", "StatePatch"]
