# ARCH: Adversarial

## Purpose
Analyse a draft response from the perspective of an opposing faction. The adversarial reader asks: what does this message reveal, commit to, and where is it exploitable? Returns structured analysis for the operator to review alongside the draft in the Review Gate. Fully optional — if `adversarial.enabled: false` in pipeline.yaml, the Orchestrator skips this module entirely.

Fully decoupled from the pipeline. Can be imported and used standalone in other applications.

## Public API

### read
- **Signature:** `async def read(self, draft: str) -> AdversarialResult`
- **Parameters:**
  - draft: str — the draft response text from Generation
- **Returns:** AdversarialResult
- **Errors:** none — failures reported via AdversarialResult.success=False

## Types

```python
@dataclass
class AdversarialResult:
    success: bool
    analysis: dict | None         # validated against config/schemas/adversarial.json
    error: str | None
```

## Implementation

**LLMAdversarialReader** — calls `toolkit/llm_client.complete()` with provider and tier from pipeline.yaml (default: OpenAI at QUALITY). System prompt from `config/prompts/adversarial.txt`. Response validated against `config/schemas/adversarial.json`.

The analysis dict typically contains:
- What the message reveals about the faction's position
- What commitments it makes (explicit and implicit)
- Where an opponent could exploit ambiguity or inconsistency
- Suggested counter-moves an opponent might make

## Inputs
- Draft response text from Generation
- LLMConfig from pipeline.yaml
- System prompt from config/prompts/adversarial.txt
- Schema from config/schemas/adversarial.json

## Outputs
- AdversarialResult — consumed by Review Gate (displayed to operator alongside draft)
- Stored in adversarial_reads table by Orchestrator

## State
None. Each read() call is independent.

## Usage Example

```python
from modules.adversarial import LLMAdversarialReader
from toolkit.llm_client import LLMConfig, ModelTier

reader = LLMAdversarialReader(
    llm_config=openai_config,
    tier=ModelTier.QUALITY,
    prompt_path="config/prompts/adversarial.txt",
    schema_path="config/schemas/adversarial.json",
)

result = await reader.read("We propose a non-aggression pact for rounds 4-6.")
if result.success:
    print(result.analysis)
    # {"reveals": [...], "commits_to": [...], "exploitable": [...], "counter_moves": [...]}

# Standalone usage (outside Diplomat pipeline)
from modules.adversarial import LLMAdversarialReader
reader = LLMAdversarialReader(llm_config, tier, prompt_path, schema_path)
result = await reader.read(any_draft_text)
```
