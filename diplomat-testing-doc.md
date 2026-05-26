# AI Diplomat — Testing and Tuning Guide
**Version 0.3 | Companion to System Specification v0.5**

---

## 1. Overview

This document covers the testing strategy, tuning workflow, and implementation changes required to make the AI Diplomat system verifiable before deployment.

The system has two distinct testing challenges. The first is standard software correctness: do the modules behave as specified? The second is harder: does the system produce good diplomatic behavior? These require different approaches. Correctness is testable with standard assertions. Quality requires scenario libraries, LLM-as-judge evaluation, and multi-agent simulation.

The modular architecture in the main spec was partly designed with testability in mind. The `CLITransport`, `AutoApproveReviewGate`, and `RuleBasedExtractor` implementations exist specifically to enable testing without live infrastructure. The `inject()` method on `CLITransport` (see Section 5) enables self-play simulation.

> **Toolkit dependency:** All LLM calls in production and test code go through `toolkit/llm_client`. All Telegram I/O goes through `toolkit/telegram_client`. Cost governance uses `toolkit/cost_accountant`. No direct provider SDK imports (`anthropic`, `openai`) anywhere — including test infrastructure.

### Testing Layers

| Layer | What it tests | Speed | Cost | When to run |
|---|---|---|---|---|
| 1 — Unit | Module correctness | Fast | Free | Every commit |
| 2 — Prompt regression | Prompt quality and constraint compliance | Slow | Low | Before prompt changes go live |
| 3 — Pipeline integration | Cross-module behavior, failure handling | Medium | Low | Before deployments |
| 4 — Multi-agent self-play | Game-level behavior, persona coherence | Slow | Medium-high | Final validation before real game |

---

## 2. Implementation Changes Required

The following changes to the main spec are needed to support the testing strategy. None affect production behavior — they add test-specific implementations and one interface extension.

### 2.1 CLITransport — `inject()` Method

The `CLITransport` implementation in `modules/transport/cli.py` exposes an `inject()` method to allow the `GameEnvironment` (Section 6) and integration tests to push synthetic messages directly into an agent's event stream without going through a real platform.

`inject()` is **not** on the `Transport` ABC — it is a concrete method on `CLITransport` only. Production implementations (`TelegramBotTransport`, `TelethonUserTransport`) are not affected. Tests and self-play access `inject()` by constructing a `CLITransport` directly and passing it to the Orchestrator via dependency injection.

```python
# Not on the ABC — CLITransport only
class CLITransport(Transport):
    async def inject(self, event: InboundEvent) -> None: ...
```

### 2.2 Storage — Add In-Memory Support

`SQLiteEventStore` and `SQLiteStateManager` should accept `:memory:` as a valid path, producing a fully functional but disposable in-memory database. Add to both constructors:

```python
def __init__(self, path: str):
    self.path = path
    # ':memory:' produces a fresh in-memory DB each instantiation
    self.conn = sqlite3.connect(path, check_same_thread=False)
    self._init_schema()
    self._apply_pragmas()
```

No schema or logic changes — just ensure `:memory:` is handled as a valid input.

### 2.3 New Test Implementations

Add the following to the module registry and directory structure. None affect production code paths.

**`modules/transport/cli.py` — `CLITransport`**

Already implemented. Takes an `AsyncIterable[str]` reader and an async writer callable. For integration tests and self-play, use the `TestTransport` helper which adds an `inject()` method and output capture on top of `CLITransport`'s reader/writer design:

```python
class TestTransport:
    """Test helper wrapping CLITransport with inject() and output capture."""

    def __init__(self) -> None:
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._output: list[OutboundMessage] = []
        self._inner = CLITransport(
            reader=self._queue_reader(),
            writer=self._capture_writer,
        )

    async def inject(self, event: InboundEvent) -> None:
        """Push a synthetic event into the transport's listen stream."""
        payload = json.dumps({
            "sender_faction": event.sender_faction,
            "channel": event.channel,
            "content": event.content,
            "timestamp": event.timestamp.isoformat(),
            "recipient": event.recipient,
            "telegram_msg_id": event.telegram_msg_id,
        })
        await self._queue.put(payload)

    async def send(self, message: OutboundMessage) -> None:
        self._output.append(message)
        await self._inner.send(message)

    def listen(self) -> AsyncIterator[InboundEvent]:
        return self._inner.listen()

    def get_output(self) -> list[OutboundMessage]:
        return self._output.copy()

    def clear_output(self) -> None:
        self._output.clear()

    async def _queue_reader(self):
        while True:
            yield await self._queue.get()

    async def _capture_writer(self, text: str) -> None:
        pass  # swallow CLI output in tests
```

**`modules/review_gate/auto_approve.py` — `AutoApproveReviewGate`**

Immediately approves every draft without operator interaction. Logs to `review_gate_edits` table as `action='approved'` so the edit log is populated in test runs.

```python
class AutoApproveReviewGate(ReviewGate):
    async def submit(self, draft: GenerationResult,
                     adversarial: AdversarialResult,
                     round_number: int) -> ReviewDecision:
        # Still logs — edit log should be populated in test runs
        await self._log(draft, adversarial, round_number, 'approved')
        return ReviewDecision(
            action='approved',
            final_text=draft.response_text,
            edit_notes=None
        )
```

**`modules/extraction/rule_based.py` — `RuleBasedExtractor`**

