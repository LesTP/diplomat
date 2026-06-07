from __future__ import annotations

from datetime import datetime, timezone

import pytest

from modules.context_assembler import DecisionContext
from modules.generation import GenerationResult
from modules.types import InboundEvent
from pipeline import Pipeline


class FakeEventStore:
    def __init__(self) -> None:
        self.appended = []

    async def append(self, event, round_number):
        self.appended.append((event, round_number))
        return f"event-{len(self.appended)}"


class FakeStateManager:
    async def get_full_state(self):
        return {"promises": [{"promise_id": "p1"}]}


class FakeCostAccountant:
    async def available_budget(self):
        return 0.75


class FakeOrchestrator:
    def __init__(self) -> None:
        self.current_round = 2
        self.event_store = FakeEventStore()
        self.state_manager = FakeStateManager()
        self.cost_accountant = FakeCostAccountant()
        self.cost_config = {
            "per_round_budget_usd": 1.0,
            "session_budget_usd": 10.0,
        }
        self.review_gate = None
        self.calls = []

    async def start(self):
        self.calls.append(("start",))

    async def shutdown(self):
        self.calls.append(("shutdown",))

    async def _apply_extraction(self, content, trigger_type, trigger_ref):
        self.calls.append(("extract", content, trigger_type, trigger_ref))

    async def _route_operator_event(self, event, event_id):
        self.calls.append(("operator", event.content, event_id))

    def advance_to_round(self, round_number):
        self.current_round = round_number
        self.calls.append(("advance", round_number))

    async def handle_round_boundary(self):
        self.calls.append(("round_boundary",))

    async def run_response_pipeline(self, trigger_event=None):
        self.calls.append(("response", trigger_event))
        return True

    async def _latest_intelligence(self):
        return {"primary": {"report": "ready"}}


class FakeRevisionGenerator:
    def __init__(self) -> None:
        self.calls = []

    async def generate(self, context, **kwargs):
        return await self.generate_with_metadata(context, **kwargs)

    async def generate_with_metadata(
        self,
        context,
        *,
        purpose="generation",
        attribution=None,
    ):
        self.calls.append(
            {
                "context": context,
                "purpose": purpose,
                "attribution": attribution,
            }
        )
        return GenerationResult(
            success=True,
            response_text="Revised response.",
            reasoning="Because the directive asked for it.",
            raw_response=None,
            error=None,
        )


class FakeReviewGate:
    def __init__(self, consumed: bool) -> None:
        self.consumed = consumed
        self.calls: list[str] = []

    async def handle_command(self, command: str) -> bool:
        self.calls.append(command)
        return self.consumed


def _event(content: str = "France proposes a split.") -> InboundEvent:
    return InboundEvent(
        timestamp=datetime(2026, 5, 31, tzinfo=timezone.utc),
        sender_faction="france",
        channel="public",
        content=content,
    )


@pytest.mark.asyncio
async def test_pipeline_lifecycle_delegates_to_orchestrator():
    orchestrator = FakeOrchestrator()
    pipeline = Pipeline(orchestrator)

    await pipeline.start()
    await pipeline.shutdown()

    assert orchestrator.calls == [("start",), ("shutdown",)]


@pytest.mark.asyncio
async def test_pipeline_event_and_extraction_methods_delegate():
    orchestrator = FakeOrchestrator()
    pipeline = Pipeline(orchestrator)
    event = _event()

    event_id = await pipeline.store_event(event)
    extracted_id = await pipeline.extract_from(event, event_id=event_id)

    assert event_id == "event-1"
    assert extracted_id == "event-1"
    assert orchestrator.event_store.appended == [(event, 2)]
    assert orchestrator.calls == [
        ("extract", "France proposes a split.", "message", "event-1")
    ]


@pytest.mark.asyncio
async def test_pipeline_extract_from_stores_event_when_needed():
    orchestrator = FakeOrchestrator()
    pipeline = Pipeline(orchestrator)
    event = _event("Germany offers support.")

    event_id = await pipeline.extract_from(event)

    assert event_id == "event-1"
    assert orchestrator.event_store.appended == [(event, 2)]
    assert orchestrator.calls == [
        ("extract", "Germany offers support.", "message", "event-1")
    ]


