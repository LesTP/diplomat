from __future__ import annotations

import asyncio
import json

from modules.types import EventFilter
from tests.helpers.factories import make_event, make_round_end_event


async def test_game_message_ingested_and_extracted(pipeline):
    await pipeline.transport.inject(
        make_event("France promises England support in Belgium.")
    )
    await _settle()

    events = await pipeline.orchestrator.event_store.query(EventFilter(limit=10))
    changes = await pipeline.orchestrator.state_manager.query("state_change_log", {})
    promises = await pipeline.orchestrator.state_manager.query("promises", {})

    assert [event.event.content for event in events] == [
        "France promises England support in Belgium."
    ]
    assert changes[0]["trigger_type"] == "message"
    assert promises[0]["from_faction"] == "France"
    assert promises[0]["to_faction"] == "England"


async def test_operator_priority_coaching_stored_unconsumed(pipeline):
    await pipeline.transport.inject(
        make_event(
            "PRIORITY: Keep France dependent on our fleet.",
            sender_faction="operator",
            channel="coaching",
        )
    )
    await _settle()

    rows = await pipeline.orchestrator.state_manager.query(
        "coaching",
        {"consumed": False},
    )

    assert len(rows) == 1
    assert rows[0]["tag"] == "PRIORITY"
    assert rows[0]["content"] == "Keep France dependent on our fleet."


async def test_operator_intel_coaching_creates_intel_state_change(pipeline):
    await pipeline.transport.inject(
        make_event(
            "INTEL: Germany broke its promise to England.",
            sender_faction="operator",
            channel="coaching",
        )
    )
    await _settle()

    changes = await pipeline.orchestrator.state_manager.query("state_change_log", {})
    inconsistencies = await pipeline.orchestrator.state_manager.query(
        "inconsistencies",
        {},
    )

    assert changes[0]["trigger_type"] == "intel_correction"
    assert inconsistencies[0]["faction_id"] == "Germany"


async def test_round_end_populates_intelligence(pipeline):
    await pipeline.transport.inject(make_round_end_event())
    await _settle()

    rows = await pipeline.orchestrator.state_manager.query("intelligence", {})
    analysis = json.loads(rows[0]["analysis_json"])

    assert rows[0]["round_number"] == 1
    assert analysis["primary"]["provider_id"] == "primary"
    assert analysis["primary"]["report"]["threat_level"] == 3
    assert pipeline.orchestrator.current_round == 2


async def test_direct_address_generates_public_response(pipeline):
    await pipeline.transport.inject(
        make_event("England, will you support France in Belgium?")
    )
    await _settle()

    outputs = await pipeline.transport.get_output()

    public_messages = [message for message in outputs if message.channel == "public"]
    assert public_messages[0].content == "England supports a balanced settlement."


async def test_preview_command_runs_response_pipeline(pipeline):
    await pipeline.transport.inject(
        make_event(
            "/preview",
            sender_faction="operator",
            channel="coaching",
        )
    )
    await _settle()

    outputs = await pipeline.transport.get_output()

    public_messages = [message for message in outputs if message.channel == "public"]
    assert public_messages[0].content == "England supports a balanced settlement."


async def _settle() -> None:
    await asyncio.sleep(0.05)
