from __future__ import annotations

import asyncio
import contextlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import pytest
import yaml

from modules.generation import GenerationResult
from modules.review_gate import OperatorReviewGate, ReviewDecision
from modules.state_manager import SQLiteStateManager
from modules.transport import OutboundMessage
from orchestrator import Orchestrator
from tests.helpers.factories import FakeCostAccountant, FakeLLMClient, make_event
from tests.helpers.stub_analyst import StubAnalyst
from tests.helpers.test_transport import TestTransport


PROJECT_ROOT = Path(__file__).resolve().parents[2]
INTELLIGENCE_FIXTURE = (
    PROJECT_ROOT / "tests" / "integration" / "fixtures" / "intelligence_stub.json"
)
SHORT_DRAFT = "England supports a balanced settlement."
LONG_DRAFT = "England supports a balanced settlement. " * 120


class FakeTransport(TestTransport):
    __test__ = False

    def __init__(self) -> None:
        super().__init__()
        self.sent: list[OutboundMessage] = []

    async def send(self, message: OutboundMessage) -> None:
        self.sent.append(message)
        await super().send(message)


class ScriptedLLMClient(FakeLLMClient):
    def __init__(self, generation_response: str) -> None:
        super().__init__(
            [
                {
                    "response": generation_response,
                    "reasoning": "Keeps the proposal concise.",
                },
                {
                    "reveals": [],
                    "commits_to": [],
                    "exploitable": [],
                    "counter_moves": [],
                    "summary": "No obvious exploit.",
                },
            ]
        )


def _draft(response_text: str) -> GenerationResult:
    return GenerationResult(
        success=True,
        response_text=response_text,
        reasoning="Keeps the proposal concise.",
        raw_response=None,
        error=None,
    )


@dataclass(frozen=True)
class FlowHarness:
    orchestrator: Any
    transport: FakeTransport
    task: asyncio.Task[None]


def _build_config(tmp_path: Path, *, max_message_chars: int) -> Path:
    config = yaml.safe_load(
        Path("config/pipeline_test.yaml").read_text(encoding="utf-8")
    )
    config["database"]["path"] = str(tmp_path / "review_gate_flow.db")
    config["modules"]["review_gate"]["class"] = "OperatorReviewGate"
    config["modules"]["review_gate"]["max_message_chars"] = max_message_chars
    config_path = tmp_path / "review_gate_flow.yaml"
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    return config_path


async def _start_flow(
    tmp_path: Path,
    *,
    generation_response: str,
    max_message_chars: int = 180,
) -> FlowHarness:
    config_path = _build_config(tmp_path, max_message_chars=max_message_chars)
    transport = FakeTransport()
    llm_client = ScriptedLLMClient(generation_response)
    cost_accountant = FakeCostAccountant()
    orchestrator = Orchestrator(
        config_path,
        base_path=PROJECT_ROOT,
        llm_client=llm_client,
        cost_accountant=cost_accountant,
        module_overrides={
            "transport": transport,
            "primary_analyst": StubAnalyst(INTELLIGENCE_FIXTURE, provider_id="primary"),
            "secondary_analyst": StubAnalyst(
                INTELLIGENCE_FIXTURE, provider_id="secondary"
            ),
        },
    )
    task = asyncio.create_task(orchestrator.start())
    await asyncio.sleep(0)
    return FlowHarness(orchestrator=orchestrator, transport=transport, task=task)


async def _wait_for(predicate: Callable[[], bool], *, timeout: float = 3.0) -> None:
    deadline = asyncio.get_running_loop().time() + timeout
    while not predicate():
        if asyncio.get_running_loop().time() > deadline:
            raise AssertionError("Timed out waiting for expected transport output")
        await asyncio.sleep(0.01)


async def _shutdown_flow(harness: FlowHarness) -> None:
    await harness.orchestrator.shutdown()
    harness.task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await harness.task


class _ScriptedPipeline:
    def __init__(self, responses: list[str]) -> None:
        self.responses = list(responses)
        self.calls: list[dict[str, str]] = []

    async def regenerate_with_directive(
        self, directive: str, previous_draft: str
    ) -> GenerationResult:
        self.calls.append(
            {
                "directive": directive,
                "previous_draft": previous_draft,
            }
        )
        response_text = self.responses.pop(0) if self.responses else previous_draft
        return _draft(response_text)


class DryRunTelegramReviewGate:
    """Scripted dry-run wrapper around the real OperatorReviewGate."""

    def __init__(
        self,
        *,
        transport: TestTransport,
        pipeline: Any,
        state_manager: Any | None = None,
        max_revises: int = 3,
    ) -> None:
        self.transport = transport
        self.gate = OperatorReviewGate(
            transport,
            pipeline=pipeline,
            state_manager=state_manager,
            max_revises=max_revises,
        )

    async def run(
        self,
        *,
        draft: GenerationResult,
        commands: list[str],
        round_number: int,
        adversarial: Any = None,
    ) -> ReviewDecision:
        task = asyncio.create_task(
            self.gate.submit(draft, adversarial=adversarial, round_number=round_number)
        )
        await asyncio.sleep(0)

        for command in commands:
            assert await self.gate.handle_command(command) is True

        decision = await task
        return decision


