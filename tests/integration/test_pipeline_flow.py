from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from typing import TypeVar

from modules.types import EventFilter
from tests.helpers.factories import make_event, make_round_end_event

T = TypeVar("T")


async def test_game_message_ingested_and_extracted(pipeline):
    state_manager = pipeline.orchestrator.state_manager
    await pipeline.transport.inject(
        make_event("France promises England support in Belgium.")
    )

    # Promises are written last in the ingest->extract path, so waiting for them
    # guarantees events + state_change_log rows already exist.
    promises = await _wait_for(lambda: state_manager.query("promises", {}))

    events = await pipeline.orchestrator.event_store.query(EventFilter(limit=10))
    changes = await state_manager.query("state_change_log", {})

    assert [event.event.content for event in events] == [
        "France promises England support in Belgium."
    ]
    assert changes[0]["trigger_type"] == "message"
    assert promises[0]["from_faction"] == "France"
    assert promises[0]["to_faction"] == "England"


async def test_operator_priority_coaching_stored_unconsumed(pipeline):
    state_manager = pipeline.orchestrator.state_manager
    await pipeline.transport.inject(
        make_event(
            "PRIORITY: Keep France dependent on our fleet.",
            sender_faction="operator",
            channel="coaching",
        )
    )

    rows = await _wait_for(
        lambda: state_manager.query("coaching", {"consumed": False})
    )

    assert len(rows) == 1
    assert rows[0]["tag"] == "PRIORITY"
    assert rows[0]["content"] == "Keep France dependent on our fleet."


async def test_operator_intel_coaching_creates_intel_state_change(pipeline):
    state_manager = pipeline.orchestrator.state_manager
    await pipeline.transport.inject(
        make_event(
            "INTEL: Germany broke its promise to England.",
            sender_faction="operator",
            channel="coaching",
        )
    )

    inconsistencies = await _wait_for(
        lambda: state_manager.query("inconsistencies", {})
    )
    changes = await state_manager.query("state_change_log", {})

    assert changes[0]["trigger_type"] == "intel_correction"
    assert inconsistencies[0]["faction_id"] == "Germany"


async def test_round_end_populates_intelligence(pipeline):
    state_manager = pipeline.orchestrator.state_manager
    await pipeline.transport.inject(make_round_end_event())

    # Wait for the full terminal state of the round boundary: intelligence
    # written AND the round counter advanced. A fixed sleep here raced the two
    # analyst passes under full-suite CPU load (the flaky-isolation failure).
    async def _round_end_ready() -> list[dict]:
        rows = await state_manager.query("intelligence", {})
        if rows and pipeline.orchestrator.current_round == 2:
            return rows
        return []

    rows = await _wait_for(_round_end_ready)
    analysis = json.loads(rows[0]["analysis_json"])

    assert rows[0]["round_number"] == 1
    assert analysis["primary"]["provider_id"] == "primary"
    assert analysis["primary"]["report"]["threat_level"] == 3
    assert pipeline.orchestrator.current_round == 2


async def test_direct_address_generates_public_response(pipeline):
    await pipeline.transport.inject(
        make_event("England, will you support France in Belgium?")
    )

    public_messages = await _wait_for_public_output(pipeline.transport)

    assert public_messages[0].content == "England supports a balanced settlement."


async def test_preview_command_runs_response_pipeline(pipeline):
    await pipeline.transport.inject(
        make_event(
            "/preview",
            sender_faction="operator",
            channel="coaching",
        )
    )

    public_messages = await _wait_for_public_output(pipeline.transport)

    assert public_messages[0].content == "England supports a balanced settlement."


async def _wait_for(
    predicate: Callable[[], Awaitable[T]],
    *,
    timeout: float = 2.0,
    interval: float = 0.01,
) -> T:
    """Poll an async predicate until it returns a truthy value (or timeout).

    Replaces fixed-duration sleeps so the assertions don't race the pipeline's
    async processing under load. On timeout the last (falsy) result is returned
    so the caller's assertion fails with a meaningful value, not a hang.
    """
    elapsed = 0.0
    while True:
        result = await predicate()
        if result or elapsed >= timeout:
            return result
        await asyncio.sleep(interval)
        elapsed += interval


async def _wait_for_public_output(transport, *, timeout: float = 2.0, interval: float = 0.01):
    """Drain transport output until a public message appears (or timeout).

    `get_output()` is destructive (drains the queue), so messages are
    accumulated across poll iterations.
    """
    collected: list = []

    async def _has_public() -> list:
        collected.extend(await transport.get_output())
        return [message for message in collected if message.channel == "public"]

    return await _wait_for(_has_public, timeout=timeout, interval=interval)
