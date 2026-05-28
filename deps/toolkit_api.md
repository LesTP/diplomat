# Toolkit API Contracts

Vendored from toolkit source. Use these signatures when building fakes in tests.
Update when toolkit changes a consumed API.

Last synced: 2026-05-28

---

## toolkit.llm_client

### Types

```python
@dataclass
class Message:
    role: str                    # "system" | "user" | "assistant"
    content: str

class ModelTier(str, Enum):
    QUALITY = "quality"
    DEFAULT = "default"
    COMMODITY = "commodity"

@dataclass
class LLMConfig:
    provider: str                # "anthropic" | "openai" | "google"
    api_key: str
    models: dict[str, str]       # tier name → model ID, e.g. {"quality": "gpt-5.5"}
    max_tokens: int = 4096
    temperature: float = 0.7

@dataclass
class LLMResponse:
    content: str
    model: str
    provider: str
    token_usage: TokenUsage

@dataclass
class TokenUsage:
    input_tokens: int
    output_tokens: int

class LLMAPIError(Exception):
    message: str
    status_code: int | None
    retry_after: float | None

class LLMResponseError(Exception):
    message: str
```

### Functions

```python
complete(messages: list[Message], config: LLMConfig, tier: ModelTier = ModelTier.DEFAULT) -> LLMResponse
```

---

## toolkit.telegram_client

### Types

```python
class TelegramClient:
    def __init__(self, bot_token: str, *, transport: TelegramTransport | None = None,
                 request_timeout_seconds: float = 10.0, poll_timeout_seconds: float = 25.0) -> None

@dataclass(frozen=True)
class TelegramUpdate:
    chat_id: int
    user_id: int
    message_text: str            # NOTE: not "text" or "content"
    command: str | None
    args: tuple[str, ...]
    message_id: int
    raw: dict[str, Any]

@dataclass(frozen=True)
class SendResult:
    success: bool
    message_id: int | None = None
    error: str | None = None

class TelegramAPIError(TelegramClientError): ...
class TelegramClientError(Exception): ...
```

### Methods

```python
# TelegramClient
async send_message(chat_id: int, text: str, reply_to: int | None = None, *, parse_mode: str | None = None) -> int
async start_polling(*, initial_offset: int | None = None) -> None   # runs until stop_polling
async stop_polling() -> None
async get_next_update() -> TelegramUpdate | None
```

---

## toolkit.cost_accountant

### Types

```python
class CostAccountant:
    def __init__(self, ledger_path: Path, pricing: dict[str, ModelPricing] | None = None) -> None

@dataclass
class CostBudget:
    per_call_usd: float | None = None
    operation_usd: float | None = None
    session_usd: float | None = None
    abort_on_rate_limit: bool = False
    abort_on_spending_cap: bool = False

@dataclass
class CostEstimate:
    model: str
    input_tokens: int
    output_tokens: int
    estimated_cost_usd: float

@dataclass
class ModelPricing:
    input_per_million: float
    output_per_million: float

class BudgetExceededError(CostAccountantError): ...
class RateLimitAbortError(CostAccountantError): ...
class SpendingCapAbortError(CostAccountantError): ...
```

### Methods

```python
# CostAccountant
complete(messages: list[Message], config: LLMConfig, tier: ModelTier, *,
         budget: CostBudget | None = None, operation: str | None = None) -> LLMResponse
estimate_cost(model: str, input_tokens: int, output_tokens: int) -> CostEstimate
report(since: datetime | None = None) -> CostReport
```

---

## toolkit.prompt_regression

### Types

```python
@dataclass(frozen=True)
class PropertyCheck:
    type: str                    # "json_path_exists" | "json_path_equals" | "llm_judge"
    description: str
    path: str | None = None
    value: Any | None = None
    criteria: str | None = None
    pass_instruction: str | None = None
    fail_instruction: str | None = None

@dataclass(frozen=True)
class PropertyResult:
    passed: bool
    description: str
    expected: Any | None = None
    actual: Any | None = None
    judge_explanation: str | None = None

@dataclass(frozen=True)
class ScenarioResult:
    scenario_id: str
    description: str
    properties: list[PropertyResult]
    passed: bool

@dataclass(frozen=True)
class RunReport:
    results: list[ScenarioResult]
    total: int
    passed: int

@dataclass(frozen=True)
class JudgeResult:
    verdict: str                 # "PASS" | "FAIL"
    explanation: str
    criteria: str
```

### Functions

```python
load_scenario(path: str | Path) -> dict[str, Any]
load_scenarios(directory: str | Path) -> list[dict[str, Any]]
json_path_exists(data: Any, path: str) -> bool
json_path_get(data: Any, path: str) -> Any          # raises KeyError, IndexError, TypeError, ValueError
```

### Classes

```python
class LLMJudge:
    def __init__(self, llm_client: Any, llm_config: dict[str, Any], tier: str = "commodity") -> None
    async def evaluate(self, response_text: str, criteria: str,
                       pass_instruction: str, fail_instruction: str,
                       context: str = "") -> JudgeResult

class ScenarioRunner:
    def __init__(self, llm_client: Any, llm_config: dict[str, Any],
                 module_caller: Callable[[str, Any, dict], Awaitable[Any]]) -> None
    async def run_scenario(self, scenario: dict[str, Any]) -> ScenarioResult
    async def run_all(self, scenario_dir: str | Path, module_filter: str | None = None) -> RunReport
```

---

## toolkit.structured_llm

### Functions

```python
async structured_complete(llm_client: Any, config: dict[str, Any], tier: str,
                           messages: list[dict[str, str]]) -> str
parse_json_response(response_text: str) -> dict[str, Any]           # raises ValueError
validate_json_schema(data: dict[str, Any], schema: dict[str, Any],
                     label: str = "") -> None                        # raises ValueError
load_prompt(path: str | Path) -> str
load_schema(path: str | Path) -> dict[str, Any]                     # raises ValueError
```