class _FailingTransport(FakeTransport):
    def __init__(self, *, fail_on_send: int) -> None:
        super().__init__()
        self._fail_on_send = fail_on_send
        self._send_calls = 0

    async def send(self, message: OutboundMessage) -> None:
        self._send_calls += 1
        if self._send_calls == self._fail_on_send:
            raise RuntimeError("coaching channel offline")
        await super().send(message)


@pytest.mark.asyncio
async def test_review_gate_flow_revise_then_approve():
    transport = FakeTransport()
    gate = DryRunTelegramReviewGate(
        transport=transport,
        pipeline=_ScriptedPipeline(["England insists on an equitable arrangement."]),
    )

    decision = await gate.run(
        draft=_draft(SHORT_DRAFT),
        commands=["/revise: be more assertive", "/approve"],
        round_number=4,
    )

    assert decision == ReviewDecision(
        action="approved",
        final_text="England insists on an equitable arrangement.",
        edit_notes=None,
    )
    assert len(transport.sent) == 2
    assert transport.sent[1].content.startswith("Round 4 — Revised Draft (revise 1/3)")
    assert "England insists on an equitable arrangement." in transport.sent[1].content
    assert gate.gate._pending is None
    assert gate.gate._revise_count == 1


@pytest.mark.asyncio
async def test_review_gate_flow_revise_chain_then_approve():
    transport = FakeTransport()
    gate = DryRunTelegramReviewGate(
        transport=transport,
        pipeline=_ScriptedPipeline(
            [
                "England proposes mutual restraint.",
                "England proposes mutual restraint with tighter guarantees.",
            ]
        ),
    )

    decision = await gate.run(
        draft=_draft(SHORT_DRAFT),
        commands=[
            "/revise: first revision",
            "/revise: second revision",
            "/approve",
        ],
        round_number=4,
    )

    assert decision == ReviewDecision(
        action="approved",
        final_text="England proposes mutual restraint with tighter guarantees.",
        edit_notes=None,
    )
    assert len(transport.sent) == 3
    assert "revise 2/3" in transport.sent[-1].content
    assert gate.gate._pending is None
    assert gate.gate._revise_count == 2


@pytest.mark.asyncio
async def test_review_gate_flow_revise_cap_rejects_fourth_then_block(tmp_path: Path):
    transport = FakeTransport()
    state_manager = SQLiteStateManager(
        tmp_path / "review_gate_flow.db",
        "config/schemas/state_patch.json",
    )
    gate = DryRunTelegramReviewGate(
        transport=transport,
        pipeline=_ScriptedPipeline(
            [
                "Draft v2",
                "Draft v3",
                "Draft v4",
            ]
        ),
        state_manager=state_manager,
    )

    decision = await gate.run(
        draft=_draft(SHORT_DRAFT),
        commands=[
            "/revise: first revision",
            "/revise: second revision",
            "/revise: third revision",
            "/revise: fourth revision",
            "/block",
        ],
        round_number=7,
    )

    rows = await state_manager.query("review_gate_edits", {})

    assert decision == ReviewDecision(
        action="blocked",
        final_text=None,
        edit_notes=None,
    )
    assert len(transport.sent) == 5
    assert transport.sent[-1].content == (
        "[revise limit reached — /approve, /edit:, or /block to resolve]"
    )
    assert gate.gate._pending is None
    assert gate.gate._revise_count == 3
    assert rows[0]["decision"] == "blocked"
    assert rows[0]["edit_text"] == "Draft v4"
    assert rows[0]["revise_directives"] == [
        "first revision",
        "second revision",
        "third revision",
    ]


@pytest.mark.asyncio
async def test_review_gate_flow_revise_then_block():
    transport = FakeTransport()
    gate = DryRunTelegramReviewGate(
        transport=transport,
        pipeline=_ScriptedPipeline(["England proposes mutual restraint."]),
    )

    decision = await gate.run(
        draft=_draft(SHORT_DRAFT),
        commands=["/revise: soften the tone", "/block"],
        round_number=4,
    )

    assert decision == ReviewDecision(
        action="blocked",
        final_text=None,
        edit_notes=None,
    )
    assert len(transport.sent) == 2
    assert gate.gate._pending is None
    assert gate.gate._revise_count == 1


@pytest.mark.asyncio
async def test_review_gate_flow_revise_transport_error_blocks():
    transport = _FailingTransport(fail_on_send=2)
    gate = DryRunTelegramReviewGate(
        transport=transport,
        pipeline=_ScriptedPipeline(["England insists on an equitable arrangement."]),
    )

    decision = await gate.run(
        draft=_draft(SHORT_DRAFT),
        commands=["/revise: be more assertive"],
        round_number=4,
    )

    assert decision == ReviewDecision(
        action="blocked",
        final_text=None,
        edit_notes="transport error: coaching channel offline",
    )
    assert len(transport.sent) == 1
    assert gate.gate._pending is None
    assert gate.gate._revise_count == 1


