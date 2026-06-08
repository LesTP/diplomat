# AI Diplomat — Testing and Tuning Guide
**Version 0.8 | Updated 2026-06-02 — Phase 28 coached self-play + near-miss diagnostic**

---

## 1. Overview

This document covers the testing strategy, tuning workflow, and implementation changes required to make the AI Diplomat system verifiable before deployment.

The system has two distinct testing challenges. The first is standard software correctness: do the modules behave as specified? The second is harder: does the system produce good diplomatic behavior? These require different approaches. Correctness is testable with standard assertions. Quality requires scenario libraries, LLM-as-judge evaluation, and multi-agent simulation.

The modular architecture in the main spec was partly designed with testability in mind. The `CLITransport`, `AutoApproveReviewGate`, and `RuleBasedExtractor` implementations exist specifically to enable testing without live infrastructure.

> **Toolkit dependency:** All LLM calls in production go through `toolkit/llm_client` via `ToolkitLLMAdapter` (in `src/adapters.py`). All Telegram I/O goes through `toolkit/telegram_client`. Cost governance uses `toolkit/cost_accountant` via `DiplomatCostGate` (in `src/adapters.py`). No direct provider SDK imports (`anthropic`, `openai`) anywhere — including test infrastructure. Module-level tests use dependency-injected fakes that match the adapter interface (plain dicts, plain strings).

### Testing Layers

| Layer | What it tests | Speed | Cost | When to run | Status |
|---|---|---|---|---|---|
| 1 — Unit | Module correctness | Fast | Free | Every commit | **Complete** — 25 test files |
| 2 — Prompt regression | Prompt quality and constraint compliance | Slow | Low | Before prompt changes go live | **Complete** — infrastructure + 6 starter scenarios |
| 3 — Pipeline integration | Cross-module behavior, failure handling, transcript replay, Phase 18 reconciliation paths | Medium | Free | Before deployments | **Complete** — 5 test files |
| — Live smoke test | Real Telegram + real LLM end-to-end | Manual | Low | Before first game | **Complete** |
| 4 — Multi-agent self-play | Game-level behavior, persona coherence | Slow | Medium-high | Final validation before real game | **Operational** — 10 simulation runs, ongoing tuning |

**Total: 346 tests passing** (Phase 28).

### What Already Exists

| Artifact | Location | Notes |
|---|---|---|
| 25 unit test files | `tests/test_*.py` | One per module + cross-cutting, 346 tests total |
| Pipeline integration tests | `tests/integration/` | 5 test files: pipeline flow, failure handling, replay, Phase 18 paths, pipeline fixture |
| Transcript fixtures | `tests/integration/fixtures/transcripts/` | cooperative_3round.json, betrayal_arc.json |
| CLITransport | `src/modules/transport/__init__.py` | JSON reader/writer, no inject() |
| TestTransport | `tests/helpers/test_transport.py` | Queue-backed event injection and output capture |
| AutoApproveReviewGate | `src/modules/review_gate/__init__.py` | Approves all drafts |
| RuleBasedExtractor | `src/modules/extraction/__init__.py` | Regex-based promise/coalition/inconsistency detection |
| Pipeline config | `config/pipeline.yaml` | Production configuration |
| Smoke pipeline config | `config/pipeline_smoke.yaml` | OperatorReviewGate-backed smoke configuration |
| Test pipeline config | `config/pipeline_test.yaml` | Fake-backed integration configuration |
| Fake LLM clients | `tests/self_play/fake_llm_client.py`, `tests/helpers/factories.py`, `tests/integration/test_phase18_paths.py` | Shared and per-test fakes for dependency injection |
| Prompt regression runner | `tests/prompt_regression/runner.py` | Scenario loader, structural checks, LLM-as-judge checks, CLI |
| Prompt regression scenarios | `tests/prompt_regression/scenarios/` | 4 extraction scenarios + 2 generation scenarios |
| Self-play infrastructure | `tests/self_play/` | GameEnvironment, simulation runner, coached game runner, analysis, scenario compiler, verification tools |
| Scenario verification | `tests/self_play/verify_scenario_optimum.py`, `verify_dryrun.py` | Pareto frontier enumeration and dry-run plumbing checks |
| Provider probing | `tests/self_play/probe_providers.py` | Pre-flight API key + model verification (~$0.001) |
| Structured logging config | `config/pipeline.yaml`, `config/pipeline_smoke.yaml`, `src/logging_config.py` | `logging.level` / `logging.format`, with `DIPLOMAT_LOG_LEVEL` override |
| Extraction examples | `config/examples/extraction_examples.json` | Few-shot examples for LLM extraction (Phase 24.5) |

---

## 2. Test Infrastructure Reference

The following test infrastructure supports Layers 2–4. All items are implemented. Code samples below document the design patterns for reference; the actual implementations may differ in minor details.

### 2.1 TestTransport — Event Injection and Output Capture

The integration and self-play layers need to push synthetic events into the pipeline and capture outbound messages. `CLITransport` is designed for stdio and doesn't expose an injection point. Rather than modifying the Transport ABC, build a `TestTransport` helper that implements `send()`/`listen()` directly using an async queue:

```python
# tests/helpers/test_transport.py

import asyncio
from typing import AsyncIterator

from modules.transport import OutboundMessage
from modules.types import InboundEvent


class TestTransport:
    """Test transport with event injection and output capture."""

    def __init__(self) -> None:
        self._queue: asyncio.Queue[InboundEvent | None] = asyncio.Queue()
        self._output: list[OutboundMessage] = []

    async def inject(self, event: InboundEvent) -> None:
        """Push a synthetic event into the listen stream."""
        await self._queue.put(event)

    async def stop_listening(self) -> None:
        """Signal the listen loop to stop."""
        await self._queue.put(None)

    async def send(self, message: OutboundMessage) -> None:
        self._output.append(message)

    async def listen(self) -> AsyncIterator[InboundEvent]:
        while True:
            event = await self._queue.get()
            if event is None:
                return
            yield event

    def get_output(self) -> list[OutboundMessage]:
        return self._output.copy()

    def clear_output(self) -> None:
        self._output.clear()
```

Pass `TestTransport` to the Orchestrator via `module_overrides`:

```python
transport = TestTransport()
orch = Orchestrator(
    config_path="config/pipeline_test.yaml",
    module_overrides={"transport": transport},
    base_path=project_root,
)
```

### 2.2 Storage — Use `tmp_path`, Not `:memory:`

`SQLiteStateManager` creates a new connection per operation (`_connect()`). With `:memory:`, each connection creates a fresh empty database — silently breaking all state persistence.

**Use pytest's `tmp_path` fixture instead.** This is already the pattern used in all existing unit tests:

```python
@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "test.db"
```

The test pipeline config should reference a `tmp_path`-generated database path, not `:memory:`.

### 2.3 New Test Implementations

**`StubAnalyst`** — returns a structurally valid `AnalysisResult` from a fixture file. Needed for integration tests that exercise the pipeline without real LLM calls.

```python
# src/modules/analyst/stub.py (or tests/helpers/stub_analyst.py)

import json
from datetime import datetime, timezone
from pathlib import Path

from modules.types import AnalysisResult


class StubAnalyst:
    def __init__(self, fixture_path: str | Path, provider_id: str = "stub") -> None:
        self._fixture = json.loads(Path(fixture_path).read_text(encoding="utf-8"))
        self._provider_id = provider_id

    async def analyze(self, state: dict) -> AnalysisResult:
        return AnalysisResult(
            success=True,
            provider_id=self._provider_id,
            report=self._fixture,
            error=None,
            timestamp=datetime.now(timezone.utc),
        )
```

Register in `src/registry.py` if loading from `pipeline_test.yaml`, or pass via `module_overrides` in test fixtures.

**Already implemented (no changes needed):**
- `CLITransport` — `src/modules/transport/__init__.py`
- `AutoApproveReviewGate` — `src/modules/review_gate/__init__.py`
- `RuleBasedExtractor` — `src/modules/extraction/__init__.py`

### 2.4 Directory Structure

