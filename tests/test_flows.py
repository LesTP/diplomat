from __future__ import annotations

from datetime import datetime, timezone

import pytest

from flows.event_driven import (
    EventDrivenFlow,
    faction_address_detector,
    signal_round_detector,
)
from modules.types import InboundEvent


class FakePipeline:
    def __init__(self) -> None:
        self.events = []
        self.calls = []

    async def store_event(self, event):
        event_id = f"event-{len(self.events) + 1}"
        self.events.append((event_id, event))
        return event_id

    async def extract_from(self, event, event_id=None):
        self.calls.append(("extract", event.content, event_id))
        return event_id

    async def dispatch_operator(self, content, event_id="operator-dispatch"):
        self.calls.append(("operator", content, event_id))

    async def reconcile_and_analyze(self):
        self.calls.append(("round",))

    async def run_response(self, trigger_event=None):
        self.calls.append(("response", trigger_event.content))
        return True


class FakeTransport:
    def __init__(self, events=None) -> None:
        self.events = list(events or [])
        self.closed = False

    async def listen(self):
        for event in self.events:
            yield event

    async def close(self):
        self.closed = True


def _event(
    content: str,
    *,
    sender_faction: str = "france",
    channel: str = "public",
) -> InboundEvent:
    return InboundEvent(
        timestamp=datetime(2026, 5, 31, tzinfo=timezone.utc),
        sender_faction=sender_faction,
        channel=channel,
        content=content,
    )


@pytest.mark.asyncio
async def test_event_driven_flow_routes_operator_event_without_extraction():
    pipeline = FakePipeline()
    flow = EventDrivenFlow(pipeline=pipeline, transport=FakeTransport())

    event_id = await flow.process_event(
        _event("WATCH: France is stalling.", sender_faction="operator")
    )

    assert event_id == "event-1"
    assert pipeline.calls == [
        ("operator", "WATCH: France is stalling.", "event-1")
    ]


@pytest.mark.asyncio
async def test_event_driven_flow_extracts_each_game_event_after_debounce():
    pipeline = FakePipeline()
    flow = EventDrivenFlow(
        pipeline=pipeline,
        transport=FakeTransport(),
        message_debounce_seconds=0,
    )

    await flow.process_event(_event("first"))
    await flow.process_event(_event("second", sender_faction="germany"))
    for task in list(flow._extraction_tasks):
        await task

    assert pipeline.calls == [
        ("extract", "first", "event-1"),
        ("extract", "second", "event-2"),
    ]


@pytest.mark.asyncio
async def test_event_driven_flow_runs_round_boundary_before_response_trigger():
    pipeline = FakePipeline()
    flow = EventDrivenFlow(
        pipeline=pipeline,
        transport=FakeTransport(),
        round_detector=signal_round_detector(r"\[ROUND END\]"),
        address_detector=faction_address_detector("england"),
        message_debounce_seconds=0,
    )

    await flow.process_event(_event("[ROUND END] England"))
    for task in list(flow._extraction_tasks):
        await task

    assert pipeline.calls == [
        ("round",),
        ("extract", "[ROUND END] England", "event-1"),
    ]


@pytest.mark.asyncio
async def test_event_driven_flow_runs_response_for_direct_address():
    pipeline = FakePipeline()
    flow = EventDrivenFlow(
        pipeline=pipeline,
        transport=FakeTransport(),
        address_detector=faction_address_detector("england"),
        message_debounce_seconds=0,
    )

    await flow.process_event(_event("England, what is your offer?"))
    for task in list(flow._extraction_tasks):
        await task

    assert pipeline.calls == [
        ("response", "England, what is your offer?"),
        ("extract", "England, what is your offer?", "event-1"),
    ]


@pytest.mark.asyncio
async def test_event_driven_flow_start_reads_transport_and_shutdown_closes():
    events = [_event("one"), _event("two")]
    pipeline = FakePipeline()
    transport = FakeTransport(events)
    flow = EventDrivenFlow(
        pipeline=pipeline,
        transport=transport,
        message_debounce_seconds=0,
    )

    await flow.start()
    for task in list(flow._extraction_tasks):
        await task
    await flow.shutdown()

    assert [event.content for _event_id, event in pipeline.events] == ["one", "two"]
    assert transport.closed is True