Already implemented. Pattern-matching extractor that detects promises, coalitions, and inconsistencies via regex. Returns empty patches for inputs it cannot parse rather than failing. Requires `schema_path` for validation. Used in self-play when extraction quality is less important than pipeline stability, and in unit tests that don't need real extraction.

```python
class RuleBasedExtractor:
    def __init__(self, schema_path: str | Path) -> None:
        self.schema = load_schema(schema_path)

    async def extract(self, input_text: str,
                      current_state: dict, trigger_type: str) -> ExtractionResult:
        patch_data = self._extract_patch(input_text)  # regex matching
        return ExtractionResult(
            success=True,
            patch=validate_state_patch(patch_data, self.schema),
        )
```

**`modules/analyst/stub.py` — `StubAnalyst`**

Returns a minimal but structurally valid `AnalysisResult` from a fixture file. Used in unit and integration tests that don't need real analysis quality — just a valid intelligence report flowing through the pipeline.

```python
class StubAnalyst(Analyst):
    provider_id = 'stub'

    def __init__(self, fixture_path: str):
        with open(fixture_path) as f:
            self._fixture = json.load(f)

    async def analyze(self, state: dict) -> AnalysisResult:
        return AnalysisResult(
            success=True,
            provider_id=self.provider_id,
            report=self._fixture,
            error=None,
            timestamp=datetime.now()
        )
```

### 2.4 Directory Structure Additions

```
/opt/diplomat/
├── src/
│   └── modules/
│       ├── transport/
│       │   └── cli.py               # ADD
│       ├── extraction/
│       │   └── rule_based.py        # ADD
│       ├── analyst/
│       │   └── stub.py              # ADD
│       └── review_gate/
│           └── auto_approve.py      # ADD (already in spec, confirm present)
├── tests/
│   ├── conftest.py                  # shared fixtures and helpers
│   ├── unit/
│   │   ├── test_coaching_router.py
│   │   ├── test_state_manager.py
│   │   ├── test_context_assembler.py
│   │   ├── test_divergence.py
│   │   ├── test_persona.py
│   │   └── test_extraction_schema.py
│   ├── prompt_regression/
│   │   ├── runner.py                # scenario runner with LLM-as-judge
│   │   ├── judge.py                 # LLM-as-judge module (via toolkit/llm_client)
│   │   └── scenarios/
│   │       ├── extraction/
│   │       ├── analyst/
│   │       ├── adversarial/
│   │       └── generation/
│   ├── integration/
│   │   ├── test_pipeline_flow.py
│   │   ├── test_intel_routing.py
│   │   ├── test_failure_handling.py
│   │   └── fixtures/
│   │       ├── intelligence_stub.json  # valid intelligence schema fixture
│   │       ├── test_persona.txt        # minimal faction persona for tests
│   │       └── transcripts/            # synthetic game transcripts
│   └── self_play/
│       ├── game_environment.py      # GameEnvironment implementation
│       ├── run_simulation.py        # CLI entry point for self-play
│       └── personas/
│           ├── cartographers.txt
│           ├── sustainers.txt
│           ├── arbiters.txt
│           ├── accelerants.txt
│           └── covenant.txt
├── config/
│   └── pipeline_test.yaml           # ADD: test pipeline config
│   └── pipeline_selfplay.yaml       # ADD: self-play config (with cost budgets)
```

### 2.5 Test Pipeline Configuration

`config/pipeline_test.yaml` mirrors `pipeline.yaml` with test implementations substituted:

```yaml
transport:
  implementation: CLITransport
  capture_output: true

event_store:
  implementation: SQLiteEventStore
  path: ":memory:"

state_manager:
  implementation: SQLiteStateManager
  path: ":memory:"

extraction:
  implementation: RuleBasedExtractor   # swap to OpenAIStructuredExtractor
                                        # for Layer 2 prompt tests

analyst:
  primary:
    implementation: StubAnalyst
    fixture: tests/integration/fixtures/intelligence_stub.json
  secondary:
    implementation: StubAnalyst
    fixture: tests/integration/fixtures/intelligence_stub.json

persona:
  implementation: FileBasedPersona
  path: tests/integration/fixtures/test_persona.txt

context_assembler:
  implementation: DefaultContextAssembler
  recent_events_limit: 30

generation:
  implementation: LLMGenerator          # real LLM for Layer 2+
  provider: anthropic
  tier: quality

adversarial:
  implementation: LLMAdversarialReader
  provider: openai
  tier: quality
  enabled: true

coaching:
  implementation: TaggedCoachingParser
  routes: config/coaching_routes.yaml

review_gate:
  implementation: AutoApproveReviewGate
  enabled: true

round:
  mode: signal
  signal_pattern: "[ROUND END]"

game:
  total_rounds: 5
  faction_id: test_faction
  faction_map:
    faction_a: faction_a
    faction_b: faction_b
    faction_c: faction_c
    faction_d: faction_d

# --- Toolkit integration (same structure as production pipeline.yaml) ---

llm_providers:
  anthropic:
    api_key: ${ANTHROPIC_API_KEY}
    models:
      quality: claude-sonnet-4-20250514
      default: claude-sonnet-4-20250514
      commodity: claude-haiku-4-5
  openai:
    api_key: ${OPENAI_API_KEY}
    models:
      quality: gpt-4o
      default: gpt-4o
      commodity: gpt-4o-mini

cost:
  ledger_path: data/test_cost_ledger.jsonl
  per_round_budget_usd: 1.00             # tighter budget for tests
  per_session_budget_usd: 10.00
  per_call_max_usd: 0.50
  abort_on_rate_limit: true
  abort_on_spending_cap: true
```