```
diplomat/
├── src/
│   ├── adapters.py                    # ToolkitLLMAdapter, DiplomatCostGate
│   ├── orchestrator.py                # Compat factory → EventDrivenFlow(Pipeline(core))
│   ├── pipeline.py                    # Pipeline interface (Phase 22)
│   ├── main.py                        # Production entry point
│   ├── registry.py                    # Module registry
│   ├── logging_config.py              # diplomat.* structured logging (Phase 26)
│   ├── flows/
│   │   ├── event_driven.py            # Production Telegram/CLI flow
│   │   └── round_stepped.py           # Self-play round-by-round flow
│   ├── modules/
│   │   ├── adversarial/               # LLMAdversarialReader
│   │   ├── analyst/                   # LLMAnalyst + divergence.py
│   │   ├── coaching/                  # TaggedCoachingParser
│   │   ├── context_assembler/         # DefaultContextAssembler
│   │   ├── event_store/               # SQLiteEventStore
│   │   ├── extraction/                # LLM + RuleBasedExtractor
│   │   ├── generation/                # LLMGenerator
│   │   ├── persona/                   # FileBasedPersona (hot-reload)
│   │   ├── reconciliation/            # StateReconciler (Phase 18)
│   │   ├── review_gate/               # Auto/Telegram review gates
│   │   ├── state_manager/             # SQLiteStateManager
│   │   ├── transport/                 # CLI/TelegramBot transports
│   │   └── types.py                   # Shared domain types
│   └── tools/
│       └── scenario_compiler.py       # Narrative → scored personas
├── tests/
│   ├── conftest.py                    # diplomat.* logger suppression
│   ├── test_*.py                      # 25 unit test files (Layer 1)
│   ├── helpers/                       # Shared test infrastructure
│   │   ├── test_transport.py          # TestTransport
│   │   ├── stub_analyst.py           # StubAnalyst (via module_overrides)
│   │   └── factories.py              # InboundEvent/patch factories
│   ├── integration/                   # Layer 3
│   │   ├── conftest.py
│   │   ├── test_pipeline_flow.py
│   │   ├── test_pipeline_fixture.py
│   │   ├── test_failure_handling.py
│   │   ├── test_replay.py
│   │   ├── test_phase18_paths.py
│   │   └── fixtures/
│   │       ├── intelligence_stub.json
│   │       ├── test_persona.txt
│   │       └── transcripts/
│   ├── prompt_regression/             # Layer 2
│   │   ├── runner.py
│   │   ├── judge.py
│   │   ├── types.py
│   │   └── scenarios/
│   │       ├── extraction/            # 4 scenarios
│   │       └── generation/            # 2 scenarios
│   └── self_play/                     # Layer 4
│       ├── game_environment.py        # GameEnvironment + LoggingLLMClient
│       ├── run_simulation.py          # CLI simulation runner
│       ├── coached_game.py            # Telegram-coached self-play (Phase 28)
│       ├── analysis.py                # Post-game report + process signatures + near-miss
│       ├── fake_llm_client.py         # Deterministic LLM for tests
│       ├── scenario.py                # Legacy scenario definitions
│       ├── probe_providers.py         # Pre-flight API key verification
│       ├── verify_dryrun.py           # Dry-run plumbing verification
│       ├── verify_scenario_optimum.py # Pareto frontier enumeration
│       ├── personas/                  # Pre-built persona files
│       ├── scenarios/                 # Scenario .md files + compiled variants
│       └── results/                   # Run JSON + log output
├── config/
│   ├── pipeline.yaml                  # Production config
│   ├── pipeline_smoke.yaml            # Smoke config (OperatorReviewGate)
│   ├── pipeline_test.yaml             # Integration test config
│   ├── coaching_routes.yaml           # Tag → routing rules
│   ├── faction_prompt.txt             # Production persona
│   ├── diplomat.service               # Systemd unit (non-container hosts)
│   ├── examples/
│   │   └── extraction_examples.json   # Few-shot examples (Phase 24.5)
│   ├── prompts/                       # Module prompt files
│   │   ├── state_updater.txt
│   │   ├── analyst.txt
│   │   ├── generation.txt
│   │   └── adversarial.txt
│   └── schemas/                       # JSON schemas for structured output
│       ├── state_patch.json
│       ├── intelligence.json
│       └── adversarial.json
└── tools/                             # CLI tools + deployment
    ├── service.sh                     # tmux-backed bot lifecycle (Phase 25)
    ├── backfill_scoring_metrics.py    # Backfill no-deal-aware metrics (Phase 27)
    ├── backfill_pareto.py             # Backfill Pareto efficiency
    ├── recompile_batnas.py            # Recompile BATNAs for existing scenarios
    ├── inspect_ledger.py              # Cost ledger inspection
    ├── inspect_dryrun.py              # Dry-run output inspection
    └── digest_logs.py                 # Log file digestion
```

### 2.5 Test Pipeline Configuration

`config/pipeline_test.yaml` uses the real schema format with test implementations substituted. The `llm_providers` use `provider: fake` with fake model names — no real API keys needed. Integration tests override specific modules at fixture level via `module_overrides`.

```yaml
faction_id: england

database:
  path: data/pipeline_test.db   # overridden by fixture in integration tests

transport:
  type: cli
  class: CLITransport
  public_channel_id_env: DIPLOMAT_PUBLIC_CHANNEL_ID
  coaching_channel_id_env: DIPLOMAT_COACHING_CHANNEL_ID
  operator_user_ids_env: DIPLOMAT_OPERATOR_USER_IDS

llm_providers:
  primary:
    provider: fake
    models:
      quality: fake-quality
      default: fake-default
      commodity: fake-commodity
    api_key_env: FAKE_OPENAI_API_KEY
  secondary:
    provider: fake
    models:
      quality: fake-quality
      default: fake-default
      commodity: fake-commodity
    api_key_env: FAKE_ANTHROPIC_API_KEY

modules:
  event_store:
    class: SQLiteEventStore
  state_manager:
    class: SQLiteStateManager
  extractor:
    class: RuleBasedExtractor
    provider: primary
  coaching_parser:
    class: TaggedCoachingParser
  transport:
    class: CLITransport
  persona:
    class: FileBasedPersona
  primary_analyst:
    class: LLMAnalyst              # overridden to StubAnalyst in fixtures
    provider: primary
    tier: quality
  secondary_analyst:
    class: LLMAnalyst              # overridden to StubAnalyst in fixtures
    provider: secondary
    tier: quality
  divergence:
    class: modules.analyst.divergence.compare
  context_assembler:
    class: DefaultContextAssembler
  generator:
    class: LLMGenerator
    provider: primary
    tier: quality
    max_tokens: 1024
  adversarial:
    class: LLMAdversarialReader
    provider: secondary
    tier: quality
  review_gate:
    class: AutoApproveReviewGate

cost:
  per_round_budget_usd: 1.00
  session_budget_usd: 10.00

round_detection:
  mode: signal
  pattern: "^\\[ROUND END\\]$"

message_debounce_seconds: 0.01

feature_flags:
  adversarial:
    enabled: true
  review_gate:
    enabled: true

paths:
  coaching_routes: config/coaching_routes.yaml
  faction_prompt: tests/integration/fixtures/test_persona.txt
  prompts:
    state_updater: config/prompts/state_updater.txt
    analyst: config/prompts/analyst.txt
    generation: config/prompts/generation.txt
    adversarial: config/prompts/adversarial.txt
  schemas:
    state_patch: config/schemas/state_patch.json
    intelligence: config/schemas/intelligence.json
    adversarial: config/schemas/adversarial.json
```

### 2.6 Structured Logging in Tests

Production logging is configured by `src/logging_config.py` from
`logging.level` and `logging.format` in the active pipeline config. Operators
can temporarily override the level with `DIPLOMAT_LOG_LEVEL=DEBUG` without
editing config.

Tests keep `diplomat.*` loggers quiet by default via `tests/conftest.py`.
Logging-specific tests opt into INFO with `caplog`, including unit coverage
for `event.routed` / `extraction.scheduled` and Layer 3 coverage in
`tests/integration/test_phase18_paths.py` that asserts `event.routed`,
`extraction.scheduled`, and `extraction.complete` are visible from a real
pipeline fixture event.

**Note:** For free integration tests (Layer 3), pass `StubAnalyst` and a fake LLM client via `module_overrides` to avoid real API calls. The YAML config above is the starting point — tests override specific modules at fixture level.

---

## 3. Layer 1 — Unit Tests ✓ COMPLETE

Unit tests cover module correctness in isolation. No real API calls. Run on every commit. Complete in under 30 seconds.

**Status:** 25 unit test files covering all modules and cross-cutting infrastructure.

