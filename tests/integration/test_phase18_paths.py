from __future__ import annotations

import asyncio
import contextlib
import json
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
import yaml

from modules.reconciliation import StateReconciler
from modules.types import EventFilter, InboundEvent
from orchestrator import OrchestrationOptions, Orchestrator
from tests.helpers.factories import FakeCostAccountant, make_event, make_round_end_event
from tests.helpers.stub_analyst import StubAnalyst
from tests.helpers.test_transport import TestTransport


@dataclass(frozen=True)
class Phase18PipelineHarness:
    orchestrator: Orchestrator
    transport: TestTransport
    llm_client: "Phase18FakeLLMClient"
    cost_accountant: FakeCostAccountant
    task: asyncio.Task[None]


class Phase18FakeLLMClient:
    """Fake shared LLM client with explicit buckets for Phase 18 path tests."""

    def __init__(
        self,
        *,
        reconciliation_responses: Iterable[dict[str, Any]] | None = None,
        generation_responses: Iterable[dict[str, Any] | str] | None = None,
        adversarial_responses: Iterable[dict[str, Any] | str] | None = None,
    ) -> None:
        self.reconciliation_responses = list(
            reconciliation_responses or [empty_reconciliation_response()]
        )
        self.generation_responses = list(
            generation_responses
            or [
                {
                    "response": "England supports a balanced settlement.",
                    "reasoning": "Keeps options open.",
                }
            ]
        )
        self.adversarial_responses = list(
            adversarial_responses
            or [
                {
                    "reveals": [],
                    "commits_to": [],
                    "exploitable": [],
                    "counter_moves": [],
                    "summary": "No obvious exploit.",
                }
            ]
        )
        self.calls: list[dict[str, Any]] = []

    async def complete(self, **kwargs: Any) -> str:
        self.calls.append(kwargs)
        system_prompt = _system_prompt_from_kwargs(kwargs).lower()
        schema = kwargs.get("schema")

        if "negotiation state reconciler" in system_prompt:
            return self._pop_json(
                self.reconciliation_responses,
                empty_reconciliation_response(),
            )
        if _schema_has_property(schema, "response"):
            return self._pop_json(
                self.generation_responses,
                self.generation_responses[-1],
            )
        return self._pop_json(
            self.adversarial_responses,
            self.adversarial_responses[-1],
        )

    @staticmethod
    def _pop_json(responses: list[dict[str, Any] | str], default: Any) -> str:
        response = responses.pop(0) if responses else default
        if isinstance(response, str):
            return response
        return json.dumps(response, sort_keys=True)


@pytest.fixture
async def phase18_pipeline(tmp_path: Path) -> Phase18PipelineHarness:
    config_path = _tmp_pipeline_config(tmp_path)
    transport = TestTransport()
    llm_client = Phase18FakeLLMClient()
    cost_accountant = FakeCostAccountant()
    fixture_path = Path("tests/integration/fixtures/intelligence_stub.json")
    orchestrator = Orchestrator(
        config_path,
        options=OrchestrationOptions(auto_response_enabled=False),
        llm_client=llm_client,
        cost_accountant=cost_accountant,
        module_overrides={
            "transport": transport,
            "primary_analyst": StubAnalyst(fixture_path, provider_id="primary"),
            "secondary_analyst": StubAnalyst(fixture_path, provider_id="secondary"),
        },
    )
    orchestrator.reconciler = StateReconciler(
        llm_client,
        orchestrator.llm_configs["primary"],
        tier="commodity",
    )
    task = asyncio.create_task(orchestrator.start())
    await asyncio.sleep(0)
    harness = Phase18PipelineHarness(
        orchestrator=orchestrator,
        transport=transport,
        llm_client=llm_client,
        cost_accountant=cost_accountant,
        task=task,
    )
    try:
        yield harness
    finally:
        await orchestrator.shutdown()
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


def empty_reconciliation_response() -> dict[str, Any]:
    return {
        "merged_promises": [],
        "status_updates": [],
        "new_inconsistencies": [],
        "missed_proposals": [],
        "merge_log": [],
    }