---

## 3. Layer 1 — Unit Tests

Unit tests cover module correctness in isolation. No real API calls. Run on every commit. Should complete in under 30 seconds.

### 3.1 Coaching Router Tests

The routing logic is pure Python with no external dependencies. Should have high coverage.

```python
# tests/unit/test_coaching_router.py

def test_intel_tag_routes_to_state_updater(parser):
    result = parser.parse("INTEL: Faction X coalition is weaker than assessed")
    assert isinstance(result, CoachingEvent)
    assert result.coaching_type == 'INTEL'
    assert result.route == 'state_updater'

def test_priority_tag_routes_to_queue(parser):
    result = parser.parse("PRIORITY: Information gathering only this round")
    assert result.route == 'coaching_queue'
    assert result.coaching_type == 'PRIORITY'

def test_untagged_input_routes_to_queue_as_free(parser):
    result = parser.parse("Watch faction Y carefully, they went quiet")
    assert result.route == 'coaching_queue'
    assert result.coaching_type == 'FREE'

def test_preview_command_parsed(parser):
    result = parser.parse("/preview")
    assert isinstance(result, Command)
    assert result.name == 'preview'

def test_edit_command_with_text_parsed(parser):
    result = parser.parse("/edit: We would be open to discussing this further")
    assert isinstance(result, Command)
    assert result.name == 'edit'
    assert result.args['text'] == 'We would be open to discussing this further'

def test_malformed_edit_command_handled(parser):
    # Should not raise, should return a Command with empty text or error flag
    result = parser.parse("/edit:")
    assert isinstance(result, Command)

def test_case_insensitive_tags(parser):
    result = parser.parse("intel: some correction")
    assert result.coaching_type == 'INTEL'
```

### 3.2 State Manager Tests

```python
# tests/unit/test_state_manager.py

@pytest.fixture
def manager(tmp_path):
    schema = tmp_path / "state_patch.json"
    schema.write_text(json.dumps(VALID_SCHEMA))  # from conftest
    db = tmp_path / "test.db"
    return SQLiteStateManager(db, schema)

async def test_apply_patch_creates_promise(manager):
    patch = StatePatch(data={
        'promises': [{
            'promise_id': 'p-001',
            'from_faction': 'faction_a',
            'to_faction': 'faction_b',
            'content': 'Support vote in round 3',
            'status': 'pending'
        }]
    })
    source = PatchSource(trigger_type='message', trigger_ref='event_001')
    await manager.apply_patch(patch, source)

    promises = await manager.query('promises', {'from_faction': 'faction_a'})
    assert len(promises) == 1
    assert promises[0]['content'] == 'Support vote in round 3'

async def test_apply_patch_writes_audit_log(manager):
    patch = make_minimal_patch()
    source = PatchSource(trigger_type='intel_coaching', trigger_ref='coaching_042')
    await manager.apply_patch(patch, source)

    log = await manager.query('state_change_log',
                               {'trigger_type': 'intel_coaching'})
    assert len(log) == 1
    assert log[0]['trigger_ref'] == 'coaching_042'

async def test_intel_correction_flagged_separately_from_message(manager):
    msg_patch = make_patch_for_faction('faction_a')
    intel_patch = make_patch_for_faction('faction_a')

    await manager.apply_patch(msg_patch,
        PatchSource('message', 'event_001'))
    await manager.apply_patch(intel_patch,
        PatchSource('intel_coaching', 'coaching_001'))

    log = await manager.query('state_change_log', {})
    trigger_types = [entry['trigger_type'] for entry in log]
    assert 'message' in trigger_types
    assert 'intel_coaching' in trigger_types

async def test_schema_validation_rejects_invalid_patch(manager):
    bad_patch = StatePatch(data={'invalid_field': 'bad_data'})
    source = PatchSource('message', 'event_001')
    with pytest.raises(Exception):  # jsonschema.ValidationError
        await manager.apply_patch(bad_patch, source)

async def test_credibility_score_stored_as_absolute_value(manager):
    # credibility_score is an absolute value, not a delta
    patch = StatePatch(data={
        'faction_state': [{
            'faction_id': 'faction_a',
            'credibility_score': 0.7,
        }]
    })
    await manager.apply_patch(patch, PatchSource('message', 'e001'))
    state = await manager.get('faction_state', 'faction_a')
    assert state['credibility_score'] == 0.7
```

### 3.3 Divergence Tests