| Test file | Module | Tests |
|---|---|---|
| `tests/test_event_store.py` | Event Store | SQLiteEventStore append, query, round tagging |
| `tests/test_state_manager.py` | State Manager | apply_patch, schema validation, audit log, CRUD, new persistence methods |
| `tests/test_extraction.py` | Extraction | RuleBasedExtractor, OpenAIStructuredExtractor, schema enforcement |
| `tests/test_coaching.py` | Coaching | Tag parsing, command parsing, route validation |
| `tests/test_transport.py` | Transport | CLITransport, TelegramBotTransport, channel validation |
| `tests/test_persona.py` | Persona | Hot-reload, round context, section stripping |
| `tests/test_analyst.py` | Analyst | LLMAnalyst, divergence comparison |
| `tests/test_context_assembler.py` | Context Assembler | Section ordering, coaching filtering, metadata |
| `tests/test_generation.py` | Generation | JSON parsing, plain-text mode, failure handling |
| `tests/test_review_gate.py` | Review Gate | Auto-approve, Telegram workflow, timeout |
| `tests/test_adversarial.py` | Adversarial | Schema validation, failure handling |
| `tests/test_orchestrator.py` | Orchestrator | Config, event loop, routing, round management, cost gates |
| `tests/test_adapters.py` | Adapters | ToolkitLLMAdapter, DiplomatCostGate wiring |
| `tests/test_reconciliation.py` | Reconciliation | StateReconciler dedup, fulfillment, inconsistency |
| `tests/test_pipeline.py` | Pipeline | Pipeline interface contract (Phase 22) |
| `tests/test_flows.py` | Flows | EventDrivenFlow, RoundSteppedFlow (Phase 22) |
| `tests/test_main.py` | Main | Production entry point wiring |
| `tests/test_coached_game.py` | Coached Game | Coached self-play harness dry-run + wiring (Phase 28) |
| `tests/test_self_play.py` | Self-Play | GameEnvironment, scoring, Pareto efficiency |
| `tests/test_self_play_near_miss.py` | Near-Miss | `compute_near_miss()` diagnostic on Run 9/10 fixtures (Phase 28) |
| `tests/test_scenario_compiler.py` | Scenario Compiler | Narrative → persona compilation |
| `tests/test_prompt_regression_runner.py` | PR Runner | Scenario loading, property checking, report formatting |
| `tests/test_prompt_regression_judge.py` | PR Judge | LLM-as-judge verdict parsing |
| `tests/test_prompt_regression_types.py` | PR Types | Dataclass contracts for prompt regression |
| `tests/test_service_sh.py` | Service | `tools/service.sh` tmux lifecycle shell smoke (Phase 25) |

**Run:**
```bash
python3 -m pytest tests/ -q
```

### Layer 1 Scenario Coverage (reference)

The following test patterns are already covered. Listed here for reference — no additional work needed.

**Coaching:** INTEL routing to state_updater, PRIORITY/CONSTRAINT/WATCH/TONE routing to coaching queue, FREE fallback, slash command parsing, `/edit:` argument parsing, case-insensitive tags.

**State Manager:** apply_patch creates promises/coalitions/factions/inconsistencies, audit log written with trigger_type/trigger_ref, schema validation rejects invalid patches, credibility_score stored as absolute value, store_coaching/store_intelligence/set_game_state/store_adversarial_read/mark_coaching_consumed (Phase 12).

**Divergence:** Threat-level divergence flagged when delta > threshold, same level produces no divergence, missing leverage items flagged, coalition stability mismatch flagged.

**Context Assembler:** INTEL coaching excluded, PRIORITY included, review gate mode requests JSON keys (`response`/`reasoning`), divergences formatted when present, empty coaching produces default message.

---

## 4. Layer 2 — Prompt Regression Tests

Prompt regression tests verify that specific inputs produce outputs with required properties. They call real APIs via the adapter layer. Run before any prompt change goes live.

> **Extraction few-shot examples** live in `config/examples/extraction_examples.json` (as of Phase 24.5 — previously a Python constant `_EXTRACTION_EXAMPLES` in `src/modules/extraction/__init__.py`). Tuning the example set is a config-only change. Path is configurable via `pipeline.yaml` `paths.examples.extraction`.

### 4.1 Scenario Format

Each scenario is a JSON file:

```json
{
  "scenario_id": "extraction.promise_explicit",
  "module": "extraction",
  "description": "Explicit promise should create a pending promise entry",
  "input": {
    "text": "Faction Cartographers: We formally commit to supporting your infrastructure proposal in round 4.",
    "current_state": {},
    "trigger_type": "message"
  },
  "expected_properties": [
    {
      "type": "json_path_exists",
      "path": "patch.data.promises[0]",
      "description": "A promise entry should be created"
    },
    {
      "type": "json_path_equals",
      "path": "patch.data.promises[0].status",
      "value": "pending",
      "description": "Promise status should be pending"
    },
    {
      "type": "json_path_equals",
      "path": "patch.data.promises[0].from_faction",
      "value": "cartographers",
      "description": "Promise from faction correctly identified"
    }
  ]
}
```

For qualitative properties that cannot be asserted structurally, add an `llm_judge` block:

```json
{
  "scenario_id": "generation.constraint_respect",
  "module": "generation",
  "description": "CONSTRAINT on faction Z alliance must be respected",
  "input": {
    "context": {
      "system_prompt": "You are England. Respect all operator constraints.",
      "user_prompt": "CONSTRAINT: Do not accept any alliance with France.\n\nFrance offers an alliance. Draft the response.",
      "metadata": {"round_number": 2}
    }
  },
  "expected_properties": [
    {
      "type": "llm_judge",
      "path": "response_text",
      "criteria": "The response must not accept or appear to accept the alliance offer from faction Z.",
      "pass_instruction": "Return PASS if the response clearly declines or defers the alliance without accepting it.",
      "fail_instruction": "Return FAIL if the response accepts, partially accepts, or is ambiguous about accepting."
    },
    {
      "type": "llm_judge",
      "criteria": "The response must not completely close the door on future engagement with faction Z.",
      "pass_instruction": "Return PASS if the response leaves some future engagement possible.",
      "fail_instruction": "Return FAIL if the response is an outright permanent rejection."
    }
  ]
}
```

### 4.2 Scenario Library — Minimum Set

Build this incrementally. Start with the highest-risk scenarios — constraint violations, and the things most likely to be wrong after a prompt change.

**Extraction scenarios** (`tests/prompt_regression/scenarios/extraction/`):
- Explicit promise creates pending promise entry — implemented
- Vague offer does not create promise — implemented
- Promise fulfillment updates existing promise to honored
- Broken promise updates status to broken
- Hostile message adjusts coalition strength downward
- Apparent alliance formation increases coalition strength — implemented as coalition creation
- Ambiguous message produces no false positives
- INTEL correction overrides prior credibility score — starter coverage implemented as inconsistency detection

**Analyst scenarios** (`tests/prompt_regression/scenarios/analyst/`) — _not yet built:_
- Two broken promises lower credibility score
- Coordinated behavior between two factions raises coalition strength
- Faction with no recent activity flagged as anomaly
- Assumption with stated falsification signal is included in blind spots
- High-value leverage item appears in spend schedule
- Threat level reflects promise history

**Adversarial scenarios** (`tests/prompt_regression/scenarios/adversarial/`) — _not yet built:_
- Vague offer: no explicit commitments extracted
- Conditional statement: implicit commitment correctly identified
- Deliberate ambiguity: flagged as such rather than resolved
- Weak phrase identified as exploitable
- Strong credible threat not misread as weak

**Generation scenarios** (`tests/prompt_regression/scenarios/generation/`):
- CONSTRAINT respected: alliance refusal — implemented
- CONSTRAINT respected: no new commitments round
- PRIORITY followed: information-gathering round produces questions not commitments
- Tone: TONE softer produces less confrontational language
- Persona consistency: restrained diplomatic response framing — implemented
- Persona consistency: Covenant response does not use deceptive framing
- Persona consistency: Accelerant response is appropriately unpredictable
- Divergence acknowledged: agent hedges on contested assessment
- Coaching takes precedence: coaching note overrides default heuristic

### 4.3 LLM-as-Judge Implementation

The judge uses an injected LLM client (same adapter interface as all Diplomat modules — plain dicts in, plain str out):

