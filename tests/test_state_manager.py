from __future__ import annotations

import json
import sqlite3

import pytest
from jsonschema import ValidationError

from modules.review_gate import ReviewDecision
from modules.state_manager import SQLiteStateManager
from modules.types import PatchSource, StatePatch


SCHEMA_PATH = "config/schemas/state_patch.json"


def manager(tmp_path) -> SQLiteStateManager:
    return SQLiteStateManager(tmp_path / "game.db", SCHEMA_PATH)


def full_patch() -> StatePatch:
    return StatePatch(
        {
            "faction_state": [
                {
                    "faction_id": "england",
                    "goals": ["control the north sea"],
                    "credibility_score": 0.8,
                    "behavioral_notes": ["direct negotiator"],
                }
            ],
            "promises": [
                {
                    "promise_id": "p1",
                    "from_faction": "england",
                    "to_faction": "france",
                    "content": "Support France into Belgium.",
                    "status": "pending",
                }
            ],
            "coalitions": [
                {
                    "coalition_id": "c1",
                    "faction_a": "england",
                    "faction_b": "france",
                    "strength": 0.7,
                    "confidence": 0.6,
                    "basis": "shared anti-germany opening",
                }
            ],
            "inconsistencies": [
                {
                    "inconsistency_id": "i1",
                    "faction_id": "france",
                    "description": "Promised two incompatible supports.",
                    "leverage_value": 0.9,
                    "spent": False,
                }
            ],
        }
    )


@pytest.mark.asyncio
async def test_apply_patch_validates_audits_and_upserts_domain_tables(tmp_path):
    sm = manager(tmp_path)

    await sm.apply_patch(full_patch(), PatchSource("message", "evt-1"))

    faction = await sm.get("faction_state", "england")
    assert faction["goals"] == ["control the north sea"]
    assert faction["credibility_score"] == 0.8
    assert faction["behavioral_notes"] == ["direct negotiator"]

    promises = await sm.query("promises", {"from_faction": "england"})
    assert [promise["promise_id"] for promise in promises] == ["p1"]
    assert promises[0]["status"] == "pending"

    audit_rows = await sm.query("state_change_log", {"trigger_ref": "evt-1"})
    assert len(audit_rows) == 1
    assert audit_rows[0]["trigger_type"] == "message"
    assert json.loads(audit_rows[0]["patch_json"]) == full_patch().data


@pytest.mark.asyncio
async def test_get_query_and_full_state_filter_current_entities(tmp_path):
    sm = manager(tmp_path)
    await sm.apply_patch(full_patch(), PatchSource("message", "evt-1"))
    await sm.apply_patch(
        StatePatch(
            {
                "promises": [
                    {
                        "promise_id": "p2",
                        "from_faction": "france",
                        "to_faction": "england",
                        "content": "Do not enter the Channel.",
                        "status": "kept",
                    }
                ],
                "inconsistencies": [
                    {
                        "inconsistency_id": "i2",
                        "faction_id": "germany",
                        "description": "Spent leverage.",
                        "spent": True,
                    }
                ],
            }
        ),
        PatchSource("message", "evt-2"),
    )

    assert await sm.get("promises", "missing") is None
    coalitions = await sm.query("coalitions", {"faction_a": "england"})
    assert [coalition["coalition_id"] for coalition in coalitions] == ["c1"]

    full_state = await sm.get_full_state()
    assert [item["faction_id"] for item in full_state["faction_state"]] == ["england"]
    assert [item["promise_id"] for item in full_state["promises"]] == ["p1"]
    assert [item["coalition_id"] for item in full_state["coalitions"]] == ["c1"]
    assert [item["inconsistency_id"] for item in full_state["inconsistencies"]] == [
        "i1"
    ]


@pytest.mark.asyncio
async def test_store_coaching_inserts_consumed_flag_and_content(tmp_path):
    sm = manager(tmp_path)

    await sm.store_coaching("coach-1", "WATCH", "Germany is stalling.", False)

    rows = await sm.query("coaching", {"coaching_id": "coach-1"})
    assert len(rows) == 1
    assert rows[0]["tag"] == "WATCH"
    assert rows[0]["content"] == "Germany is stalling."
    assert rows[0]["consumed"] is False
    assert rows[0]["created_at"]


@pytest.mark.asyncio
async def test_store_intelligence_inserts_sorted_json_payload(tmp_path):
    sm = manager(tmp_path)
    analysis = {"secondary": {"success": True}, "primary": {"success": True}}

    await sm.store_intelligence(3, "primary", analysis)

    rows = await sm.query("intelligence", {"provider": "primary"})
    assert len(rows) == 1
    assert rows[0]["round_number"] == 3
    assert json.loads(rows[0]["analysis_json"]) == analysis
    assert rows[0]["analysis_json"] == json.dumps(analysis, sort_keys=True)
    assert rows[0]["created_at"]