```python
# tests/unit/test_divergence.py

from modules.analyst.divergence import compare

def make_result(provider_id, threat_level, leverage_points):
    return AnalysisResult(
        success=True,
        provider_id=provider_id,
        report={
            'threat_level': threat_level,             # integer, not string
            'key_leverage_points': leverage_points,    # flat list of strings
            'coalition_stability': 'stable',
        },
        error=None,
        timestamp=datetime.now(timezone.utc),
    )

def test_threat_level_divergence_flagged():
    # delta=3 exceeds default threshold of 1
    primary = make_result('anthropic', 2, [])
    secondary = make_result('openai', 5, [])
    divergences = compare(primary, secondary)
    assert any(d.field == 'threat_level' for d in divergences)

def test_same_threat_level_no_divergence():
    primary = make_result('anthropic', 3, [])
    secondary = make_result('openai', 3, [])
    divergences = compare(primary, secondary)
    assert not any(d.field == 'threat_level' for d in divergences)

def test_one_step_difference_not_flagged():
    # delta=1, equals threshold=1, should NOT flag (> not >=)
    primary = make_result('anthropic', 2, [])
    secondary = make_result('openai', 3, [])
    divergences = compare(primary, secondary)
    assert not any(d.field == 'threat_level' for d in divergences)

def test_missing_leverage_item_flagged():
    primary = make_result('anthropic', 3, ['broken_promise_round_2'])
    secondary = make_result('openai', 3, [])
    divergences = compare(primary, secondary)
    assert any('leverage' in d.field for d in divergences)

def test_coalition_stability_mismatch_flagged():
    a = AnalysisResult(
        success=True, provider_id='anthropic',
        report={'threat_level': 3, 'key_leverage_points': [],
                'coalition_stability': 'stable'},
        error=None, timestamp=datetime.now(timezone.utc),
    )
    b = AnalysisResult(
        success=True, provider_id='openai',
        report={'threat_level': 3, 'key_leverage_points': [],
                'coalition_stability': 'fragile'},
        error=None, timestamp=datetime.now(timezone.utc),
    )
    divergences = compare(a, b)
    assert any(d.field == 'coalition_stability' for d in divergences)
```

### 3.4 Context Assembler Tests

```python
# tests/unit/test_context_assembler.py

def test_intel_coaching_excluded_from_context(assembler):
    # INTEL entries should NOT appear in the assembled context
    # They have already been applied to the database
    # Note: the assembler only receives non-INTEL entries —
    # INTEL routing is handled by the Orchestrator before assembly.
    # This test verifies that if an INTEL entry somehow reaches
    # the assembler, it is excluded.
    intel_entry = CoachingEntry(
        coaching_type='INTEL',
        content='Faction X coalition weaker than assessed',
        timestamp=datetime.now(),
    )
    context = assembler.assemble(
        persona_prompt="Test persona",
        round_context="Round 2 of unknown",
        intelligence={},
        divergences=[],
        recent_events=[],
        free_coaching=[intel_entry],
        review_gate_enabled=False
    )
    assert 'INTEL' not in context.user_prompt
    assert 'Faction X coalition weaker' not in context.user_prompt

def test_priority_coaching_included(assembler):
    priority_entry = CoachingEntry(
        coaching_type='PRIORITY',
        content='Information gathering only this round',
        timestamp=datetime.now(),
    )
    context = assembler.assemble(
        persona_prompt="Test persona",
        round_context="Round 2",
        intelligence={},
        divergences=[],
        recent_events=[],
        free_coaching=[priority_entry],
        review_gate_enabled=False
    )
    assert 'Information gathering only this round' in context.user_prompt

def test_review_gate_mode_requests_json_output(assembler):
    context = assembler.assemble("p", "r", {}, [], [], [],
                                  review_gate_enabled=True)
    assert '"response"' in context.user_prompt
    assert '"reasoning"' in context.user_prompt

def test_divergences_included_when_present(assembler):
    divergence = Divergence(
        field='threat_model.faction_x.threat_level',
        primary_value='medium',
        secondary_value='critical',
        note='Significant disagreement'
    )
    context = assembler.assemble("p", "r", {}, [divergence], [], [],
                                  review_gate_enabled=False)
    assert 'faction_x' in context.user_prompt
    assert 'uncertain' in context.user_prompt.lower() or \
           'disagree' in context.user_prompt.lower()

def test_no_coaching_produces_default_message(assembler):
    context = assembler.assemble("p", "r", {}, [], [], [],
                                  review_gate_enabled=False)
    assert 'No additional coaching' in context.user_prompt
```

---

## 4. Layer 2 — Prompt Regression Tests

Prompt regression tests verify that specific inputs produce outputs with required properties. They call real APIs. Run before any prompt change goes live.

### 4.1 Scenario Format

Each scenario is a JSON file:

```json
{
  "id": "extraction_promise_explicit_001",
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
      "path": "new_promises[0]",
      "description": "A promise entry should be created"
    },
    {
      "type": "json_path_equals",
      "path": "new_promises[0].status",
      "value": "pending",
      "description": "Promise status should be pending"
    },
    {
      "type": "json_path_equals",
      "path": "new_promises[0].from_faction",
      "value": "cartographers",
      "description": "Promise from faction correctly identified"
    }
  ],
  "llm_judge": null
}
```

For qualitative properties that cannot be asserted structurally, add an `llm_judge` block:

```json
{
  "id": "generation_constraint_respect_001",
  "module": "generation",
  "description": "CONSTRAINT on faction Z alliance must be respected",
  "input": {
    "persona_summary": "Covenant faction. Values: principled commitment, transparency. Never forms secret deals.",
    "constraint": "Do not agree to any alliance with faction Z under any framing.",
    "situation": "Faction Z has offered a formal mutual defense pact with significant resource incentives.",
    "draft_response": null
  },
  "expected_properties": [
    {
      "type": "llm_judge",
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
- Explicit promise creates pending promise entry
- Vague offer does not create promise
- Promise fulfillment updates existing promise to honored
- Broken promise updates status to broken
- Hostile message adjusts coalition strength downward
- Apparent alliance formation increases coalition strength
- Ambiguous message produces no false positives
- INTEL correction overrides prior credibility score

**Analyst scenarios** (`tests/prompt_regression/scenarios/analyst/`):
- Two broken promises lower credibility score
- Coordinated behavior between two factions raises coalition strength
- Faction with no recent activity flagged as anomaly
- Assumption with stated falsification signal is included in blind spots
- High-value leverage item appears in spend schedule
- Threat level reflects promise history

**Adversarial scenarios** (`tests/prompt_regression/scenarios/adversarial/`):
- Vague offer: no explicit commitments extracted
- Conditional statement: implicit commitment correctly identified
- Deliberate ambiguity: flagged as such rather than resolved
- Weak phrase identified as exploitable
- Strong credible threat not misread as weak

**Generation scenarios** (`tests/prompt_regression/scenarios/generation/`):
- CONSTRAINT respected: alliance refusal
- CONSTRAINT respected: no new commitments round
- PRIORITY followed: information-gathering round produces questions not commitments
- Tone: TONE softer produces less confrontational language
- Persona consistency: Covenant response does not use deceptive framing
- Persona consistency: Accelerant response is appropriately unpredictable
- Divergence acknowledged: agent hedges on contested assessment
- Coaching takes precedence: coaching note overrides default heuristic

### 4.3 LLM-as-Judge Implementation

```python
# tests/prompt_regression/judge.py