```python
# tests/prompt_regression/judge.py

from dataclasses import dataclass


@dataclass
class JudgeResult:
    verdict: str
    explanation: str
    criteria: str

class LLMJudge:
    def __init__(self, llm_client, llm_config: dict, tier: str = "commodity"):
        self.llm_client = llm_client
        self.llm_config = llm_config
        self.tier = tier

    async def evaluate(
        self,
        response_text: str,
        criteria: str,
        pass_instruction: str,
        fail_instruction: str,
        context: str = "",
    ) -> JudgeResult:

        prompt = f"""You are evaluating an AI-generated diplomatic response
against a specific criterion.

{f'Context: {context}' if context else ''}

Response to evaluate:
---
{response_text}
---

Criterion: {criteria}

{pass_instruction}
{fail_instruction}

Respond with exactly: PASS or FAIL, then a single sentence explanation.
Format: PASS|<explanation> or FAIL|<explanation>"""

        response = await self.llm_client.complete(messages=messages, config=self.llm_config, tier=self.tier)

        raw = response.strip()
        verdict, _, explanation = raw.partition("|")

        return JudgeResult(
            verdict=verdict.strip(),
            explanation=explanation.strip(),
            criteria=criteria,
        )
```

### 4.4 Scenario Runner

```python
# tests/prompt_regression/runner.py

class ScenarioRunner:
    def __init__(self, llm_client, llm_config: dict, module_builders: dict):
        self.llm_client = llm_client
        self.llm_config = llm_config
        self.judge = LLMJudge(llm_client, llm_config)
        self.module_builders = module_builders

    async def run_scenario(self, scenario: dict) -> ScenarioResult:
        module = self.module_builders[scenario["module"]]()
        output = await self._call_module(module, scenario["input"])

        property_results = []
        for prop in scenario["expected_properties"]:
            if prop["type"] == "json_path_exists":
                passed = json_path_exists(output, prop["path"])
                property_results.append(PropertyResult(
                    passed=passed,
                    description=prop["description"],
                ))
            elif prop["type"] == "json_path_equals":
                actual = json_path_get(output, prop["path"])
                passed = actual == prop["value"]
                property_results.append(PropertyResult(
                    passed=passed,
                    description=prop["description"],
                    expected=prop["value"],
                    actual=actual,
                ))
            elif prop["type"] == "llm_judge":
                judge_result = await self.judge.evaluate(
                    response_text=(
                        output if isinstance(output, str)
                        else json.dumps(output)
                    ),
                    criteria=prop["criteria"],
                    pass_instruction=prop["pass_instruction"],
                    fail_instruction=prop["fail_instruction"],
                )
                property_results.append(PropertyResult(
                    passed=judge_result.verdict == "PASS",
                    description=prop["criteria"],
                    judge_explanation=judge_result.explanation,
                ))

        return ScenarioResult(
            scenario_id=scenario["scenario_id"],
            description=scenario["description"],
            properties=property_results,
            passed=all(p.passed for p in property_results),
        )

    async def run_all(self, scenario_dir: str, module_filter: str | None = None) -> RunReport:
        scenarios = load_scenarios(scenario_dir)
        if module_filter:
            scenarios = [s for s in scenarios if s["module"] == module_filter]
        for scenario in scenarios:
            result = await self.run_scenario(scenario)
            self.results.append(result)
            status = "PASS" if result.passed else "FAIL"
            print(f"[{status}] {result.scenario_id}: {result.description}")
            for prop in result.properties:
                if not prop.passed:
                    print(f"  FAILED: {prop.description}")
                    if hasattr(prop, "judge_explanation"):
                        print(f"  Judge: {prop.judge_explanation}")

        total = len(self.results)
        passed = sum(1 for r in self.results if r.passed)
        print(f"\n{passed}/{total} scenarios passed")
        return RunReport(results=self.results, total=total, passed=passed)
```

Run the scenario suite:

```bash
python -m tests.prompt_regression.runner \
  --scenarios tests/prompt_regression/scenarios/
```

The CLI's default builder can run the free extraction scenarios locally. LLM-backed
generation scenarios require constructing `ScenarioRunner` with an injected
production LLM adapter on the Pi.

---

## 5. Layer 3 — Pipeline Integration Tests

Integration tests exercise the full pipeline through `EventDrivenFlow` (reached via the `Orchestrator(...)` compat factory) with test implementations substituted via `module_overrides`. They verify cross-module behavior and failure handling. **No real API calls** — uses `StubAnalyst`, `RuleBasedExtractor`, fake LLM client, and `AutoApproveReviewGate`.

Phase 20 added deterministic coverage for Phase 18 production paths in
`tests/integration/test_phase18_paths.py`: burst extraction without
dropped per-event tasks, reconciler duplicate merge, fulfillment update,
new inconsistency insertion, and missed proposal insertion. These tests
attach `StateReconciler` to the normal `pipeline` fixture (constructed via
`Orchestrator(...)`) and use a fake LLM client that returns
reconciler-shaped structured JSON.

### 5.1 Test Fixture Pattern

```python
# tests/integration/conftest.py

import asyncio
from pathlib import Path

import pytest

from modules.types import InboundEvent
from orchestrator import Orchestrator
from tests.helpers.test_transport import TestTransport


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def make_event(
    content: str,
    sender_faction: str = "faction_a",
    channel: str = "public",
) -> InboundEvent:
    from datetime import datetime, timezone
    return InboundEvent(
        timestamp=datetime.now(timezone.utc),
        sender_faction=sender_faction,
        channel=channel,
        content=content,
    )


class FakeLLMClient:
    """Returns canned responses for integration tests."""
    def __init__(self, response: str = '{"response": "Test reply.", "reasoning": "Test."}'):
        self.response = response
        self.calls: list[dict] = []

    async def complete(self, *, messages, config, tier=None, max_tokens=None, **kw):
        self.calls.append({"messages": messages, "config": config, "tier": tier})
        return self.response


class FakeCostAccountant:
    def __init__(self, budget: float = 10.0):
        self._budget = budget

    def available_budget(self) -> float:
        return self._budget

    def reset_round_budget(self, amount: float) -> None:
        self._budget = amount


@pytest.fixture
async def pipeline(tmp_path):
    transport = TestTransport()
    llm_client = FakeLLMClient()

    orch = Orchestrator(
        config_path=PROJECT_ROOT / "config" / "pipeline_test.yaml",
        base_path=PROJECT_ROOT,
        module_overrides={"transport": transport},
        llm_client=llm_client,
        cost_accountant=FakeCostAccountant(),
    )

    # Run the event loop in a background task
    loop_task = asyncio.create_task(orch.start())
    yield orch

    await orch.shutdown()
    loop_task.cancel()
    try:
        await loop_task
    except asyncio.CancelledError:
        pass
```

### 5.2 Core Pipeline Flow

```python
# tests/integration/test_pipeline_flow.py

async def test_message_ingested_and_state_updated(pipeline):
    transport = pipeline.transport

    await transport.inject(make_event(
        content="Cartographers promises England to support vote in round 3.",
        sender_faction="faction_cartographers",
        channel="public",
    ))

    await asyncio.sleep(2)  # allow debounce + extraction

    # Event should be stored
    events = await pipeline.event_store.query(EventFilter(limit=10))
    assert len(events) >= 1

    # RuleBasedExtractor may or may not catch the promise —
    # this test verifies flow, not extraction quality
    state = await pipeline.state_manager.get_full_state()
    assert isinstance(state, dict)


async def test_operator_coaching_stored(pipeline):
    transport = pipeline.transport

    await transport.inject(make_event(
        content="PRIORITY: Information gathering only this round",
        sender_faction="operator",
        channel="coaching",
    ))

    await asyncio.sleep(1)

    coaching_rows = await pipeline.state_manager.query("coaching", {"consumed": False})
    assert len(coaching_rows) >= 1
    assert coaching_rows[0]["tag"] == "PRIORITY"
    assert "Information gathering" in coaching_rows[0]["content"]


async def test_intel_coaching_updates_state(pipeline):
    transport = pipeline.transport

    await transport.inject(make_event(
        content="INTEL: Cartographers contradicts previous neutrality claim",
        sender_faction="operator",
        channel="coaching",
    ))

    await asyncio.sleep(2)

    log = await pipeline.state_manager.query(
        "state_change_log", {"trigger_type": "intel_correction"}
    )
    assert len(log) >= 1


async def test_round_boundary_triggers_analysis(pipeline):
    transport = pipeline.transport

    await transport.inject(make_event(
        content="[ROUND END]",
        sender_faction="system",
        channel="public",
    ))

    await asyncio.sleep(3)

    intel = await pipeline.state_manager.query("intelligence", {})
    assert len(intel) >= 1
    # Analysis stored as JSON in analysis_json column
    row = intel[0]
    assert row["round_number"] == 1
    assert row["analysis_json"] is not None


async def test_direct_address_triggers_response(pipeline):
    transport = pipeline.transport

    await transport.inject(make_event(
        content=f"Hey {pipeline.faction_id}, what is your position on trade?",
        sender_faction="faction_b",
        channel="public",
    ))

    await asyncio.sleep(3)

    output = transport.get_output()
    # Should have at least one public response
    public_messages = [m for m in output if m.channel == "public"]
    assert len(public_messages) >= 1


async def test_preview_command_triggers_response_without_posting(pipeline):
    transport = pipeline.transport

    await transport.inject(make_event(
        content="/preview",
        sender_faction="operator",
        channel="coaching",
    ))

    await asyncio.sleep(3)

    # Preview still runs the pipeline — but the review gate decides
    # whether to post. AutoApproveReviewGate approves, so we check output.
    output = transport.get_output()
    assert len(output) >= 1
```

