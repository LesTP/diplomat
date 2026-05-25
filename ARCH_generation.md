# ARCH: Generation

## Purpose
Produce the faction's next diplomatic message from assembled context. Calls toolkit/llm_client.complete() with the DecisionContext (system_prompt + user_prompt) produced by the Context Assembler. If the review gate is enabled, requests structured JSON output with both the response and the reasoning. Otherwise requests plain text.

## Public API

### generate
- **Signature:** `async def generate(self, context: DecisionContext) -> GenerationResult`
- **Parameters:**
  - context: DecisionContext — system_prompt and user_prompt from Context Assembler
- **Returns:** GenerationResult
- **Errors:** none — failures reported via GenerationResult.success=False

## Types

```python
@dataclass
class GenerationResult:
    success: bool
    response_text: str | None     # the diplomatic message to post
    reasoning: str | None         # populated if review gate mode (JSON output)
    raw_response: dict | None     # full LLM response for debugging
    error: str | None
```

## Implementation

**LLMGenerator** — calls `toolkit/llm_client.complete()` with provider and tier from pipeline.yaml (default: Anthropic at QUALITY).

Output format depends on review gate mode:
- **Review gate enabled:** prompt requests JSON `{"response": "...", "reasoning": "..."}`. The module parses and splits the response.
- **Review gate disabled:** prompt requests plain text. `reasoning` is None.

Provider swap is a pipeline.yaml config change — point `generation.provider` at a different `llm_providers` entry.

## Inputs
- DecisionContext from Context Assembler
- LLMConfig from pipeline.yaml
- Review gate enabled flag from pipeline.yaml

## Outputs
- GenerationResult — consumed by Adversarial (if enabled) and Review Gate

## State
None. Each generate() call is independent.

## Usage Example

```python
from modules.generation import LLMGenerator
from toolkit.llm_client import LLMConfig, ModelTier

generator = LLMGenerator(
    llm_config=anthropic_config,
    tier=ModelTier.QUALITY,
    max_tokens=1024,
    review_gate_enabled=True,
)

result = await generator.generate(context)
if result.success:
    print(f"Draft: {result.response_text}")
    print(f"Reasoning: {result.reasoning}")
```
