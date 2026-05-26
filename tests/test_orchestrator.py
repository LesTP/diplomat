from __future__ import annotations

import asyncio
import shutil
from pathlib import Path
from datetime import datetime, timezone

import pytest
import yaml

from modules.adversarial import AdversarialResult
from modules.extraction import ExtractionResult
from modules.generation import GenerationResult
from modules.review_gate import ReviewDecision
from modules.types import AnalysisResult, Divergence, InboundEvent, StatePatch
from modules.transport import OutboundMessage
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


class FakeEventStore:
    def __init__(self):
        self.events = []

    async def append(self, event, round_number):
        event_id = f"event-{len(self.events) + 1}"
        self.events.append((event_id, event, round_number))
        return event_id

    async def query(self, filters):
        return []


class FakeStateManager:
    def __init__(self):
        self.patches = []
        self.coaching = []
        self.rows = {
            "coaching": [],
            "intelligence": [],
            "review_gate_edits": [],
        }
        self.intelligence = []
        self.game_state = {}
        self.adversarial_reads = []
        self.consumed_marked = False

    async def get_full_state(self):
        return {"promises": []}

    async def apply_patch(self, patch, source):
        self.patches.append((patch, source))

    async def query(self, entity_type, filters=None):
        rows = list(self.rows.get(entity_type, []))
        filters = filters or {}
        return [
            row
            for row in rows
            if all(row.get(key) == value for key, value in filters.items())
        ]

    async def store_coaching(self, coaching_id, tag, content, consumed):
        row = {
            "coaching_id": coaching_id,
            "tag": tag,
            "content": content,
            "consumed": consumed,
        }
        self.coaching.append(row)
        self.rows["coaching"].append(row)

    async def store_intelligence(self, round_number, provider, analysis):
        row = {
            "round_number": round_number,
            "provider": provider,
            "analysis_json": analysis,
        }
        self.intelligence.append(row)
        self.rows["intelligence"].append(row)

    async def set_game_state(self, key, value):
        self.game_state[key] = value

    async def store_adversarial_read(self, round_number, analysis):
        self.adversarial_reads.append(
            {"round_number": round_number, "analysis": analysis}
        )

    async def mark_coaching_consumed(self):
        self.consumed_marked = True


class FakeExtractor:
    def __init__(self):
        self.calls = []

    async def extract(self, input_text, current_state, trigger_type):
        self.calls.append((input_text, current_state, trigger_type))
        return ExtractionResult(success=True, patch=StatePatch({}), error=None)


class FakeTransport:
    def __init__(self, events=None):
        self.events = list(events or [])
        self.sent = []
        self.closed = False

    async def send(self, message):
        self.sent.append(message)

    async def listen(self):
        for event in self.events:
            yield event

    async def close(self):
        self.closed = True


class FailingTransport(FakeTransport):
    def __init__(self, failures):
        super().__init__()
        self.failures = failures

    async def send(self, message):
        if message.channel == "public" and self.failures > 0:
            self.failures -= 1
            raise RuntimeError("send failed")
        await super().send(message)


class FakeAnalyst:
    def __init__(self, provider_id, success=True):
        self.provider_id = provider_id
        self.success = success
        self.calls = []

    async def analyze(self, state):
        self.calls.append(state)
        return AnalysisResult(
            success=self.success,
            provider_id=self.provider_id,
            report={"threat_level": 2, "key_leverage_points": ["Belgium"]}
            if self.success
            else None,
            error=None if self.success else "failed",
            timestamp=datetime(2026, 5, 26, tzinfo=timezone.utc),
        )


class FakePersona:
    async def get_base_prompt(self):
        return "Base persona"

    async def build_round_context(self, round_number, rounds_remaining, coaching_context):
        return f"Round {round_number}"


class FakeAssembler:
    def __init__(self):
        self.calls = []

    async def assemble(self, **kwargs):
        self.calls.append(kwargs)
        return {"context": "ready"}


class FakeGenerator:
    def __init__(self, results):
        self.results = list(results)
        self.calls = []

    async def generate(self, context):
        self.calls.append(context)
        return self.results.pop(0)


class FakeAdversarial:
    def __init__(self, result=None):
        self.result = result or AdversarialResult(
            success=True,
            analysis={"reveals": []},
            error=None,
        )
        self.calls = []

    async def read(self, draft):
        self.calls.append(draft)
        return self.result


class FakeReviewGate:
    def __init__(self, decision=None):
        self.decision = decision or ReviewDecision(
            action="approved",
            final_text="Final public message.",
            edit_notes=None,
        )
        self.calls = []

    async def submit(self, draft, adversarial, round_number):
        self.calls.append((draft, adversarial, round_number))
        return self.decision