@pytest.mark.asyncio
async def test_set_game_state_inserts_and_updates_value(tmp_path):
    sm = manager(tmp_path)

    await sm.set_game_state("round_number", "1")
    await sm.set_game_state("round_number", "2")

    row = await sm.get("game_state", "round_number")
    assert row == {"key": "round_number", "value": "2"}


@pytest.mark.asyncio
async def test_store_adversarial_read_inserts_sorted_json_payload(tmp_path):
    sm = manager(tmp_path)
    analysis = {"risks": ["overcommitment"], "score": 4}

    await sm.store_adversarial_read(4, analysis)

    rows = await sm.query("adversarial_reads", {"round_number": 4})
    assert len(rows) == 1
    assert json.loads(rows[0]["analysis_json"]) == analysis
    assert rows[0]["analysis_json"] == json.dumps(analysis, sort_keys=True)
    assert rows[0]["created_at"]


@pytest.mark.asyncio
async def test_mark_coaching_consumed_marks_only_unconsumed_rows(tmp_path):
    sm = manager(tmp_path)
    await sm.store_coaching("coach-1", "WATCH", "Watch Germany.", False)
    await sm.store_coaching("coach-2", "TONE", "Be warmer.", True)

    await sm.mark_coaching_consumed()

    rows = await sm.query("coaching", {})
    by_id = {row["coaching_id"]: row for row in rows}
    assert by_id["coach-1"]["consumed"] is True
    assert by_id["coach-2"]["consumed"] is True
    assert len(rows) == 2


@pytest.mark.asyncio
async def test_log_review_decision_persists_revise_directives(tmp_path):
    sm = manager(tmp_path)

    await sm.log_review_decision(
        round_number=4,
        decision=ReviewDecision(
            action="approved",
            final_text="Draft v4",
            edit_notes=None,
        ),
        draft_text="Draft v4",
        revise_directives=["first revision", "second revision"],
    )

    rows = await sm.query("review_gate_edits", {})

    assert len(rows) == 1
    assert rows[0]["event_id"] == "round-4"
    assert rows[0]["decision"] == "approved"
    assert rows[0]["edit_text"] == "Draft v4"
    assert rows[0]["revise_directives"] == ["first revision", "second revision"]


@pytest.mark.asyncio
async def test_apply_patch_rejects_invalid_patch_without_audit_row(tmp_path):
    sm = manager(tmp_path)

    with pytest.raises(ValidationError):
        await sm.apply_patch(
            StatePatch({"faction_state": [{"faction_id": "england"}]}),
            PatchSource("message", "evt-invalid"),
        )

    assert await sm.query("state_change_log", {}) == []
    assert await sm.get("faction_state", "england") is None


@pytest.mark.asyncio
async def test_unknown_entity_type_and_filter_column_raise_value_error(tmp_path):
    sm = manager(tmp_path)

    with pytest.raises(ValueError):
        await sm.get("unknown", "id")

    with pytest.raises(ValueError):
        await sm.query("promises", {"not_a_column": "value"})


def test_initialization_creates_owned_tables_and_enables_wal(tmp_path):
    db_path = tmp_path / "game.db"
    manager(tmp_path)

    with sqlite3.connect(db_path) as conn:
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }

    assert mode == "wal"
    assert {
        "faction_state",
        "promises",
        "coalitions",
        "inconsistencies",
        "state_change_log",
        "intelligence",
        "adversarial_reads",
        "coaching",
        "review_gate_edits",
        "game_state",
    }.issubset(tables)


@pytest.mark.asyncio
async def test_review_gate_edits_migration_keeps_existing_rows_null(tmp_path):
    db_path = tmp_path / "game.db"
    with sqlite3.connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE review_gate_edits (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id  TEXT NOT NULL,
                decision  TEXT NOT NULL,
                edit_text TEXT,
                created_at TEXT NOT NULL
            );
            INSERT INTO review_gate_edits (
                event_id,
                decision,
                edit_text,
                created_at
            )
            VALUES ('round-1', 'edited', 'Softer.', '2026-06-07T00:00:00Z');
            """
        )

    sm = SQLiteStateManager(db_path, SCHEMA_PATH)
    rows = await sm.query("review_gate_edits", {})

    with sqlite3.connect(db_path) as conn:
        columns = {
            row[1]
            for row in conn.execute("PRAGMA table_info(review_gate_edits)").fetchall()
        }

    assert "revise_directives" in columns
    assert rows[0]["revise_directives"] is None