@pytest.mark.asyncio
async def test_review_gate_flow_happy_path(tmp_path: Path):
    harness = await _start_flow(tmp_path, generation_response=SHORT_DRAFT)
    try:
        await harness.transport.inject(
            make_event("/preview", sender_faction="operator", channel="coaching")
        )
        await _wait_for(
            lambda: any(
                message.channel == "coaching"
                and message.content.startswith("Review Gate - Round")
                for message in harness.transport.sent
            )
        )

        await harness.transport.inject(
            make_event("/approve", sender_faction="operator", channel="coaching")
        )
        await _wait_for(
            lambda: any(message.channel == "public" for message in harness.transport.sent)
        )

        public_messages = [
            message for message in harness.transport.sent if message.channel == "public"
        ]

        assert public_messages[-1].content == SHORT_DRAFT
        assert harness.orchestrator.review_gate._pending is None
    finally:
        await _shutdown_flow(harness)


@pytest.mark.asyncio
async def test_review_gate_flow_routes_state_command_while_review_pending(tmp_path: Path):
    harness = await _start_flow(tmp_path, generation_response=SHORT_DRAFT)
    try:
        await harness.transport.inject(
            make_event("/preview", sender_faction="operator", channel="coaching")
        )
        await _wait_for(
            lambda: any(
                message.channel == "coaching"
                and message.content.startswith("Review Gate - Round")
                for message in harness.transport.sent
            )
        )

        await harness.transport.inject(
            make_event("/state", sender_faction="operator", channel="coaching")
        )
        await _wait_for(
            lambda: any(
                message.channel == "coaching" and message.content.startswith("State")
                for message in harness.transport.sent
            )
        )

        await harness.transport.inject(
            make_event("/approve", sender_faction="operator", channel="coaching")
        )
        await _wait_for(
            lambda: any(message.channel == "public" for message in harness.transport.sent)
        )

        assert any(
            message.channel == "coaching" and message.content.startswith("State")
            for message in harness.transport.sent
        )
        assert any(message.channel == "public" for message in harness.transport.sent)
        assert harness.orchestrator.review_gate._pending is None
    finally:
        await _shutdown_flow(harness)


@pytest.mark.asyncio
async def test_review_gate_flow_chunks_large_draft_through_transport(tmp_path: Path):
    harness = await _start_flow(tmp_path, generation_response=LONG_DRAFT)
    try:
        await harness.transport.inject(
            make_event("/preview", sender_faction="operator", channel="coaching")
        )
        await _wait_for(
            lambda: any(
                message.channel == "coaching"
                and message.content.startswith("Review Gate - Round")
                for message in harness.transport.sent
            )
        )

        coaching_messages = [
            message for message in harness.transport.sent if message.channel == "coaching"
        ]
        assert len(coaching_messages) == 1
        assert coaching_messages[0].content.startswith("Review Gate - Round")
        assert len(coaching_messages[0].content) > 4096

        await harness.transport.inject(
            make_event("/approve", sender_faction="operator", channel="coaching")
        )
        await _wait_for(
            lambda: any(message.channel == "public" for message in harness.transport.sent)
        )

        assert harness.orchestrator.review_gate._pending is None
    finally:
        await _shutdown_flow(harness)


@pytest.mark.asyncio
async def test_review_gate_flow_lazy_fetch_through_transport(tmp_path: Path):
    harness = await _start_flow(tmp_path, generation_response=SHORT_DRAFT)
    try:
        await harness.transport.inject(
            make_event("/preview", sender_faction="operator", channel="coaching")
        )
        await _wait_for(
            lambda: any(
                message.channel == "coaching"
                and message.content.startswith("Review Gate - Round")
                for message in harness.transport.sent
            )
        )

        await harness.transport.inject(
            make_event("/adversarial", sender_faction="operator", channel="coaching")
        )
        await _wait_for(
            lambda: any(
                message.channel == "coaching"
                and message.content.startswith("Adversarial:\n")
                for message in harness.transport.sent
            )
        )

        adversarial_index = next(
            index
            for index, message in enumerate(harness.transport.sent)
            if message.channel == "coaching" and message.content.startswith("Adversarial:\n")
        )

        await harness.transport.inject(
            make_event("/approve", sender_faction="operator", channel="coaching")
        )
        await _wait_for(
            lambda: any(message.channel == "public" for message in harness.transport.sent)
        )

        public_index = next(
            index
            for index, message in enumerate(harness.transport.sent)
            if message.channel == "public"
        )

        assert adversarial_index < public_index
        assert harness.orchestrator.review_gate._pending is None
    finally:
        await _shutdown_flow(harness)