def reconciliation_response(
    *,
    merged_promises: list[dict[str, Any]] | None = None,
    status_updates: list[dict[str, Any]] | None = None,
    new_inconsistencies: list[dict[str, Any]] | None = None,
    missed_proposals: list[dict[str, Any]] | None = None,
    merge_log: list[str] | None = None,
) -> dict[str, Any]:
    response = empty_reconciliation_response()
    response.update(
        {
            "merged_promises": merged_promises or [],
            "status_updates": status_updates or [],
            "new_inconsistencies": new_inconsistencies or [],
            "missed_proposals": missed_proposals or [],
            "merge_log": merge_log or [],
        }
    )
    return response


def promise(
    promise_id: str,
    from_faction: str,
    to_faction: str,
    content: str,
    *,
    status: str = "pending",
    resolution: str | None = None,
) -> dict[str, Any]:
    data = {
        "promise_id": promise_id,
        "from_faction": from_faction,
        "to_faction": to_faction,
        "content": content,
        "status": status,
    }
    if resolution is not None:
        data["resolution"] = resolution
    return data


def transcript_burst(count: int = 5) -> list[InboundEvent]:
    return [
        make_event(
            f"France promises England support in sector {index}.",
            telegram_msg_id=index,
        )
        for index in range(1, count + 1)
    ]


async def inject_transcript_burst(
    transport: TestTransport,
    events: Iterable[InboundEvent],
) -> None:
    for event in events:
        await transport.inject(event)


async def test_phase18_pipeline_fixture_starts(
    phase18_pipeline: Phase18PipelineHarness,
):
    assert phase18_pipeline.orchestrator.current_round == 1
    assert phase18_pipeline.task.done() is False
    assert phase18_pipeline.orchestrator.reconciler is not None


async def test_burst_extraction_no_drops(phase18_pipeline: Phase18PipelineHarness):
    events = transcript_burst()

    await inject_transcript_burst(phase18_pipeline.transport, events)
    changes = await wait_for_state_change_count(phase18_pipeline, 5)

    stored_events = await phase18_pipeline.orchestrator.event_store.query(
        EventFilter(limit=10)
    )

    assert [row.event.content for row in stored_events] == [
        event.content for event in events
    ]
    assert [row["trigger_type"] for row in changes] == ["message"] * 5
    assert len(changes) == 5


async def test_reconciler_dedup(phase18_pipeline: Phase18PipelineHarness):
    await phase18_pipeline.transport.inject(
        make_event("France promises England support in Belgium.")
    )
    await phase18_pipeline.transport.inject(
        make_event("France promises England support for Belgium.")
    )
    await settle_phase18_pipeline()

    before = await phase18_pipeline.orchestrator.state_manager.query("promises", {})
    assert len(before) == 2

    keep_id = before[0]["promise_id"]
    remove_id = before[1]["promise_id"]
    phase18_pipeline.llm_client.reconciliation_responses = [
        reconciliation_response(
            merged_promises=[
                {
                    "keep_id": keep_id,
                    "remove_ids": [remove_id],
                    "reason": "same France-to-England Belgium support promise",
                }
            ],
            merge_log=[f"merged {remove_id} into {keep_id}"],
        )
    ]

    await phase18_pipeline.transport.inject(make_round_end_event())
    await settle_phase18_pipeline()

    after = await phase18_pipeline.orchestrator.state_manager.query("promises", {})
    assert [row["promise_id"] for row in after] == [keep_id]


async def test_reconciler_fulfillment(phase18_pipeline: Phase18PipelineHarness):
    await phase18_pipeline.transport.inject(
        make_event("France promises England support in Belgium.")
    )
    await settle_phase18_pipeline()

    before = await phase18_pipeline.orchestrator.state_manager.query("promises", {})
    assert len(before) == 1
    promise_id = before[0]["promise_id"]
    phase18_pipeline.llm_client.reconciliation_responses = [
        reconciliation_response(
            status_updates=[
                {
                    "promise_id": promise_id,
                    "new_status": "kept",
                    "resolution": "France followed through in the transcript.",
                }
            ],
            merge_log=[f"marked {promise_id} kept"],
        )
    ]

    await phase18_pipeline.transport.inject(
        make_event("France moves to support England in Belgium.")
    )
    await settle_phase18_pipeline()
    await phase18_pipeline.transport.inject(make_round_end_event())
    await settle_phase18_pipeline()

    after = await phase18_pipeline.orchestrator.state_manager.query("promises", {})
    assert after[0]["promise_id"] == promise_id
    assert after[0]["status"] == "kept"
    assert after[0]["resolution"] == "France followed through in the transcript."


