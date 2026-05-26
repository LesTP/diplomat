from __future__ import annotations

import shutil
from pathlib import Path

import pytest
import yaml

from modules.analyst import LLMAnalyst
from modules.context_assembler import DefaultContextAssembler
from modules.coaching import TaggedCoachingParser
from modules.event_store import SQLiteEventStore
from modules.extraction import RuleBasedExtractor
from modules.generation import LLMGenerator
from modules.persona import FileBasedPersona
from modules.review_gate import AutoApproveReviewGate
from modules.state_manager import SQLiteStateManager
from orchestrator import Orchestrator, PipelineConfigError
from registry import REGISTRY, RegistryLookupError, resolve_class


class FakeLLMClient:
    async def complete(self, **kwargs):
        return "{}"


class FakeTelegramClient:
    async def send_message(self, chat_id, content):
        return None

    async def get_next_update(self):
        return None


def _copy_project_config(tmp_path: Path) -> Path:
    for relative in (
        "config/coaching_routes.yaml",
        "config/faction_prompt.txt",
        "config/prompts/state_updater.txt",
        "config/prompts/analyst.txt",
        "config/prompts/generation.txt",
        "config/prompts/adversarial.txt",
        "config/schemas/state_patch.json",
        "config/schemas/intelligence.json",
        "config/schemas/adversarial.json",
    ):
        source = Path(relative)
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)

    config = yaml.safe_load(Path("config/pipeline.yaml").read_text(encoding="utf-8"))
    config["database"]["path"] = "data/test.db"
    config["transport"]["class"] = "CLITransport"
    config["modules"]["transport"]["class"] = "CLITransport"
    config_path = tmp_path / "config/pipeline.yaml"
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    return config_path


def test_successful_instantiation_with_fakes(tmp_path, monkeypatch):
    config_path = _copy_project_config(tmp_path)
    monkeypatch.setenv("OPENAI_API_KEY", "openai-key")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "anthropic-key")

    orchestrator = Orchestrator(
        config_path,
        base_path=tmp_path,
        llm_client=FakeLLMClient(),
        telegram_client=FakeTelegramClient(),
    )

    assert orchestrator.faction_id == "england"
    assert orchestrator.db_path == tmp_path / "data/test.db"
    assert orchestrator.event_store.__class__ is SQLiteEventStore
    assert orchestrator.state_manager.__class__ is SQLiteStateManager
    assert orchestrator.extractor.__class__ is RuleBasedExtractor
    assert orchestrator.coaching_parser.__class__ is TaggedCoachingParser
    assert orchestrator.persona.__class__ is FileBasedPersona
    assert orchestrator.primary_analyst.__class__ is LLMAnalyst
    assert orchestrator.secondary_analyst.__class__ is LLMAnalyst
    assert orchestrator.context_assembler.__class__ is DefaultContextAssembler
    assert orchestrator.generator.__class__ is LLMGenerator
    assert orchestrator.review_gate.__class__ is AutoApproveReviewGate
    assert "generation" in orchestrator.prompts
    assert (tmp_path / "data/test.db").exists()
    assert (tmp_path / "data/test.db-wal").exists()


def test_bad_config_path_raises():
    with pytest.raises(PipelineConfigError, match="Unable to read pipeline config"):
        Orchestrator("/does/not/exist.yaml")


def test_missing_required_key_raises(tmp_path):
    config_path = _copy_project_config(tmp_path)
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    del config["cost"]
    config_path.write_text(yaml.safe_dump(config), encoding="utf-8")

    with pytest.raises(PipelineConfigError, match="missing required key: cost"):
        Orchestrator(config_path, base_path=tmp_path)


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("SQLiteEventStore", "SQLiteEventStore"),
        ("SQLiteStateManager", "SQLiteStateManager"),
        ("RuleBasedExtractor", "RuleBasedExtractor"),
        ("OpenAIStructuredExtractor", "OpenAIStructuredExtractor"),
        ("TaggedCoachingParser", "TaggedCoachingParser"),
        ("CLITransport", "CLITransport"),
        ("TelegramBotTransport", "TelegramBotTransport"),
        ("FileBasedPersona", "FileBasedPersona"),
        ("LLMAnalyst", "LLMAnalyst"),
        ("DefaultContextAssembler", "DefaultContextAssembler"),
        ("LLMGenerator", "LLMGenerator"),
        ("LLMAdversarialReader", "LLMAdversarialReader"),
        ("AutoApproveReviewGate", "AutoApproveReviewGate"),
        ("TelegramReviewGate", "TelegramReviewGate"),
        ("modules.analyst.divergence.compare", "compare"),
    ],
)
def test_registry_lookup_for_each_module_type(name, expected):
    assert name in REGISTRY
    assert resolve_class(name).__name__ == expected


def test_registry_lookup_unknown_target_raises():
    with pytest.raises(RegistryLookupError, match="Unable to resolve"):
        resolve_class("missing.module.Target")