class FakeCostAccountant:
    def __init__(self, budgets):
        self.budgets = list(budgets)
        self.checks = 0
        self.resets = []

    def available_budget(self):
        self.checks += 1
        if self.budgets:
            return self.budgets.pop(0)
        return 1

    def reset_round_budget(self, amount):
        self.resets.append(amount)


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


def _event(sender_faction="operator", content="/status"):
    return InboundEvent(
        timestamp=datetime(2026, 5, 26, tzinfo=timezone.utc),
        sender_faction=sender_faction,
        channel="coaching" if sender_faction == "operator" else "public",
        content=content,
    )


def _orchestrator(tmp_path, **overrides):
    event_store = overrides.pop("event_store", FakeEventStore())
    state_manager = overrides.pop("state_manager", FakeStateManager())
    extractor = overrides.pop("extractor", FakeExtractor())
    transport = overrides.pop("transport", FakeTransport())
    cost_accountant = overrides.pop("cost_accountant", None)
    config_path = _copy_project_config(tmp_path)
    orchestrator = Orchestrator(
        config_path,
        base_path=tmp_path,
        llm_client=FakeLLMClient(),
        cost_accountant=cost_accountant,
        module_overrides={
            "event_store": event_store,
            "state_manager": state_manager,
            "extractor": extractor,
            "transport": transport,
            **overrides,
        },
    )
    orchestrator.message_debounce_seconds = 0
    return orchestrator, event_store, state_manager, extractor, transport


def _generation(success=True, text="Draft response.", error=None):
    return GenerationResult(
        success=success,
        response_text=text if success else None,
        reasoning="Because.",
        raw_response=None,
        error=error,
    )


def _pipeline_orchestrator(tmp_path, **overrides):
    defaults = {
        "primary_analyst": FakeAnalyst("primary"),
        "secondary_analyst": FakeAnalyst("secondary"),
        "divergence": lambda primary, secondary: [
            Divergence(
                field="threat_level",
                primary_value="2",
                secondary_value="4",
                note="Disagreement.",
            )
        ],
        "persona": FakePersona(),
        "context_assembler": FakeAssembler(),
        "generator": FakeGenerator([_generation()]),
        "adversarial": FakeAdversarial(),
        "review_gate": FakeReviewGate(),
    }
    defaults.update(overrides)
    return _orchestrator(tmp_path, **defaults)


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


@pytest.mark.asyncio
async def test_start_listens_and_shutdown_closes_transport(tmp_path):
    transport = FakeTransport([_event(content="/status")])
    orchestrator, event_store, _state_manager, _extractor, _transport = _orchestrator(
        tmp_path,
        transport=transport,
    )

    await orchestrator.start()
    await orchestrator.shutdown()

    assert event_store.events[0][1].content == "/status"
    assert transport.sent[0].channel == "coaching"
    assert "Status" in transport.sent[0].content
    assert transport.closed is True


@pytest.mark.asyncio
async def test_operator_command_routes_to_command_handler(tmp_path):
    orchestrator, _event_store, _state_manager, _extractor, transport = _orchestrator(
        tmp_path
    )

    await orchestrator.process_event(_event(content="/ledger"))

    assert transport.sent == [
        OutboundMessage(
            content="Ledger\nPer-round budget: $1.00\nSession budget: $10.00",
            channel="coaching",
        )
    ]


@pytest.mark.asyncio
async def test_operator_intel_runs_extraction_and_applies_patch(tmp_path):
    orchestrator, _event_store, state_manager, extractor, _transport = _orchestrator(
        tmp_path
    )

    await orchestrator.process_event(_event(content="INTEL: France broke a promise."))

    assert extractor.calls == [
        ("France broke a promise.", {"promises": []}, "intel_correction")
    ]
    assert len(state_manager.patches) == 1
    assert state_manager.patches[0][1].trigger_type == "intel_correction"
    assert state_manager.patches[0][1].trigger_ref == "event-1"


@pytest.mark.asyncio
async def test_operator_coaching_is_stored_unconsumed(tmp_path):
    orchestrator, _event_store, state_manager, _extractor, _transport = _orchestrator(
        tmp_path
    )

    await orchestrator.process_event(_event(content="WATCH: Germany is stalling."))

    assert state_manager.coaching[0]["tag"] == "WATCH"
    assert state_manager.coaching[0]["content"] == "Germany is stalling."
    assert state_manager.coaching[0]["consumed"] is False