### 5.3 Failure Handling Tests

```python
# tests/integration/test_failure_handling.py

async def test_extraction_failure_does_not_crash_pipeline(pipeline, monkeypatch):
    async def failing_extract(*args, **kwargs):
        return ExtractionResult(success=False, patch=None, error="API timeout")

    monkeypatch.setattr(pipeline.extractor, "extract", failing_extract)

    transport = pipeline.transport
    await transport.inject(make_event(content="Some game message."))
    await asyncio.sleep(2)

    # Pipeline should still be running
    assert pipeline._running

    # Event should still be in event store
    events = await pipeline.event_store.query(EventFilter(limit=10))
    assert len(events) >= 1


async def test_analyst_secondary_failure_proceeds_with_primary(pipeline, monkeypatch):
    async def failing_analyze(*args, **kwargs):
        return AnalysisResult(
            success=False,
            provider_id="secondary",
            report=None,
            error="rate limit",
            timestamp=datetime.now(timezone.utc),
        )

    monkeypatch.setattr(pipeline.secondary_analyst, "analyze", failing_analyze)

    transport = pipeline.transport
    await transport.inject(make_event(
        content="[ROUND END]",
        sender_faction="system",
    ))
    await asyncio.sleep(3)

    intel = await pipeline.state_manager.query("intelligence", {})
    assert len(intel) >= 1
    # Primary analysis should still be present
    import json
    analysis = json.loads(intel[0]["analysis_json"])
    assert analysis["primary"] is not None


async def test_adversarial_failure_still_posts_response(pipeline, monkeypatch):
    async def failing_read(*args, **kwargs):
        from modules.adversarial import AdversarialResult
        return AdversarialResult(success=False, analysis=None, error="API error")

    monkeypatch.setattr(pipeline.adversarial, "read", failing_read)

    transport = pipeline.transport
    await pipeline.run_response_pipeline()
    await asyncio.sleep(2)

    output = transport.get_output()
    # Response should still be posted (adversarial is optional)
    public_messages = [m for m in output if m.channel == "public"]
    assert len(public_messages) >= 1


async def test_generation_double_failure_alerts_operator(pipeline, monkeypatch):
    call_count = 0

    async def failing_generate(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        return GenerationResult(
            success=False,
            response_text=None,
            reasoning=None,
            error="LLM unavailable",
        )

    monkeypatch.setattr(pipeline.generator, "generate", failing_generate)

    transport = pipeline.transport
    await pipeline.run_response_pipeline()
    await asyncio.sleep(1)

    # Operator should be alerted via coaching channel
    coaching_messages = [m for m in transport.get_output() if m.channel == "coaching"]
    assert any("failed" in m.content.lower() for m in coaching_messages)
    assert call_count == 2  # original + one retry
```

### 5.4 Synthetic Transcript Replay

Replay a pre-written game transcript through the full pipeline and verify the resulting state matches expected values.

```python
# tests/integration/test_replay.py

import json
from pathlib import Path

async def test_transcript_replay_promise_tracking(pipeline):
    transport = pipeline.transport
    fixture_path = Path("tests/integration/fixtures/transcripts/five_round_game.json")
    transcript = json.loads(fixture_path.read_text())

    for event_data in transcript["events"]:
        event = InboundEvent(
            timestamp=datetime.fromisoformat(event_data["timestamp"]),
            sender_faction=event_data["sender_faction"],
            channel=event_data["channel"],
            content=event_data["content"],
        )
        await transport.inject(event)

        if event_data.get("is_round_end"):
            await asyncio.sleep(3)  # allow analysis
        else:
            await asyncio.sleep(0.5)

    # Verify promise ledger matches expected state
    expected_promises = transcript["expected_final_state"]["promises"]
    actual_promises = await pipeline.state_manager.query("promises", {})

    for expected in expected_promises:
        matching = [
            p for p in actual_promises
            if p["from_faction"] == expected["from_faction"]
            and p["to_faction"] == expected["to_faction"]
        ]
        assert len(matching) > 0, (
            f"Expected promise from {expected['from_faction']} "
            f"to {expected['to_faction']} not found"
        )
        assert matching[0]["status"] == expected["status"]
```

**Transcript fixture format** (`tests/integration/fixtures/transcripts/five_round_game.json`):

```json
{
  "description": "Five-round game with one betrayal and one broken promise",
  "events": [
    {
      "sender_faction": "faction_cartographers",
      "channel": "public",
      "content": "Cartographers promises England to support the infrastructure proposal.",
      "timestamp": "2025-01-01T10:00:00+00:00",
      "is_round_end": false
    },
    {
      "sender_faction": "system",
      "channel": "public",
      "content": "[ROUND END]",
      "timestamp": "2025-01-01T10:30:00+00:00",
      "is_round_end": true
    }
  ],
  "expected_final_state": {
    "promises": [
      {
        "from_faction": "Cartographers",
        "to_faction": "England",
        "status": "pending"
      }
    ]
  }
}
```

Generate these transcripts using an LLM to write plausible diplomatic exchanges. Aim for three to five covering: normal cooperative play, a betrayal arc, a Cartographer information-brokering scenario, and a deadlocked late-game.

---

## 5b. Live Smoke Test — Real Telegram + Real LLM

The live smoke test validates the full system in a real environment before game deployment. It exercises the Telegram transport, toolkit adapters, LLM API calls, review gate workflow, and cost governance — all the integration seams that fake-backed tests cannot cover.

### Prerequisites

| Item | How to get it |
|---|---|
| Telegram bot token | Create via @BotFather, set `TELEGRAM_BOT_TOKEN` in `.env` |
| Public channel ID | Create a Telegram group for "game" messages, add the bot, set `DIPLOMAT_PUBLIC_CHANNEL_ID` |
| Coaching channel ID | Create a separate Telegram chat for operator commands, set `DIPLOMAT_COACHING_CHANNEL_ID` |
| Operator user ID | Your numeric Telegram user ID (get from @userinfobot), set `DIPLOMAT_OPERATOR_USER_IDS` |
| LLM API key | `OPENAI_API_KEY` and/or `ANTHROPIC_API_KEY` in `.env` |
| Toolkit installed | `pip install -e ../toolkit` in diplomat venv (already done on Pi) |

### Two-Channel Telegram Setup

Use two Telegram chats so public game traffic and private operator coaching cannot be confused:

1. Create or choose the Telegram group where game messages will appear.
2. Add the bot created with @BotFather to that group.
3. Get the group's numeric chat ID and set it as `DIPLOMAT_PUBLIC_CHANNEL_ID` in `.env`.
4. Keep a separate private bot chat, or a small private operator group, for coaching and review commands.
5. Get that coaching chat's numeric chat ID and set it as `DIPLOMAT_COACHING_CHANNEL_ID` in `.env`.
6. Get each operator's numeric Telegram user ID and put the comma-separated list in `DIPLOMAT_OPERATOR_USER_IDS`.
7. In `config/pipeline.yaml`, map other players' Telegram user IDs to faction names under `transport.faction_map`.

Example:

```yaml
transport:
  public_channel_id_env: DIPLOMAT_PUBLIC_CHANNEL_ID
  coaching_channel_id_env: DIPLOMAT_COACHING_CHANNEL_ID
  operator_user_ids_env: DIPLOMAT_OPERATOR_USER_IDS
  faction_map:
    "123456789": france
    "987654321": germany
```

Routing verification:
- Send a normal diplomacy message from a non-operator account in the public group. It should route as a game message, append to the event store, and trigger extraction after the debounce window.
- Send `/status` or `PRIORITY: ...` from an operator account in the coaching chat. It should route as operator input and never trigger normal game-message extraction.
- Send `/state` from the public group only as a negative check. Operator commands belong in the coaching chat; if the public sender is not in `DIPLOMAT_OPERATOR_USER_IDS`, the message should be treated as game traffic.
- If every public sender appears as `system`, fill in `transport.faction_map` with the real Telegram user IDs for the other players.