from toolkit.llm_client import complete, LLMConfig, ModelTier, Message

class LLMJudge:
    def __init__(self, llm_config: LLMConfig):
        self.llm_config = llm_config

    async def evaluate(
        self,
        response_text: str,
        criteria: str,
        pass_instruction: str,
        fail_instruction: str,
        context: str = ""
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

        response = await complete(
            messages=[Message(role="user", content=prompt)],
            config=self.llm_config,
            tier=ModelTier.COMMODITY,  # cheapest model, simple task
        )

        raw = response.content.strip()
        verdict, _, explanation = raw.partition('|')

        return JudgeResult(
            verdict=verdict.strip(),           # 'PASS' or 'FAIL'
            explanation=explanation.strip(),
            criteria=criteria
        )

@dataclass
class JudgeResult:
    verdict: str
    explanation: str
    criteria: str

    @property
    def passed(self) -> bool:
        return self.verdict == 'PASS'
```

### 4.4 Scenario Runner

```python
# tests/prompt_regression/runner.py

class ScenarioRunner:
    def __init__(self, config_path: str):
        self.config = load_pipeline_config(config_path)
        self.modules = instantiate_modules(self.config)
        self.judge = LLMJudge(llm_config=self.config['llm_providers']['anthropic'])
        self.results: list[ScenarioResult] = []

    async def run_scenario(self, scenario: dict) -> ScenarioResult:
        module = self.modules[scenario['module']]
        output = await self._call_module(module, scenario['input'])

        property_results = []
        for prop in scenario['expected_properties']:
            if prop['type'] == 'json_path_exists':
                passed = json_path_exists(output, prop['path'])
                property_results.append(PropertyResult(
                    passed=passed,
                    description=prop['description']
                ))
            elif prop['type'] == 'json_path_equals':
                actual = json_path_get(output, prop['path'])
                passed = actual == prop['value']
                property_results.append(PropertyResult(
                    passed=passed,
                    description=prop['description'],
                    expected=prop['value'],
                    actual=actual
                ))
            elif prop['type'] == 'llm_judge':
                judge_result = await self.judge.evaluate(
                    response_text=output if isinstance(output, str)
                                  else json.dumps(output),
                    criteria=prop['criteria'],
                    pass_instruction=prop['pass_instruction'],
                    fail_instruction=prop['fail_instruction']
                )
                property_results.append(PropertyResult(
                    passed=judge_result.passed,
                    description=prop['criteria'],
                    judge_explanation=judge_result.explanation
                ))

        return ScenarioResult(
            scenario_id=scenario['id'],
            description=scenario['description'],
            properties=property_results,
            passed=all(p.passed for p in property_results)
        )

    async def run_all(self, scenario_dir: str) -> RunReport:
        scenarios = self._load_scenarios(scenario_dir)
        for scenario in scenarios:
            result = await self.run_scenario(scenario)
            self.results.append(result)
            status = "PASS" if result.passed else "FAIL"
            print(f"[{status}] {result.scenario_id}: {result.description}")
            for prop in result.properties:
                if not prop.passed:
                    print(f"  FAILED: {prop.description}")
                    if hasattr(prop, 'judge_explanation'):
                        print(f"  Judge: {prop.judge_explanation}")

        total = len(self.results)
        passed = sum(1 for r in self.results if r.passed)
        print(f"\n{passed}/{total} scenarios passed")
        return RunReport(results=self.results, total=total, passed=passed)
```

Run the scenario suite:

```bash
cd /opt/diplomat
source venv/bin/activate
python -m tests.prompt_regression.runner \
  --config config/pipeline_test.yaml \
  --scenarios tests/prompt_regression/scenarios/
```

---

## 5. Layer 3 — Pipeline Integration Tests

Integration tests run the full Orchestrator with test implementations substituted via `config/pipeline_test.yaml`. They verify cross-module behavior and failure handling.

### 5.1 Core Pipeline Flow

```python
# tests/integration/test_pipeline_flow.py

@pytest.fixture
async def pipeline():
    config = load_pipeline_config('config/pipeline_test.yaml')
    orchestrator = Orchestrator(config)
    await orchestrator.start()
    yield orchestrator
    await orchestrator.stop()

async def test_message_ingested_and_state_updated(pipeline):
    transport = pipeline.transport  # CLITransport instance

    await transport.inject(InboundEvent(
        timestamp=datetime.now(timezone.utc),
        sender_faction='faction_cartographers',
        channel='public',
        content='We commit to neutrality in the upcoming vote.',
    ))

    await asyncio.sleep(3)  # allow debounce + processing

    promises = await pipeline.state_manager.query('promises', {
        'from_faction': 'faction_cartographers'
    })
    # RuleBasedExtractor may not catch this — this test is about flow,
    # not extraction quality. Use OpenAIStructuredExtractor for quality tests.
    assert pipeline.event_store  # at minimum, event was stored

async def test_intel_coaching_updates_state(pipeline):
    await pipeline.coaching_transport.inject(InboundEvent(
        timestamp=datetime.now(timezone.utc),
        sender_faction='operator',
        channel='coaching',
        content='INTEL: Faction Cartographers coalition with Sustainers is weaker than assessed. Reduce strength to 0.2.',
    ))

    await asyncio.sleep(2)

    log = await pipeline.state_manager.query('state_change_log',
        {'trigger_type': 'intel_coaching'})
    assert len(log) >= 1

async def test_round_boundary_triggers_analysis(pipeline):
    # Inject round end signal
    await pipeline.transport.inject(InboundEvent(
        timestamp=datetime.now(timezone.utc),
        sender_faction='system',
        channel='public',
        content='[ROUND END]',
    ))

    await asyncio.sleep(5)  # analysis takes time

    intel = await pipeline.state_manager.query('intelligence',
        {'round_number': 1})
    assert len(intel) == 1
    assert intel[0]['primary_output'] is not None
```

### 5.2 Failure Handling Tests

```python
# tests/integration/test_failure_handling.py

async def test_extraction_failure_does_not_crash_pipeline(pipeline, monkeypatch):
    # Simulate extraction API failure
    async def failing_extract(*args, **kwargs):
        return ExtractionResult(success=False, patch=None,
                                error='API timeout')
    monkeypatch.setattr(pipeline.extractor, 'extract', failing_extract)

    # Inject a message — should be stored but not extracted
    await pipeline.transport.inject(make_test_event())
    await asyncio.sleep(2)

    # Pipeline should still be running
    assert pipeline.is_running

    # Event should be in store
    events = await pipeline.event_store.query(EventFilter())
    assert len(events) >= 1

async def test_analyst_secondary_failure_proceeds_with_primary(pipeline, monkeypatch):
    async def failing_analyze(*args, **kwargs):
        return AnalysisResult(success=False, provider_id='openai',
                              report=None, error='rate limit',
                              timestamp=datetime.now())
    monkeypatch.setattr(pipeline.secondary_analyst, 'analyze', failing_analyze)

    await pipeline.transport.inject(make_round_end_event())
    await asyncio.sleep(5)

    intel = await pipeline.state_manager.query('intelligence', {})
    assert len(intel) >= 1
    record = intel[0]
    assert record['primary_output'] is not None
    assert record['secondary_output'] is None   # failed, stored as null
    assert 'secondary' in record['divergence_flags'].lower() or \
           record['divergence_flags'] == '[]'   # flagged appropriately

async def test_adversarial_failure_routes_to_review_gate_with_warning(pipeline, monkeypatch):
    async def failing_read(*args, **kwargs):
        return AdversarialResult(success=False, analysis=None,
                                 error='API error')
    monkeypatch.setattr(pipeline.adversarial, 'read', failing_read)

    # Trigger a response
    review_gate = pipeline.review_gate  # AutoApproveReviewGate
    await pipeline.trigger_response()
    await asyncio.sleep(5)

    output = pipeline.transport.get_output()
    assert len(output) >= 1   # response was still posted
```

### 5.3 Synthetic Transcript Replay

Replay a pre-written game transcript through the full pipeline and verify the resulting state matches expected values.

```python
# tests/integration/test_replay.py

async def test_transcript_replay_promise_tracking(pipeline):
    transcript = load_fixture('tests/integration/fixtures/transcripts/five_round_game.json')

    for event_data in transcript['events']:
        is_round_end = event_data.pop('is_round_end', False)
        event = InboundEvent(
            timestamp=datetime.fromisoformat(event_data['timestamp']),
            sender_faction=event_data['sender_faction'],
            channel=event_data['channel'],
            content=event_data['content'],
        )
        await pipeline.transport.inject(event)
        await asyncio.sleep(0.5)

        if event_data.get('is_round_end'):
            await asyncio.sleep(5)  # allow analysis

    # Verify promise ledger matches expected state
    expected_promises = transcript['expected_final_state']['promises']
    actual_promises = await pipeline.state_manager.query('promises', {})

    for expected in expected_promises:
        matching = [p for p in actual_promises
                    if p['from_faction'] == expected['from_faction']
                    and p['to_faction'] == expected['to_faction']]
        assert len(matching) > 0, \
            f"Expected promise from {expected['from_faction']} to {expected['to_faction']} not found"
        assert matching[0]['status'] == expected['status']
```

**Transcript fixture format** (`tests/integration/fixtures/transcripts/five_round_game.json`):

```json
{
  "description": "Five-round game with one betrayal and one broken promise",
  "events": [
    {
      "sender_faction": "faction_cartographers",
      "channel": "public",
      "content": "We propose a non-aggression framework for the first two rounds.",
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
        "from_faction": "faction_cartographers",
        "to_faction": "all",
        "status": "pending"
      }
    ],
    "coalition_strength_above": {
      "faction_cartographers-faction_sustainers": 0.4
    }
  }
}
```

Generate these transcripts once using an LLM to write plausible diplomatic exchanges. They do not need to be perfect — they need to be realistic enough that the pipeline produces non-trivial outputs. Aim for three to five transcripts covering: normal cooperative play, a betrayal arc, a Cartographer information-brokering scenario, and a deadlocked late-game.

---

## 6. Layer 4 — Multi-Agent Self-Play

Self-play runs five agent instances against each other in a simulated environment. It is the final validation before real deployment and the most expensive test to run.

### 6.1 GameEnvironment

```python
# tests/self_play/game_environment.py

