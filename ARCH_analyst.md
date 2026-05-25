# ARCH: Analyst + Divergence

## Purpose
**Analyst:** Produce a neutral strategic intelligence report from the current structured game state. A single `LLMAnalyst` implementation is parameterised by provider — the Orchestrator instantiates two instances (primary with Anthropic, secondary with OpenAI) from pipeline.yaml config. Each calls toolkit/llm_client.complete() independently. Both use the same prompt and schema.

**Divergence:** Pure Python comparison of two AnalysisResult objects. No API call. Applies configurable thresholds from pipeline.yaml to identify material disagreements. Returns a list of Divergence items for inclusion in the Context Assembler's output.

## Public API

### Analyst

#### analyze
- **Signature:** `async def analyze(self, state: dict) -> AnalysisResult`
- **Parameters:**
  - state: dict — full state snapshot from State Manager.get_full_state()
- **Returns:** AnalysisResult
- **Errors:** none — failures reported via AnalysisResult.success=False

### Divergence

#### compare
- **Signature:** `def compare(a: AnalysisResult, b: AnalysisResult) -> list[Divergence]`
- **Parameters:**
  - a: AnalysisResult — primary analyst output
  - b: AnalysisResult — secondary analyst output
- **Returns:** list[Divergence] — material disagreements (empty if analysts agree)
- **Errors:** none

## Types

```python
@dataclass
class AnalysisResult:
    success: bool
    provider_id: str              # from LLMConfig.provider (e.g., 'anthropic', 'openai')
    report: dict | None           # validated against config/schemas/intelligence.json
    error: str | None
    timestamp: datetime

@dataclass
class Divergence:
    field: str                    # which report field disagrees
    primary_value: str
    secondary_value: str
    note: str                     # human-readable explanation
```

## Configuration

From pipeline.yaml:

```yaml
analyst:
  primary:
    provider: anthropic
    tier: quality
  secondary:
    provider: openai
    tier: quality
  divergence_threshold:
    threat_level_steps: 1
    missing_leverage_item: true
    coalition_stability_mismatch: true
```

Both instances use:
- Prompt: `config/prompts/analyst.txt`
- Schema: `config/schemas/intelligence.json`

## Inputs
- Full state dict from State Manager
- LLMConfig from pipeline.yaml (one per instance)
- System prompt from config/prompts/analyst.txt
- Divergence thresholds from pipeline.yaml

## Outputs
- AnalysisResult (per instance) — consumed by Orchestrator, stored in intelligence table
- list[Divergence] — consumed by Context Assembler, stored in intelligence.divergence_flags

## State
None. Each analyze() call is independent. Divergence comparison is a pure function.

## Usage Example

```python
from modules.analyst import LLMAnalyst
from modules.analyst.divergence import compare
from toolkit.llm_client import LLMConfig, ModelTier

primary = LLMAnalyst(
    llm_config=anthropic_config,
    tier=ModelTier.QUALITY,
    prompt_path="config/prompts/analyst.txt",
    schema_path="config/schemas/intelligence.json",
    provider_id="anthropic",
)
secondary = LLMAnalyst(
    llm_config=openai_config,
    tier=ModelTier.QUALITY,
    prompt_path="config/prompts/analyst.txt",
    schema_path="config/schemas/intelligence.json",
    provider_id="openai",
)

state = await state_manager.get_full_state()

primary_result = await primary.analyze(state)
secondary_result = await secondary.analyze(state)

divergences = compare(primary_result, secondary_result)
```