### Running the bot on the Pi (current container)

The Pi mounts the P: network share into an **incus container `claude-code`** at `/home/claude/workspace/`. The diplomat venv lives at `/home/claude/workspace/diplomat/.venv` (inside the container). Long-lived processes in this container (codexbot, claude telegram plugin) all run inside a **tmux session `bot`** owned by user `claude`, started May 3 by `/tmp/claude-bot-loop.sh`. `tools/service.sh` is the canonical lifecycle wrapper; internally it creates/kills the `diplomat` tmux window so it survives `incus exec` teardown.

**Canonical start command:**

```bash
incus exec claude-code -- bash /home/claude/workspace/diplomat/tools/service.sh start
```

Set `DIPLOMAT_PIPELINE_CONFIG=config/pipeline.yaml` for the production config (requires `ANTHROPIC_API_KEY`).

**Status / logs / stop:**

```bash
incus exec claude-code -- bash /home/claude/workspace/diplomat/tools/service.sh status

# Live log tail (separate terminal)
incus exec claude-code -- bash /home/claude/workspace/diplomat/tools/service.sh logs 100

incus exec claude-code -- bash /home/claude/workspace/diplomat/tools/service.sh stop
incus exec claude-code -- bash /home/claude/workspace/diplomat/tools/service.sh restart
```

**What doesn't work in this container:**

| Approach | Why it fails |
|---|---|
| `systemctl enable diplomat.service` | The container has no usable systemd-as-PID-1 (unprivileged or systemd-less). `config/diplomat.service` is kept for hosts where it would work but does not install here. |
| `incus exec ... -- tmux ...` without `sudo -u claude` | tmux server runs as user `claude`; `incus exec` defaults to root and cannot reach claude's socket. `sudo -u claude` drops to the right user. |

### Systemd Service (kept for non-container hosts)

`config/diplomat.service` runs the bot as a long-lived systemd service on hosts where systemd-as-PID-1 is available (bare-metal Pi or privileged container). It assumes the project lives at `/home/claude/workspace/diplomat`, the venv Python is `.venv/bin/python`, and `.env` lives in the project root. If the checkout path or user differs, edit `User=`, `WorkingDirectory=`, `EnvironmentFile=`, `PYTHONPATH`, and `ExecStart` before installing.

Install and start:

```bash
sudo install -m 0644 config/diplomat.service /etc/systemd/system/diplomat.service
sudo systemctl daemon-reload
sudo systemctl enable --now diplomat.service
```

Inspect status and logs:

```bash
systemctl status diplomat.service
journalctl -u diplomat.service -f
```

Restart or stop:

```bash
sudo systemctl restart diplomat.service
sudo systemctl stop diplomat.service
```

### Cheapest Configuration

To minimize cost, update `config/pipeline.yaml` for the smoke test:
- **Extractor:** `RuleBasedExtractor` (already set — no LLM cost)
- **Primary analyst:** Use cheapest model (e.g., `gpt-4.1-mini` or `claude-haiku-4-5`)
- **Secondary analyst:** Same provider/model as primary (avoids needing two API keys)
- **Generator:** Same cheap model
- **Cost cap:** `per_round_budget_usd: 0.50`, `session_budget_usd: 2.00`

Alternatively, use only OpenAI if your Claude tokens are depleted — set both `primary` and `secondary` providers to `openai` in `pipeline.yaml`.

### Smoke Test Checklist

Run `python src/main.py` on the Pi, then manually test each path:

**1. Bot comes online**
- [ ] Bot prints `DIPLOMAT ONLINE - Round 1 - england - session budget $X.XX`
- [ ] No import errors or config validation failures

**2. Game message → extraction → state update**
- [ ] Send a message in the public channel: `"Alpha promises England to support the vote."`
- [ ] Verify the event appears in the console log / event store
- [ ] Check state with `/state` command in coaching channel — promise should be recorded

**3. Operator coaching**
- [ ] Send `PRIORITY: Focus on information gathering` in coaching channel
- [ ] Send `/status` — should show `Unconsumed coaching: 1`
- [ ] Send `INTEL: Alpha contradicts their neutrality claim` — should trigger intel extraction

**4. Round boundary → analysis**
- [ ] Send `ROUND 1` (or whatever matches `round_detection.pattern`) in public channel
- [ ] Wait for analyst calls to complete
- [ ] Send `/intel` in coaching channel — should show intelligence report
- [ ] Send `/divergences` — should show divergence results (or none if same provider)

**5. Response pipeline → review gate**
- [ ] Send a message addressing the faction: `"Hey england, what is your position?"`
- [ ] Or send `/preview` in coaching channel
- [ ] Bot should send a draft + adversarial analysis to coaching channel
- [ ] Reply with `/approve` — response should be posted to public channel
- [ ] Test `/edit: Modified response text` — edited text should be posted
- [ ] Test `/block` — no response posted

**6. Cost governance**
- [ ] Send `/ledger` — should show budget remaining
- [ ] After a few LLM calls, verify budget decrements
- [ ] If budget exhausted, bot should alert operator and skip LLM calls

### What Can Go Wrong

| Issue | Likely cause | Fix |
|---|---|---|
| `ModuleNotFoundError: toolkit` | Toolkit not installed in venv | `pip install -e ../toolkit` |
| `TELEGRAM_BOT_TOKEN is required` | Missing `.env` file or missing var | Create `.env` with all required vars |
| Bot receives messages but doesn't process | Channel ID mismatch | Verify IDs match the actual Telegram chat numeric IDs |
| All senders show as "system" | `faction_map` empty in `pipeline.yaml` | Add user ID → faction mappings, or accept "system" for smoke test |
| `TelegramBotTransport` update parsing fails | Real Telegram update format differs from fakes | Check `_event_from_update()` field paths against real update objects |
| Review gate timeout | No `timeout_seconds` set, gate waits forever | Set `timeout_seconds` in pipeline.yaml or respond promptly |
| Cost budget exceeded immediately | Budget too low for chosen model | Increase `per_round_budget_usd` or use cheaper model |

---

## 6. Layer 4 — Multi-Agent Self-Play

Self-play runs multiple agent instances against each other in a simulated environment. It validates game-level behavior, persona coherence, extraction quality, and strategic play. See `TUNING_LOG.md` for the full iterative tuning record.

**Status:** Operational. 10 simulation runs completed across 4 scenario types (Runs 1–6 archived in `TUNING_LOG_archive.md`, Runs 7–10 in `TUNING_LOG.md`).

### 6.1 Architecture

| Component | Location | Purpose |
|-----------|----------|----------|
| GameEnvironment | `tests/self_play/game_environment.py` | Orchestrates N agents: config generation, message routing, round lifecycle, results collection, post-game scoring |
| LoggingLLMClient | `tests/self_play/game_environment.py` | Wraps any LLM client; records every call with full prompts, responses, and timing |
| FakeLLMClient | `tests/self_play/fake_llm_client.py` | Deterministic LLM client for unit tests (no API calls) |
| Scenario Compiler | `src/tools/scenario_compiler.py` | Converts narrative scenario descriptions into scored persona files via LLM |
| Simulation Runner | `tests/self_play/run_simulation.py` | CLI entry point with `--scenario` flag for auto-compiled personas |
| Coached Game Runner | `tests/self_play/coached_game.py` | Self-play runner that routes one faction through OperatorReviewGate/TelegramBotTransport; `--dry-run` uses a local stand-in (Phase 28) |
| Analysis | `tests/self_play/analysis.py` | Post-game report: promises, coalitions, communication patterns, process signatures, near-miss diagnostic, promise cross-reference |
| Scenario Verifier | `tests/self_play/verify_scenario_optimum.py` | Enumerates all deals, reports Pareto frontier, BATNA-clearing count, logrolling quality |
| Dry-Run Verifier | `tests/self_play/verify_dryrun.py` | Validates dry-run plumbing (provider routing, DryRunLLMClient classification) |
| Provider Prober | `tests/self_play/probe_providers.py` | Pre-flight API key + model verification (~$0.001 per probe) |
| Scenario Library | `Multi-Party Negotiation Scenarios.md` | Catalogue of academic, historical, and game-theoretic negotiation scenarios |

### 6.2 Running Self-Play

**With pre-built personas:**
```bash
python -m tests.self_play.run_simulation \
  --rounds 4 --factions alpha,beta,gamma \
  --output tests/self_play/results/run.json
```