@pytest.mark.asyncio
async def test_pipeline_operator_round_and_response_methods_delegate():
    orchestrator = FakeOrchestrator()
    pipeline = Pipeline(orchestrator)
    event = _event("England, respond.")

    await pipeline.dispatch_operator("WATCH: Germany is quiet.", "event-operator")
    pipeline.advance_to_round(4)
    await pipeline.reconcile_and_analyze()
    response_sent = await pipeline.run_response(trigger_event=event)

    assert response_sent is True
    assert orchestrator.current_round == 4
    assert orchestrator.calls == [
        ("operator", "WATCH: Germany is quiet.", "event-operator"),
        ("advance", 4),
        ("round_boundary",),
        ("response", event),
    ]


@pytest.mark.asyncio
async def test_pipeline_dispatch_operator_consumed_review_command_skips_fallthrough():
    orchestrator = FakeOrchestrator()
    orchestrator.review_gate = FakeReviewGate(consumed=True)
    pipeline = Pipeline(orchestrator)

    await pipeline.dispatch_operator("/approve", "event-approve")

    assert orchestrator.review_gate.calls == ["/approve"]
    assert orchestrator.calls == []


@pytest.mark.asyncio
async def test_pipeline_dispatch_operator_unconsumed_review_command_falls_through():
    orchestrator = FakeOrchestrator()
    orchestrator.review_gate = FakeReviewGate(consumed=False)
    pipeline = Pipeline(orchestrator)

    await pipeline.dispatch_operator("/state", "event-state")

    assert orchestrator.review_gate.calls == ["/state"]
    assert orchestrator.calls == [("operator", "/state", "event-state")]


@pytest.mark.asyncio
async def test_pipeline_dispatch_operator_non_slash_content_skips_review_gate():
    orchestrator = FakeOrchestrator()
    orchestrator.review_gate = FakeReviewGate(consumed=True)
    pipeline = Pipeline(orchestrator)

    await pipeline.dispatch_operator("WATCH: Germany is quiet.", "event-watch")

    assert orchestrator.review_gate.calls == []
    assert orchestrator.calls == [("operator", "WATCH: Germany is quiet.", "event-watch")]


@pytest.mark.asyncio
async def test_pipeline_query_methods_delegate():
    orchestrator = FakeOrchestrator()
    pipeline = Pipeline(orchestrator)

    assert await pipeline.get_state() == {"promises": [{"promise_id": "p1"}]}
    assert await pipeline.get_intelligence() == {"primary": {"report": "ready"}}
    assert await pipeline.get_ledger() == {
        "current_round": 2,
        "per_round_budget_usd": 1.0,
        "session_budget_usd": 10.0,
        "available_budget_usd": 0.75,
    }


@pytest.mark.asyncio
async def test_pipeline_regenerate_with_directive_appends_revision_sections():
    class RevisionOrchestrator:
        def __init__(self) -> None:
            self.faction_id = "england"
            self.generator = FakeRevisionGenerator()

        async def _build_decision_context(self):
            return DecisionContext(
                system_prompt="Persona prompt",
                user_prompt="Base prompt",
                metadata={"round_number": 3, "event_count": 12},
            )

    orchestrator = RevisionOrchestrator()
    pipeline = Pipeline(orchestrator)

    result = await pipeline.regenerate_with_directive(
        "Be more direct about Belgium.",
        "Original draft text.",
    )

    assert result == GenerationResult(
        success=True,
        response_text="Revised response.",
        reasoning="Because the directive asked for it.",
        raw_response=None,
        error=None,
    )
    assert len(orchestrator.generator.calls) == 1
    call = orchestrator.generator.calls[0]
    assert call["purpose"] == "generation_revision"
    assert call["attribution"] == "england"
    assert call["context"].system_prompt == "Persona prompt"
    assert call["context"].metadata == {"round_number": 3, "event_count": 12}
    assert call["context"].user_prompt == (
        "Base prompt\n\n"
        "[OPERATOR REVISION DIRECTIVE]: Be more direct about Belgium.\n\n"
        "[PREVIOUS DRAFT — REVISE PER DIRECTIVE]: Original draft text."
    )