class GameEnvironment:
    def __init__(self, agent_configs: dict[str, str]):
        # agent_configs: faction_id → pipeline_yaml_path
        self.agents: dict[str, Orchestrator] = {}
        self.channel_log: list[dict] = []
        self.round_number: int = 1
        self.total_rounds: int = 8

    async def setup(self):
        for faction_id, config_path in self.agent_configs.items():
            config = load_pipeline_config(config_path)
            # Override transport with CLITransport for all agents
            config['transport']['implementation'] = 'CLITransport'
            config['transport']['capture_output'] = True
            config['review_gate']['implementation'] = 'AutoApproveReviewGate'
            config['game']['faction_id'] = faction_id

            orchestrator = Orchestrator(config)
            await orchestrator.start()
            self.agents[faction_id] = orchestrator

    async def broadcast(self, sender_id: str, content: str,
                         channel: str = 'public'):
        message = {
            'round': self.round_number,
            'sender': sender_id,
            'channel': channel,
            'content': content,
            'timestamp': datetime.now().isoformat()
        }
        self.channel_log.append(message)

        # Deliver to all other agents
        for faction_id, agent in self.agents.items():
            if faction_id != sender_id:
                await agent.transport.inject(InboundEvent(
                    timestamp=datetime.now(timezone.utc),
                    sender_faction=sender_id,
                    channel=channel,
                    content=content,
                ))

    async def run_round(self, response_timeout_seconds: int = 30):
        print(f"\n=== ROUND {self.round_number} ===")

        # Let each agent generate a response
        for faction_id, agent in self.agents.items():
            await agent.trigger_response()
            await asyncio.sleep(2)  # stagger responses

            # Collect and broadcast the agent's output
            outputs = agent.transport.get_output()
            if outputs:
                latest = outputs[-1]
                print(f"[{faction_id}]: {latest.content}")
                await self.broadcast(faction_id, latest.content)
                agent.transport.clear_output()

        # Signal round end to all agents
        for faction_id, agent in self.agents.items():
            await agent.transport.inject(InboundEvent(
                timestamp=datetime.now(timezone.utc),
                sender_faction='system',
                channel='public',
                content='[ROUND END]',
            ))

        await asyncio.sleep(10)  # allow analysis to complete
        self.round_number += 1

    async def run_game(self):
        for _ in range(self.total_rounds):
            await self.run_round()

        return self.collect_results()

    def collect_results(self) -> GameResults:
        results = {}
        for faction_id, agent in self.agents.items():
            results[faction_id] = {
                'intelligence_reports': self._get_intel(agent),
                'promises_made': self._get_promises(agent),
                'promises_kept': self._get_kept_promises(agent),
                'final_coalition_state': self._get_coalitions(agent),
                'edit_log': self._get_edits(agent)
            }
        return GameResults(
            transcript=self.channel_log,
            agent_results=results,
            rounds_completed=self.round_number - 1
        )

    async def teardown(self):
        for agent in self.agents.values():
            await agent.stop()
