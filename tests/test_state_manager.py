from __future__ import annotations

import json
import sqlite3

import pytest
from jsonschema import ValidationError

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
