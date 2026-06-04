from __future__ import annotations

import asyncio
import contextlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import pytest
import yaml

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