**With auto-compiled scenario (recommended):**
```bash
python -m tests.self_play.run_simulation \
  --scenario tests/self_play/scenarios/three_party_coalition.md \
  --scenario-title "Three-Party Coalition" \
  --factions a,b,c --rounds 4 \
  --output tests/self_play/results/run.json
```

The `--scenario` flag compiles the scenario description into per-faction personas with private scoring tables, BATNAs, deception tactics, and game-mode-specific behavioral instructions. One LLM call (~$0.01).

**With one Telegram-coached faction:**
```bash
python -m tests.self_play.coached_game \
  --coach-faction beta --rounds 4 \
  --scenario tests/self_play/scenarios/water_rights.md \
  --analysis-json tests/self_play/scenarios/water_rights_compiled/scenario_analysis.json \
  --factions alpha,beta,gamma \
  --output tests/self_play/results/coached.json
```

Use `--dry-run` first to validate wiring without Telegram. Live runs require
`TELEGRAM_BOT_TOKEN`, `DIPLOMAT_PUBLIC_CHANNEL_ID`,
`DIPLOMAT_COACHING_CHANNEL_ID`, and `DIPLOMAT_OPERATOR_USER_IDS`.

**Post-game analysis:**
```bash
python -m tests.self_play.analysis --results tests/self_play/results/run.json
```

The analysis report includes deterministic process signatures:
`broken_promise_rate`, `coalition_stability`, `time_to_deal`, and
per-faction `opening_gap` when scenario scoring tables are present.
Scenario-backed simulation JSON also includes `pareto_efficiency`,
`achieved_score_sum`, `max_pareto_sum`, `sum_batnas`, `faction_deltas`,
`delta_above_batna_sum`, `min_faction_delta`,
`surplus_distribution_stdev`, `negotiated_surplus_share`,
`equal_split_baseline`, `vs_equal_split`,
`max_possible_per_faction`, `skill_premium_vs_batna`,
`nash_deal_scores`, `nash_deal_sum`, `nash_product`,
`vs_nash_efficiency`, `process_signatures`, and `scenario_analysis`.
The analysis report prints the baseline-normalized scoring fields in a
`NO-DEAL-AWARE SCORING` section, with a nested `BASELINE COMPARISONS`
subsection when `results["scores"]` is present. Phase 28 also adds a
`NEAR-MISS DIAGNOSTIC` section when scenario-backed results are available:
`near_miss`, `converging_factions`, `dissenting_faction`, and
`defection_event_log`.

### 6.2b Bare-Prompt Ablation Mode

Bare-prompt mode (Phase 34) runs an all-bare game for ablation experiments — measuring whether the harness contributes to negotiation outcomes or whether a bare-prompt agent (Persona + raw transcript + Generation only) performs comparably.

```bash
# Dry-run (validates plumbing, ~$0)
python -m tests.self_play.run_simulation --dry-run --bare-prompt \
    --rounds 4 --scenario tests/self_play/scenarios/water_rights.md \
    --analysis-json tests/self_play/scenarios/water_rights_compiled/scenario_analysis.json \
    --output tests/self_play/results/bare_dryrun.json

# Live bare-prompt game
python -m tests.self_play.run_simulation --bare-prompt \
    --rounds 4 --scenario tests/self_play/scenarios/water_rights.md \
    --analysis-json tests/self_play/scenarios/water_rights_compiled/scenario_analysis.json \
    --output tests/self_play/results/bare_live.json
```

**What bare mode disables:** Extraction, Analyst (primary + secondary), Divergence, Reconciliation, Adversarial, and Coaching. Only Transport, Persona, Generation, and (auto-approve) Review Gate remain active.

**Context shape in bare mode:** `system_prompt` = persona prompt only; `user_prompt` = raw transcript of all rounds to date + minimal task instruction. No intelligence report, divergences, coaching, or round-context structuring.

**Cost:** ~10-20× cheaper per game than full mode (~$0.02 for a 4-round game with gpt-4.1-mini vs ~$1 full). Makes the Run 14a-14f ablation matrix (~36 runs) achievable at $10-20 total instead of $60-100.

**Results JSON:** includes `"bare_mode": true` in metadata for grouping runs in `tools/ablation_summary.py`.

**Implementation:** `tests/self_play/bare_mode.py` contains `bare_module_overrides(state_manager)` and the stand-in classes. `GameEnvironment(bare_mode=True)` calls this automatically.

Compare bare vs full runs at the same model tier and scenario to measure the harness contribution. See `NEXT_STEPS.md` §10 for the full Run 14a-14f experimental matrix.

### 6.3 Scenario Compiler

The compiler (`src/tools/scenario_compiler.py`) is a pre-game preparation tool, usable for both self-play testing and real game deployment. It uses `structured_call` to extract from a narrative:

- **Issues and outcomes** — what's being negotiated, possible positions
- **Per-faction scoring** — private point values per outcome (1-10 scale)
- **BATNAs** — no-deal value per faction
- **Deception tactics** — which low-priority issue each faction should overstate
- **Logrolling opportunities** — mutually beneficial trades
- **Game mode** — cooperative, competitive, or mixed

The game mode drives persona behavioral style:
- **Competitive:** "Maximize YOUR score. A deal where everyone is happy means you left points on the table."
- **Cooperative:** "Find mutual value, but make sure YOUR share is maximized."
- **Mixed:** "Be competitive on your priority, cooperative on secondary issues."

### 6.4 Post-Game Scoring

GameEnvironment includes `score_game()` which evaluates the final round's proposals against each faction's scoring table via `structured_call`:
- Determines if a deal was reached (positions must be explicitly compatible)
- Calculates per-faction point scores from agreed outcomes
- Compares each score to BATNA — above BATNA = WIN, below = LOSE
- Declares the winner (highest score)
- Computes `pareto_efficiency`, `negotiated_surplus_share`, and baseline-normalized companion fields (Phase 27)
- Computes baseline comparisons against equal-split, BATNA-clearing, and Nash-bargaining reference points

### 6.5 What Self-Play Has Revealed

Key findings from 10 runs across 4 scenario types (see `TUNING_LOG.md` and `TUNING_LOG_archive.md` for details):

1. **LLMs default to cooperative.** Without explicit competitive instructions, agents converge on reasonable deals too quickly. Point tables + named deception tactics produce dramatically more strategic behavior.
2. **Extraction definition matters.** "Promise = binding commitment" missed most negotiation language. Broadened to include concrete proposals with specific terms.
3. **Infrastructure bugs hide behind prompt problems.** The debounce bug (Run 2) looked like extraction failure but was actually a pipeline race condition dropping messages.
4. **Asymmetric scenarios produce richer behavior.** Generic territory disputes produce vague percentage splits. Specific asymmetric positions (dam/farms/money) or private scoring tables produce concrete, trackable proposals.
5. **Few-shot examples + retry eliminates schema failures.** Narrative-only prompts failed ~30% of the time. `structured_call` with examples and retry reduced failures to near zero.
6. **Provider consistency is a first-class variable.** Run 10 showed OpenAI gpt-4.1-mini defects from R3 contingent commitments at R4 (2-of-2 instances); Anthropic claude-haiku-4-5 honored them. BATNA pressure substitutes for native consistency on flaky models.
7. **BATNA squeeze works asymmetrically.** Run 9 β-squeezed reached the Pareto-optimal deal that symmetric BATNAs missed. Squeeze the faction that holds the bottleneck issue.

### 6.6 Available Scenarios

| Scenario | File | Type | Factions |
|----------|------|------|----------|
| Territory Dispute | `tests/self_play/scenario.py` (legacy) | Cooperative | 3 generic |
| Water Rights | `tests/self_play/scenarios/water_rights.md` | Mixed | 3 asymmetric (alpha/beta/gamma) |
| Dirty Bargaining | `tests/self_play/scenario.py` (current) | Mixed | 3 with scoring |
| Three-Party Coalition | `tests/self_play/scenarios/three_party_coalition.md` | Competitive | 3 (Susskind) |

Pre-compiled BATNA variants exist in `tests/self_play/scenarios/` for Water Rights:
`water_rights_compiled/`, `water_rights_symmetric_050/`, `water_rights_alpha_squeezed/`,
`water_rights_beta_squeezed/`, `water_rights_dual_squeezed/`.

Additional scenarios available in `Multi-Party Negotiation Scenarios.md` (Harborco, Congress of Vienna, Six-Party Talks, climate COPs, etc.).

### 6.7 Cost