@pytest.mark.asyncio
async def test_game_message_debounce_cancels_and_reschedules(tmp_path):
    orchestrator, _event_store, state_manager, extractor, _transport = _orchestrator(
        tmp_path
    )
    orchestrator.message_debounce_seconds = 0.01

    await orchestrator.process_event(_event(sender_faction="france", content="first"))
    first_task = orchestrator._debounce_task
    await orchestrator.process_event(_event(sender_faction="germany", content="second"))
    await asyncio.sleep(0)

    assert first_task.cancelled() or first_task.done()
    await orchestrator._debounce_task
    assert extractor.calls == [("second", {"promises": []}, "message")]
    assert state_manager.patches[0][1].trigger_type == "message"
    assert state_manager.patches[0][1].trigger_ref == "event-2"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("command", "expected"),
    [
        ("/status", "Status\nFaction: england\nRound: 1"),
        ("/state", "State\n{"),
        ("/ledger", "Ledger\nPer-round budget: $1.00"),
        ("/intel", "Intelligence\n"),
        ("/divergences", "Divergences\n"),
        ("/edits", "Review Edits\n"),
    ],
)
async def test_command_handler_reply_formats(tmp_path, command, expected):
    state_manager = FakeStateManager()
    state_manager.rows["intelligence"] = [
        {
            "id": 1,
            "analysis_json": '{"divergences": [{"field": "threat_level"}]}',
        }
    ]
    state_manager.rows["review_gate_edits"] = [
        {"id": 1, "decision": "edited", "edit_text": "Softer."}
    ]
    orchestrator, _event_store, _state_manager, _extractor, transport = _orchestrator(
        tmp_path,
        state_manager=state_manager,
    )

    await orchestrator.process_event(_event(content=command))

    assert transport.sent
    assert transport.sent[0].channel == "coaching"
    assert transport.sent[0].content.startswith(expected)


@pytest.mark.asyncio
async def test_round_boundary_signal_detection_stores_analysis(tmp_path):
    orchestrator, _event_store, state_manager, _extractor, _transport = (
        _pipeline_orchestrator(tmp_path)
    )

    await orchestrator.process_event(_event(sender_faction="france", content="ROUND 2"))

    assert orchestrator.current_round == 2
    assert state_manager.game_state["round_number"] == "2"
    assert state_manager.intelligence[0]["round_number"] == 1
    assert state_manager.intelligence[0]["analysis_json"]["primary"]["success"] is True
    assert state_manager.intelligence[0]["analysis_json"]["divergences"][0]["field"] == (
        "threat_level"
    )


@pytest.mark.asyncio
async def test_round_boundary_time_mode(tmp_path):
    config_path = _copy_project_config(tmp_path)
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    config["round_detection"] = {"mode": "time", "interval_seconds": 0.01}
    config_path.write_text(yaml.safe_dump(config), encoding="utf-8")
    state_manager = FakeStateManager()
    transport = FakeTransport()
    orchestrator = Orchestrator(
        config_path,
        base_path=tmp_path,
        llm_client=FakeLLMClient(),
        module_overrides={
            "event_store": FakeEventStore(),
            "state_manager": state_manager,
            "extractor": FakeExtractor(),
            "transport": transport,
            "primary_analyst": FakeAnalyst("primary"),
            "secondary_analyst": FakeAnalyst("secondary"),
            "divergence": lambda primary, secondary: [],
            "persona": FakePersona(),
            "context_assembler": FakeAssembler(),
            "generator": FakeGenerator([_generation()]),
            "adversarial": FakeAdversarial(),
            "review_gate": FakeReviewGate(),
        },
    )

    orchestrator._running = True
    task = asyncio.create_task(orchestrator._time_round_loop())
    await asyncio.sleep(0.02)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert orchestrator.current_round >= 2
    assert state_manager.intelligence


@pytest.mark.asyncio
async def test_primary_analyst_failure_alerts_and_skips_round_analysis(tmp_path):
    orchestrator, _event_store, state_manager, _extractor, transport = (
        _pipeline_orchestrator(
            tmp_path,
            primary_analyst=FakeAnalyst("primary", success=False),
        )
    )

    await orchestrator.handle_round_boundary()

    assert orchestrator.current_round == 1
    assert state_manager.intelligence == []
    assert transport.sent[0].channel == "coaching"
    assert "Primary analyst failed" in transport.sent[0].content


@pytest.mark.asyncio
async def test_secondary_analyst_failure_proceeds_with_primary_only(tmp_path):
    orchestrator, _event_store, state_manager, _extractor, transport = (
        _pipeline_orchestrator(
            tmp_path,
            secondary_analyst=FakeAnalyst("secondary", success=False),
        )
    )

    await orchestrator.handle_round_boundary()

    assert orchestrator.current_round == 2
    assert state_manager.intelligence[0]["analysis_json"]["secondary"]["success"] is False
    assert state_manager.intelligence[0]["analysis_json"]["divergences"] == []
    assert "Secondary analyst failed" in transport.sent[0].content


