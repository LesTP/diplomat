# ARCH: Extraction

## Purpose
Convert raw text into structured state patches via LLM. Receives either game messages (trigger_type='message') or operator INTEL corrections (trigger_type='intel_correction') and produces a StatePatch conforming to the state_patch.json schema. Uses toolkit/llm_client at COMMODITY tier for cost efficiency. Includes a rule-based fallback for offline operation.

## Public API

### extract
- **Signature:** `async def extract(self, input_text: str, current_state: dict, trigger_type: str) -> ExtractionResult`
- **Parameters:**
  - input_text: str — raw message text or operator INTEL note
  - current_state: dict — current state snapshot from State Manager (provides context for extraction)
  - trigger_type: str — 'message' | 'intel_correction'
- **Returns:** ExtractionResult
- **Errors:** none — failures are reported via ExtractionResult.success=False

## Types

```python
@dataclass
class ExtractionResult:
    success: bool
    patch: StatePatch | None      # None on failure
    error: str | None             # error description on failure
```

## Implementations

**OpenAIStructuredExtractor** (primary) — calls `toolkit/llm_client.complete()` with `ModelTier.COMMODITY`. System prompt from `config/prompts/state_updater.txt`. The state_patch.json schema is included in the prompt for structured output enforcement. The module parses the LLM response as JSON and validates it against the schema before returning.

Few-shot examples are loaded from a JSON file at construction (default path: `config/examples/extraction_examples.json`; override via `pipeline.yaml` `paths.examples.extraction` or by passing `examples_path` directly). Examples used to be a Python constant `_EXTRACTION_EXAMPLES` — they were moved out to config in Phase 24.5 so prompt-tuning the example set is a config-only change (no code edit, no redeploy of compiled modules).

Trigger type handling:
- `'message'`: input is raw game messages, treated as observed facts
- `'intel_correction'`: input is prefixed with `[OPERATOR INTEL]`, treated as high-confidence override

Debounce: configured via `pipeline.yaml` `debounce_seconds`. The Orchestrator batches messages within this window and calls extract() once per batch. (Provisional — batching semantics to be resolved during implementation.)

**RuleBasedExtractor** (fallback) — pattern-matching for testing and offline operation. Returns empty patches for inputs it cannot parse. Never fails.

## Inputs
- Raw text from Transport (game messages) or Coaching (INTEL notes)
- Current state dict from State Manager
- System prompt from config/prompts/state_updater.txt
- Schema from config/schemas/state_patch.json
- LLMConfig from pipeline.yaml (via Orchestrator)

## Outputs
- ExtractionResult with StatePatch — consumed by State Manager via apply_patch()
- On failure: ExtractionResult with success=False, patch=None, error description

## State
None. Each extract() call is independent.

## Provisional Contract
toolkit/llm_client.complete() returns plain text. This module must handle JSON parsing and schema validation locally (prompt engineering + response parsing + jsonschema.validate). If this proves fragile, consider extending toolkit with a complete_structured() method. Resolve during implementation.

## Usage Example

```python
from modules.extraction import OpenAIStructuredExtractor
from toolkit.llm_client import LLMConfig, ModelTier

extractor = OpenAIStructuredExtractor(
    llm_config=llm_config,
    tier=ModelTier.COMMODITY,
    schema_path="config/schemas/state_patch.json",
    prompt_path="config/prompts/state_updater.txt",
)

current_state = await state_manager.get_full_state()

# Game message extraction
result = await extractor.extract(
    input_text="Alpha promises Beta non-aggression through round 6.",
    current_state=current_state,
    trigger_type="message",
)
if result.success:
    await state_manager.apply_patch(result.patch, PatchSource("message", event_id))

# INTEL correction
result = await extractor.extract(
    input_text="Alpha actually broke the promise in round 4",
    current_state=current_state,
    trigger_type="intel_correction",
)
if result.success:
    await state_manager.apply_patch(result.patch, PatchSource("intel_coaching", coaching_id))
```