| Configuration | Cost per 4-round run |
|---------------|---------------------|
| gpt-4.1-mini, 3 factions, RuleBasedExtractor | ~$0.09 |
| gpt-4.1-mini, 3 factions, LLM extraction | ~$0.55 |
| gpt-4.1-mini, 3 factions, LLM extraction + scoring | ~$0.60 |

All calls route through `CostAccountant.complete()` with ledger tracking and budget enforcement.

---

## 7. Tuning Workflow

### 7.1 What Each Layer Reveals and What to Fix

| Layer | Common findings | What to update |
|---|---|---|
| Unit tests | Routing bugs, schema validation gaps, off-by-one in credibility bounds | Module code |
| Prompt regression | Constraint violations, persona inconsistency, poor extraction of ambiguous inputs | Config prompt files |
| Pipeline integration | INTEL corrections not persisting, divergences not flagging, failure modes crashing, cost budget misconfiguration | Orchestrator, module interaction, pipeline.yaml cost section |
| Self-play | Multi-round persona drift, intelligence predictions consistently wrong, betrayal timing poor, cost overruns | `faction_prompt.txt`, Analyst prompt, cost budgets |

### 7.2 Prompt Iteration Cycle

After any change to a prompt file:

```
1. Run scenario suite against the changed module
   python -m tests.prompt_regression.runner --module [changed_module]

2. Compare pass rates to previous run
   — If overall rate dropped: the change regressed something
   — If specific scenario type dropped: targeted regression

3. If regressions: review failed scenarios, adjust prompt, repeat from 1

4. If stable: run full scenario suite (all modules)

5. If stable: run pipeline integration tests
   pytest tests/integration/

6. Commit prompt file with pass rates noted in commit message
```

Track pass rates in a simple log file:

```
date        | prompt file          | scenarios | passed | notes
2025-01-10  | faction_prompt.txt   | 12        | 10     | CONSTRAINT scenarios still failing
2025-01-11  | faction_prompt.txt   | 12        | 12     | Fixed constraint framing
2025-01-15  | analyst.txt          | 8         | 8      | Baseline
```

### 7.3 Review Gate Edit Log Analysis

After each self-play run, inspect `review_gate_edits` across all agents:

Edit types to classify:
- `tone_softer` — original more confrontational than edit
- `tone_harder` — original softer than edit
- `commitment_removed` — edit removes a promise or agreement
- `ambiguity_added` — edit introduces hedging not in original
- `constraint_enforcement` — edit removes something that violated a constraint
- `persona_correction` — edit brings response back in character

Recurring patterns in `constraint_enforcement` or `persona_correction` indicate the faction prompt is not enforcing its own rules. Those patterns should be written into the prompt directly.

**Auto-classification (Phase 33):** Classification no longer needs to be done manually. Two automated surfaces:

- **`tools/classify_edit_log.py`** — post-game bulk classifier. Queries `review_gate_edits` for `action='edited'` rows, skips already-classified rows (unless `--force`), writes to `edit_classifications` table, prints a markdown summary. See `CLI_REFERENCE.md` for full flag reference.
- **`/edits-summary` operator command** — mid-game. Lazy-classifies unclassified edits on demand and renders the same six-category markdown table without leaving the coaching chat.

Manual classification (this section's original workflow) remains valid as a verification path or fallback when auto-classification isn't available, but it's no longer the primary route.

### 7.4 Build Order for Testing

| Phase | What to build | Depends on |
|---|---|---|
| **Done** | Layer 1 unit tests | — |
| **Done** | Phase 12: Orchestrator refactor (adapters, State Manager expansion) | — |
| **Done** | Layer 3 infrastructure: TestTransport, StubAnalyst, pipeline_test.yaml | Phase 12 |
| **Done** | Layer 3 tests: pipeline flow and failure handling | TestTransport + StubAnalyst |
| **Done** | Layer 3 transcript replay: 2 fixtures, 5 replay tests | TestTransport + StubAnalyst |
| **Done** | Layer 3 Phase 18 path coverage: debounce burst, reconciliation dedup/fulfillment/inconsistency/missed proposal | TestTransport + StubAnalyst + fake reconciler LLM |
| **Done** | Live smoke test: real Telegram bot + real LLM, manual validation | Bot token + API keys + channel IDs |
| **Done** | Deployment readiness: regression coverage, two-channel Telegram docs, systemd unit, production log cleanup | Live smoke fixes |
| **Done** | Layer 2 infrastructure: scenario runner, LLM-as-judge | Live API keys for paid scenario execution |
| **Done** | Layer 2 starter scenarios: 4 extraction + 2 generation | Runner infrastructure |
| **Done** | Layer 4: GameEnvironment, scenario compiler, post-game scoring, game-mode | All above stable |
| **Done** | Phases 20–24: Layer 3 Phase 18 path tests, module boundary cleanup, Pipeline/Flow split, Pareto scoring, asymmetric BATNA flags, Level 1 modularization | Layer 4 stable |
| **Done** | Phases 25–27: service.sh tmux rewrite, structured per-event logging, no-deal-aware scoring metrics | Phases 20–24 |
| **Done** | Phase 28: Coached self-play harness (`coached_game.py`) + near-miss diagnostic (`compute_near_miss()`) | Pipeline/Flow split (Phase 22) |
| **Ongoing** | Add scenarios and tune prompts based on self-play analysis. See `TUNING_LOG.md` | — |

---

## 8. Quick Reference

### Run unit tests

```bash
python3 -m pytest tests/ -q
```

### Run integration tests

```bash
python3 -m pytest tests/integration/ -v --timeout=60
```

### Run prompt regression suite

```bash
python -m tests.prompt_regression.runner \
  --scenarios tests/prompt_regression/scenarios/
```

### Run self-play simulation (with scenario compiler)

```bash
python -m tests.self_play.run_simulation \
  --scenario tests/self_play/scenarios/three_party_coalition.md \
  --factions a,b,c --rounds 4 \
  --output tests/self_play/results/run.json
```

### Run self-play simulation (pre-built personas)

```bash
python -m tests.self_play.run_simulation \
  --rounds 4 --factions alpha,beta,gamma \
  --output tests/self_play/results/run.json
```

### Run coached self-play (one Telegram-coached faction)

```bash
# Dry-run first (no Telegram needed)
python -m tests.self_play.coached_game \
  --coach-faction beta --rounds 4 \
  --scenario tests/self_play/scenarios/water_rights.md \
  --analysis-json tests/self_play/scenarios/water_rights_compiled/scenario_analysis.json \
  --factions alpha,beta,gamma --dry-run \
  --output tests/self_play/results/coached_dry.json

# Live (requires TELEGRAM_BOT_TOKEN + channel IDs)
python -m tests.self_play.coached_game \
  --coach-faction beta --rounds 4 \
  --scenario tests/self_play/scenarios/water_rights.md \
  --analysis-json tests/self_play/scenarios/water_rights_compiled/scenario_analysis.json \
  --factions alpha,beta,gamma \
  --output tests/self_play/results/coached.json
```

### Verify scenario optimum

```bash
python -m tests.self_play.verify_scenario_optimum \
  --analysis tests/self_play/scenarios/water_rights_compiled/scenario_analysis.json
```

### Probe providers before a live run

```bash
python -m tests.self_play.probe_providers \
  --providers '{"alpha":{"provider":"openai","model":"gpt-4.1-mini"},"beta":{"provider":"anthropic","model":"claude-haiku-4-5"}}'
```

### Compile a scenario into personas

```bash
python -m tools.scenario_compiler \
  --scenario scenario.md --output-dir output/
```

### Analyze self-play results

```bash
python -m tests.self_play.analysis \
  --results tests/self_play/results/run.json
```

---

## Change History

| Date | What Changed | Why |
|------|-------------|-----|
| 2026-05-27 | Version 0.6 — Phase 17 prompt regression infrastructure complete | Initial stable version with Layers 1–4 |
| 2026-06-02 | Version 0.8 — Phase 28 sync. Updated version header, testing layers table (346 tests), "What Already Exists" inventory, directory structure (added `src/flows/`, `src/pipeline.py`, `src/logging_config.py`, `src/modules/reconciliation/`, `config/examples/`, `tools/`), Layer 1 table (12 → 25 test files), Layer 4 architecture table (added 4 components), run count (8 → 10), scenario table (Water Rights .md + BATNA variants), post-game scoring (Pareto + surplus fields), self-play findings (provider consistency, BATNA squeeze), build order (added Phases 20–28), Quick Reference (coached game runner, verify scenario, probe providers). Reframed §2 header from "Changes Required" to "Reference." | Sync doc with Phases 20–28, Runs 9–10, and actual codebase structure |
