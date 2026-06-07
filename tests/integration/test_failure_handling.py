from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone

from modules.adversarial import AdversarialResult
from modules.extraction import ExtractionResult
from modules.generation import GenerationResult
from modules.types import AnalysisResult, EventFilter
from tests.helpers.factories import make_event, make_round_end_event


async def test_extraction_failure_keeps_pipeline_running_and_event_stored(
    pipeline,
    monkeypatch,
):
    async def fail_extract(input_text, current_state, trigger_type):
        return ExtractionResult(success=False, patch=None, error="extract failed")

    monkeypatch.setattr(pipeline.orchestrator.extractor, "extract", fail_extract)

    await pipeline.transport.inject(
        make_event("France promises England support in Belgium.")
    )
    await _settle()

    events = await pipeline.orchestrator.event_store.query(EventFilter(limit=10))
    changes = await pipeline.orchestrator.state_manager.query("state_change_log", {})

    assert [event.event.content for event in events] == [
        "France promises England support in Belgium."
    ]
    assert changes == []
    assert pipeline.task.done() is False


async def test_secondary_analyst_failure_stores_primary_only(pipeline, monkeypatch):
    async def fail_secondary(state, recent_events=None):
        return AnalysisResult(
            success=False,
            provider_id="secondary",
            report=None,
            error="secondary failed",
            timestamp=datetime(2026, 5, 27, tzinfo=timezone.utc),
        )

    monkeypatch.setattr(
        pipeline.orchestrator.secondary_analyst,
        "analyze",
        fail_secondary,
    )

    await pipeline.transport.inject(make_round_end_event())
    await _settle()

    rows = await pipeline.orchestrator.state_manager.query("intelligence", {})
    analysis = json.loads(rows[0]["analysis_json"])
    outputs = await pipeline.transport.get_output()

    assert analysis["primary"]["success"] is True
    assert analysis["secondary"]["success"] is False
    assert analysis["divergences"] == []
    assert any(
        message.channel == "coaching"
        and "Secondary analyst failed" in message.content
        for message in outputs
    )


async def test_adversarial_failure_posts_response_with_warning(pipeline, monkeypatch):
    async def fail_adversarial(draft):
        return AdversarialResult(
            success=False,
            analysis=None,
            error="adversarial failed",
        )

    monkeypatch.setattr(pipeline.orchestrator.adversarial, "read", fail_adversarial)

    await pipeline.transport.inject(
        make_event("England, will you support France in Belgium?")
    )
    await _settle()

    outputs = await pipeline.transport.get_output()

    assert any(
        message.channel == "coaching"
        and "Adversarial read failed" in message.content
        for message in outputs
    )
    assert any(
        message.channel == "public"
        and message.content == "England supports a balanced settlement."
        for message in outputs
    )


async def test_double_generation_failure_alerts_operator(pipeline, monkeypatch):
    async def fail_generation(context, **kwargs):
        return GenerationResult(
            success=False,
            response_text=None,
            reasoning=None,
            raw_response=None,
            error="generation failed",
        )

    monkeypatch.setattr(pipeline.orchestrator.generator, "generate", fail_generation)

    await pipeline.transport.inject(
        make_event(
            "/preview",
            sender_faction="operator",
            channel="coaching",
        )
    )
    await _settle()

    outputs = await pipeline.transport.get_output()

    assert any(
        message.channel == "coaching"
        and "Generation failed: generation failed" in message.content
        for message in outputs
    )
    assert not any(message.channel == "public" for message in outputs)


async def test_transport_send_failure_after_retries_alerts_operator(
    pipeline,
    monkeypatch,
):
    original_send = pipeline.transport.send
    attempts = 0

    async def fail_public_send(message):
        nonlocal attempts
        if message.channel == "public":
            attempts += 1
            raise RuntimeError("send failed")
        await original_send(message)

    monkeypatch.setattr(pipeline.transport, "send", fail_public_send)

    await pipeline.transport.inject(
        make_event("England, will you support France in Belgium?")
    )
    await _settle()

    outputs = await pipeline.transport.get_output()

    assert attempts == 3
    assert any(
        message.channel == "coaching"
        and "Transport send failed after 3 attempts." in message.content
        for message in outputs
    )


async def _settle() -> None:
    await asyncio.sleep(0.05)
