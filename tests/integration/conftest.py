from __future__ import annotations

import asyncio
import contextlib
from dataclasses import dataclass
from pathlib import Path

import pytest
import yaml

from orchestrator import Orchestrator
from tests.helpers.factories import FakeCostAccountant, FakeLLMClient
from tests.helpers.test_transport import TestTransport


@dataclass(frozen=True)
class PipelineHarness:
    orchestrator: Orchestrator
    transport: TestTransport
    llm_client: FakeLLMClient
    cost_accountant: FakeCostAccountant
    task: asyncio.Task[None]


@pytest.fixture
async def pipeline(tmp_path: Path) -> PipelineHarness:
    config_path = _tmp_pipeline_config(tmp_path)
    transport = TestTransport()
    llm_client = FakeLLMClient(
        [
            {
                "response": "England supports a balanced settlement.",
                "reasoning": "Keeps options open.",
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
    cost_accountant = FakeCostAccountant()
    orchestrator = Orchestrator(
        config_path,
        llm_client=llm_client,
        cost_accountant=cost_accountant,
        module_overrides={"transport": transport},
    )
    task = asyncio.create_task(orchestrator.start())
    await asyncio.sleep(0)
    harness = PipelineHarness(
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


def _tmp_pipeline_config(tmp_path: Path) -> Path:
    config = yaml.safe_load(
        Path("config/pipeline_test.yaml").read_text(encoding="utf-8")
    )
    config["database"]["path"] = str(tmp_path / "pipeline.db")
    config_path = tmp_path / "pipeline_test.yaml"
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    return config_path