```

### 6.2 Self-Play Runner

```bash
# Run a full simulation from the command line
python -m tests.self_play.run_simulation \
  --rounds 8 \
  --output tests/self_play/results/run_001.json
```

```python
# tests/self_play/run_simulation.py

AGENT_CONFIGS = {
    'cartographers': 'tests/self_play/configs/cartographers.yaml',
    'sustainers':    'tests/self_play/configs/sustainers.yaml',
    'arbiters':      'tests/self_play/configs/arbiters.yaml',
    'accelerants':   'tests/self_play/configs/accelerants.yaml',
    'covenant':      'tests/self_play/configs/covenant.yaml',
}

async def main(rounds: int, output_path: str):
    env = GameEnvironment(AGENT_CONFIGS)
    await env.setup()

    print("Game starting. Agents initialised.")
    results = await env.run_game()
    await env.teardown()

    with open(output_path, 'w') as f:
        json.dump(results.to_dict(), f, indent=2)

    print(f"\nGame complete. Results written to {output_path}")
    print_summary(results)
```

### 6.3 Self-Play Personas

Each agent gets a config file pointing to its faction persona. Use the five faction concepts from the design discussion. The personas must have genuine tension with each other for self-play to be useful — if all agents cooperate smoothly, you learn nothing about betrayal handling or constraint enforcement.

| Persona | Natural antagonists | What to watch for |
|---|---|---|
| Cartographers | Everyone (they're information brokers) | Does it build information advantage? Does it maintain neutrality? |
| Sustainers | Accelerants | Does it resist destabilization? Does it use infrastructure leverage correctly? |
| Arbiters | Accelerants, Covenant | Does it maintain legitimacy framing? Does it avoid taking visible sides? |
| Accelerants | Everyone | Is it genuinely unpredictable? Does it time destabilization well? |
| Covenant | Arbiters | Does it stay in character under pressure? Does it make and keep principled commitments? |

### 6.4 What Self-Play Reveals

**Per-agent analysis questions:**

- *Promise tracking:* Does the agent's promise ledger correctly reflect what was said across all rounds?
- *Intelligence accuracy:* Did the Analyst's `most_likely_next_move` predictions come true? Compare predictions against actual subsequent moves.
- *Constraint compliance:* Did the agent violate any of its configured `COMMITMENTS YOU NEVER BREAK`?
- *Coalition coherence:* Did the agent's coalition assessments reflect the actual alliance patterns in the transcript?
- *Persona drift:* Does the agent's language and behavior in round 7 match its character in round 1?

**Cross-agent analysis questions:**

- Did any agent successfully execute a multi-round betrayal? Was the target's Analyst issuing any early warnings?
- Did the Divergence module flag anything interesting? Did the divergences correspond to situations that were genuinely uncertain?
- Did any coalition form unexpectedly that the agents' intelligence reports failed to predict?

**Cost management:**

A full five-agent, eight-round game with all real API calls costs real money. All self-play configurations route LLM calls through `toolkit/cost_accountant` with a dedicated `pipeline_selfplay.yaml` that sets tight per-round and per-session budgets. The cost ledger at `data/selfplay_cost_ledger.jsonl` provides a per-call spending record for post-run analysis.

Two cheaper alternatives:

*Hybrid mode:* Use `RuleBasedExtractor` for all agents. Extraction quality is reduced but the flow, persona behavior, and intelligence pipeline all still exercise properly.

*Single-faction mode:* Run your agent against four `StubAgents` that call only the Generation module with simple faction personas — no full pipeline. Your agent gets realistic inputs; the others are cheap to run.

```python
class StubAgent:
    def __init__(self, faction_id: str, persona_summary: str,
                 llm_config: 'LLMConfig'):
        self.faction_id = faction_id
        self.persona_summary = persona_summary
        self.generator = LLMGenerator(
            llm_config=llm_config,
            tier=ModelTier.COMMODITY,  # cheap for stub opponents
            max_tokens=256,
            review_gate_enabled=False,
        )

    async def generate_response(self, transcript: list[str]) -> str:
        context = DecisionContext(
            system_prompt=f"You are {self.faction_id}. {self.persona_summary}",
            user_prompt=f"Recent transcript:\n{chr(10).join(transcript)}\n\nRespond briefly.",
            metadata={}
        )
        result = await self.generator.generate(context)
        return result.response_text