@pytest.mark.asyncio
async def test_happy_path_response_pipeline_with_fakes(tmp_path):
    orchestrator, _event_store, state_manager, _extractor, transport = (
        _pipeline_orchestrator(tmp_path)
    )

    sent = await orchestrator.run_response_pipeline()

    assert sent is True
    assert transport.sent[-1] == OutboundMessage(
        content="Final public message.",
        channel="public",
    )
    assert state_manager.adversarial_reads
    assert state_manager.consumed_marked is True


@pytest.mark.asyncio
async def test_direct_address_triggers_response_pipeline(tmp_path):
    orchestrator, _event_store, _state_manager, _extractor, transport = (
        _pipeline_orchestrator(tmp_path)
    )

    await orchestrator.process_event(
        _event(sender_faction="france", content="England, can we talk?")
    )

    assert transport.sent[-1].channel == "public"


@pytest.mark.asyncio
async def test_preview_command_triggers_response_pipeline(tmp_path):
    orchestrator, _event_store, _state_manager, _extractor, transport = (
        _pipeline_orchestrator(tmp_path)
    )

    await orchestrator.process_event(_event(content="/preview"))

    assert transport.sent[-1].channel == "public"


@pytest.mark.asyncio
async def test_generation_failure_retries_once(tmp_path):
    generator = FakeGenerator(
        [_generation(success=False, error="provider down"), _generation(text="Retry")]
    )
    orchestrator, _event_store, _state_manager, _extractor, transport = (
        _pipeline_orchestrator(tmp_path, generator=generator)
    )

    sent = await orchestrator.run_response_pipeline()

    assert sent is True
    assert len(generator.calls) == 2
    assert transport.sent[-1].channel == "public"


@pytest.mark.asyncio
async def test_adversarial_failure_passed_to_review_gate(tmp_path):
    adversarial_result = AdversarialResult(
        success=False,
        analysis=None,
        error="bad json",
    )
    adversarial = FakeAdversarial(adversarial_result)
    review_gate = FakeReviewGate()
    orchestrator, _event_store, _state_manager, _extractor, transport = (
        _pipeline_orchestrator(
            tmp_path,
            adversarial=adversarial,
            review_gate=review_gate,
        )
    )

    sent = await orchestrator.run_response_pipeline()

    assert sent is True
    assert review_gate.calls[0][1] == adversarial_result
    assert any(message.channel == "coaching" for message in transport.sent)


@pytest.mark.asyncio
async def test_review_gate_block_prevents_send(tmp_path):
    review_gate = FakeReviewGate(
        ReviewDecision(action="blocked", final_text=None, edit_notes="No.")
    )
    orchestrator, _event_store, _state_manager, _extractor, transport = (
        _pipeline_orchestrator(tmp_path, review_gate=review_gate)
    )

    sent = await orchestrator.run_response_pipeline()

    assert sent is False
    assert [message for message in transport.sent if message.channel == "public"] == []


@pytest.mark.asyncio
async def test_transport_send_retries_three_times(tmp_path):
    transport = FailingTransport(failures=2)
    orchestrator, _event_store, _state_manager, _extractor, _transport = (
        _pipeline_orchestrator(tmp_path, transport=transport)
    )

    sent = await orchestrator.run_response_pipeline()

    assert sent is True
    assert transport.sent[-1].channel == "public"


@pytest.mark.asyncio
async def test_cost_budget_blocks_generation_and_alerts_operator(tmp_path):
    cost_accountant = FakeCostAccountant([0])
    generator = FakeGenerator([_generation()])
    orchestrator, _event_store, _state_manager, _extractor, transport = (
        _pipeline_orchestrator(
            tmp_path,
            cost_accountant=cost_accountant,
            generator=generator,
        )
    )

    sent = await orchestrator.run_response_pipeline()

    assert sent is False
    assert generator.calls == []
    assert "Cost budget exceeded before generation" in transport.sent[0].content


@pytest.mark.asyncio
async def test_cost_budget_resets_per_round(tmp_path):
    cost_accountant = FakeCostAccountant([1, 1])
    orchestrator, _event_store, _state_manager, _extractor, _transport = (
        _pipeline_orchestrator(tmp_path, cost_accountant=cost_accountant)
    )

    await orchestrator.handle_round_boundary()

    assert cost_accountant.resets == [1.0, 1.0]
    assert cost_accountant.checks == 2