async def test_reconciler_inconsistency(phase18_pipeline: Phase18PipelineHarness):
    await phase18_pipeline.transport.inject(
        make_event("France states it needs 20 million gallons this round.")
    )
    await phase18_pipeline.transport.inject(
        make_event("France now says it only needs 15 million gallons.")
    )
    await settle_phase18_pipeline()

    assert (
        await phase18_pipeline.orchestrator.state_manager.query(
            "inconsistencies",
            {},
        )
        == []
    )
    phase18_pipeline.llm_client.reconciliation_responses = [
        reconciliation_response(
            new_inconsistencies=[
                {
                    "faction_id": "France",
                    "description": "shifted stated water need from 20M to 15M",
                    "leverage_value": 0.8,
                }
            ],
            merge_log=["flagged France water-demand shift"],
        )
    ]

    await phase18_pipeline.transport.inject(make_round_end_event())
    await settle_phase18_pipeline()

    rows = await phase18_pipeline.orchestrator.state_manager.query(
        "inconsistencies",
        {},
    )
    assert len(rows) == 1
    assert rows[0]["inconsistency_id"] == "recon-France-r1"
    assert rows[0]["faction_id"] == "France"
    assert rows[0]["description"] == "shifted stated water need from 20M to 15M"
    assert rows[0]["leverage_value"] == 0.8


async def test_reconciler_missed_proposal(phase18_pipeline: Phase18PipelineHarness):
    await phase18_pipeline.transport.inject(
        make_event(
            "France offers England support in Belgium if England backs France in Spain."
        )
    )
    await settle_phase18_pipeline()

    assert await phase18_pipeline.orchestrator.state_manager.query("promises", {}) == []
    missed = promise(
        "recon-france-england-belgium-support",
        "France",
        "England",
        "support in Belgium if England backs France in Spain",
    )
    phase18_pipeline.llm_client.reconciliation_responses = [
        reconciliation_response(
            missed_proposals=[missed],
            merge_log=["added missed France-to-England proposal"],
        )
    ]

    await phase18_pipeline.transport.inject(make_round_end_event())
    await settle_phase18_pipeline()

    rows = await phase18_pipeline.orchestrator.state_manager.query("promises", {})
    assert len(rows) == 1
    assert rows[0]["promise_id"] == missed["promise_id"]
    assert rows[0]["from_faction"] == missed["from_faction"]
    assert rows[0]["to_faction"] == missed["to_faction"]
    assert rows[0]["content"] == missed["content"]
    assert rows[0]["status"] == "pending"


async def settle_phase18_pipeline() -> None:
    await asyncio.sleep(0.08)


async def wait_for_state_change_count(
    harness: Phase18PipelineHarness,
    count: int,
    *,
    timeout: float = 1.0,
) -> list[dict[str, Any]]:
    deadline = asyncio.get_running_loop().time() + timeout
    while True:
        rows = await harness.orchestrator.state_manager.query("state_change_log", {})
        if len(rows) >= count:
            return rows
        if asyncio.get_running_loop().time() >= deadline:
            return rows
        await asyncio.sleep(0.01)


def _tmp_pipeline_config(tmp_path: Path) -> Path:
    config = yaml.safe_load(
        Path("config/pipeline_test.yaml").read_text(encoding="utf-8")
    )
    config["database"]["path"] = str(tmp_path / "phase18_paths.db")
    config["message_debounce_seconds"] = 0.01
    config_path = tmp_path / "phase18_pipeline.yaml"
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    return config_path


def _schema_has_property(schema: Any, property_name: str) -> bool:
    return isinstance(schema, dict) and property_name in schema.get("properties", {})


def _system_prompt_from_kwargs(kwargs: dict[str, Any]) -> str:
    if "system_prompt" in kwargs:
        return str(kwargs["system_prompt"])
    messages = kwargs.get("messages")
    if isinstance(messages, list) and messages:
        first = messages[0]
        if isinstance(first, dict):
            return str(first.get("content", ""))
    return ""