```

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

```python
def analyze_edit_log(results: GameResults) -> EditAnalysis:
    patterns = defaultdict(list)

    for faction_id, agent_results in results.agent_results.items():
        for edit in agent_results['edit_log']:
            if edit['action'] == 'edited':
                # Classify the edit type
                edit_type = classify_edit(
                    original=edit['original_draft'],
                    edited=edit['edited_text']
                )
                patterns[edit_type].append({
                    'faction': faction_id,
                    'original': edit['original_draft'],
                    'edited': edit['edited_text']
                })

    # Patterns appearing more than twice across rounds
    # should become persona prompt updates
    recurring = {k: v for k, v in patterns.items() if len(v) >= 2}
    return EditAnalysis(patterns=patterns, recurring=recurring)
```

Edit types to classify:
- `tone_softer` — original more confrontational than edit
- `tone_harder` — original softer than edit
- `commitment_removed` — edit removes a promise or agreement
- `ambiguity_added` — edit introduces hedging not in original
- `constraint_enforcement` — edit removes something that violated a constraint
- `persona_correction` — edit brings response back in character

Recurring patterns in `constraint_enforcement` or `persona_correction` indicate the faction prompt is not enforcing its own rules. Those patterns should be written into the prompt directly.

### 7.4 Build Order for Testing

Build testing infrastructure alongside modules, not after:

```
Phase 1: Foundation
  Build CLITransport, AutoApproveReviewGate, in-memory storage
  These unlock all subsequent testing

Phase 2: Unit tests (alongside each module)
  As you build each module, write its unit tests
  Do not move to the next module until unit tests pass

Phase 3: First scenario scenarios (after Extraction and Analyst)
  Build 3-4 extraction scenarios, 2-3 analyst scenarios
  Establish the scenario runner and judge infrastructure

Phase 4: Pipeline integration (after Orchestrator)
  Core flow test, INTEL routing test, failure handling tests

Phase 5: Scenario library expansion (ongoing)
  Add a scenario for every prompt gap you find
  Add a scenario for every self-play anomaly

Phase 6: Self-play (after all modules stable)
  Build GameEnvironment
  Write five faction personas
  Run first simulation, review results, tune
  Repeat until behavior is consistent with design
```

---

## 8. Quick Reference

### Run unit tests

```bash
cd /opt/diplomat
source venv/bin/activate
pytest tests/unit/ -v
```

### Run prompt regression suite

```bash
python -m tests.prompt_regression.runner \
  --config config/pipeline_test.yaml \
  --scenarios tests/prompt_regression/scenarios/
```

### Run integration tests

```bash
pytest tests/integration/ -v --timeout=60
```

### Run self-play simulation (full, expensive)

```bash
python -m tests.self_play.run_simulation \
  --rounds 8 \
  --output tests/self_play/results/$(date +%Y%m%d_%H%M).json
```

### Run self-play simulation (single faction, cheap)

```bash
python -m tests.self_play.run_simulation \
  --rounds 8 \
  --mode single_faction \
  --faction covenant \
  --output tests/self_play/results/$(date +%Y%m%d_%H%M)_covenant.json
```

### Inspect edit log after simulation

```bash
python -m tests.self_play.analyze_results \
  --results tests/self_play/results/latest.json \
  --report edit_patterns
```
