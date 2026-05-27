from __future__ import annotations

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from modules.types import InboundEvent


TRANSCRIPT_DIR = Path("tests/integration/fixtures/transcripts")
COOPERATIVE_TRANSCRIPT = TRANSCRIPT_DIR / "cooperative_3round.json"
BETRAYAL_TRANSCRIPT = TRANSCRIPT_DIR / "betrayal_arc.json"


async def replay_transcript(pipeline, fixture_path: Path) -> dict[str, list[dict[str, Any]]]:
    transcript = json.loads(fixture_path.read_text(encoding="utf-8"))

    for event_data in transcript["events"]:
        event = InboundEvent(
            timestamp=datetime.fromisoformat(event_data["timestamp"]),
            sender_faction=event_data["sender_faction"],
            channel=event_data["channel"],
            content=event_data["content"],
        )
        await pipeline.transport.inject(event)
        await asyncio.sleep(0.08 if event_data.get("is_round_end") else 0.05)

    state_manager = pipeline.orchestrator.state_manager
    return {
        "promises": await state_manager.query("promises", {}),
        "coalitions": await state_manager.query("coalitions", {}),
        "inconsistencies": await state_manager.query("inconsistencies", {}),
        "intelligence": await state_manager.query("intelligence", {}),
    }


async def test_cooperative_3round_promises(pipeline):
    state = await replay_transcript(pipeline, COOPERATIVE_TRANSCRIPT)
    expected = _expected(COOPERATIVE_TRANSCRIPT)["promises"]

    assert len(state["promises"]) == 2
    for promise in expected:
        matches = [
            row
            for row in state["promises"]
            if row["from_faction"] == promise["from_faction"]
            and row["to_faction"] == promise["to_faction"]
            and row["status"] == promise["status"]
        ]
        assert len(matches) == 1


async def test_cooperative_3round_coalition(pipeline):
    state = await replay_transcript(pipeline, COOPERATIVE_TRANSCRIPT)
    expected = _expected(COOPERATIVE_TRANSCRIPT)["coalitions"][0]

    assert len(state["coalitions"]) == 1
    assert state["coalitions"][0]["faction_a"] == expected["faction_a"]
    assert state["coalitions"][0]["faction_b"] == expected["faction_b"]


async def test_cooperative_3round_intelligence(pipeline):
    state = await replay_transcript(pipeline, COOPERATIVE_TRANSCRIPT)

    assert [row["round_number"] for row in state["intelligence"]] == [1, 2, 3]


async def test_betrayal_arc_inconsistency(pipeline):
    state = await replay_transcript(pipeline, BETRAYAL_TRANSCRIPT)
    expected = _expected(BETRAYAL_TRANSCRIPT)["inconsistencies"][0]

    assert len(state["inconsistencies"]) == 1
    assert state["inconsistencies"][0]["faction_id"] == expected["faction_id"]
    assert state["inconsistencies"][0]["description"] == expected["description"]


async def test_betrayal_arc_promise_and_coalition(pipeline):
    state = await replay_transcript(pipeline, BETRAYAL_TRANSCRIPT)
    expected = _expected(BETRAYAL_TRANSCRIPT)

    assert len(state["promises"]) == 1
    assert state["promises"][0]["from_faction"] == expected["promises"][0]["from_faction"]
    assert state["promises"][0]["to_faction"] == expected["promises"][0]["to_faction"]
    assert state["promises"][0]["status"] == expected["promises"][0]["status"]

    assert len(state["coalitions"]) == 1
    assert state["coalitions"][0]["faction_a"] == expected["coalitions"][0]["faction_a"]
    assert state["coalitions"][0]["faction_b"] == expected["coalitions"][0]["faction_b"]


def _expected(fixture_path: Path) -> dict[str, Any]:
    transcript = json.loads(fixture_path.read_text(encoding="utf-8"))
    return transcript["expected_final_state"]
