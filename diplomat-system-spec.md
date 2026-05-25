# AI Diplomat — System Specification
**Version 0.5 | AI Life Diplomacy Game Agent**

> **Note on provider APIs:** Model names, structured output syntax, and SDK versions should be verified against current provider documentation before implementing. Architectural decisions are stable; specific API calls will need review.

> **Shared dependencies:** This project consumes modules from the **toolkit** project for LLM calls, Telegram I/O, and cost governance. Diplomat does not depend on provider SDKs directly — all LLM and Telegram interactions go through toolkit's abstractions. See Section 3.6 for the dependency map.
>
> Toolkit location: `p:\shared\toolkit\`

---

## 1. Overview

This document specifies the architecture, module interfaces, implementations, storage schema, and operational setup for an AI faction agent in the AI Life Diplomacy game.

The system is designed as a set of loosely coupled modules, each owning one responsibility and exposing a typed interface. No module depends on another module's implementation — only on its interface. Domain logic lives in configuration files, not in code. This means:

- Individual modules can be reused in other applications by swapping configuration
- Wrong assumptions about the game or tech setup are corrected by changing one module's implementation, not by touching the pipeline
- The pipeline topology is owned by the Orchestrator alone; adding, removing, or reordering steps does not affect modules

The system targets a Raspberry Pi 4 or 5 running Raspberry Pi OS Lite 64-bit.

---

## 2. Hardware Requirements

| Component | Minimum | Recommended |
|---|---|---|
| Model | Raspberry Pi 4 | Raspberry Pi 5 |
| RAM | 4GB | 8GB |
| Storage | 32GB SD card | 128GB SSD via USB |
| Network | Ethernet | Ethernet (not Wi-Fi) |
| OS | Raspberry Pi OS Lite 64-bit | Raspberry Pi OS Lite 64-bit |

**Note on storage:** SQLite performs better on SSD under sustained write load. If SD card only, enable WAL mode and configure aggressive log rotation.

---

## 3. Module Architecture

### 3.1 Design Principles

**One responsibility per module.** Each module owns exactly one concern. The Transport module does not know what a faction is. The Analyst module does not know what database is underneath. The State Manager does not know what AI provider produced the patch it is applying.

**Depend on interfaces, not implementations.** All inter-module communication goes through defined interfaces. The Orchestrator selects implementations at startup based on config. Modules never instantiate other modules directly.

**Configuration over code for domain logic.** The game's specific entities, prompts, personas, routing rules, and pipeline topology are files in the config directory. A different application or a different game setup changes config files. A different platform or provider changes one module implementation. Neither requires touching other modules.

**Fail locally.** Each module handles its own failures and returns a typed result indicating success or failure. The Orchestrator decides how to handle a module failure — skip, retry, fallback — without propagating exceptions across module boundaries.

### 3.2 Module Registry

| Module | Responsibility | Interface defined in |
|---|---|---|
| Transport | Platform I/O (send/receive) | `modules/transport/__init__.py` |
| Event Store | Append-only raw event log | `modules/event_store/__init__.py` |
| State Manager | Structured domain state | `modules/state_manager/__init__.py` |
| Extraction | Text → structured state patch | `modules/extraction/__init__.py` |
| Analyst | Structured state → intelligence report | `modules/analyst/__init__.py` |
| Divergence | Compare two analysis outputs | `modules/analyst/divergence.py` |
| Persona | Faction identity configuration | `modules/persona/__init__.py` |
| Context Assembler | Assemble Decision Engine input | `modules/context_assembler/__init__.py` |
| Generation | Context → response text | `modules/generation/__init__.py` |
| Adversarial | Draft → adversarial analysis | `modules/adversarial/__init__.py` |
| Coaching | Parse and route operator input | `modules/coaching/__init__.py` |
| Review Gate | Human approval workflow | `modules/review_gate/__init__.py` |
| Orchestrator | Pipeline topology and wiring | `orchestrator.py` |

### 3.3 Module Interfaces

#### Transport

```python
class Transport(ABC):
    async def send(self, message: OutboundMessage) -> None: ...
    async def listen(self) -> AsyncIterator[InboundEvent]: ...

@dataclass
class OutboundMessage:
    content: str
    channel: str          # 'public' | 'private' | 'coaching'
    recipient: str | None # faction_id for private, None for public

@dataclass
class InboundEvent:
    source: str           # faction_id | 'operator' | 'system'
    channel: str          # 'public' | 'private' | 'coaching'
    content: str
    timestamp: datetime
    metadata: dict        # platform-specific, opaque to other modules
```

#### Event Store

```python
class EventStore(ABC):
    async def append(self, event: InboundEvent, round_number: int) -> str: ...
    async def query(self, filters: EventFilter) -> list[StoredEvent]: ...

@dataclass
class EventFilter:
    round_number: int | None = None
    source: str | None = None
    channel: str | None = None
    since: datetime | None = None
    limit: int = 100

@dataclass
class StoredEvent:
    event_id: str
    round_number: int
    event: InboundEvent
```

#### State Manager

```python
class StateManager(ABC):
    async def get(self, entity_type: str, entity_id: str) -> dict | None: ...
    async def query(self, entity_type: str, filters: dict) -> list[dict]: ...
    async def apply_patch(self, patch: StatePatch, source: PatchSource) -> None: ...
    async def get_full_state(self) -> dict: ...  # for Analyst input

@dataclass
class PatchSource:
    trigger_type: str     # 'message' | 'intel_coaching'
    trigger_ref: str      # event_id or coaching_id

# StatePatch schema is loaded from config/schemas/state_patch.json
# and validated at runtime — not hardcoded in this interface
@dataclass
class StatePatch:
    data: dict            # validated against schema at apply time
```

#### Extraction

```python
class Extractor(ABC):
    async def extract(
        self,
        input_text: str,
        current_state: dict,
        trigger_type: str         # 'message' | 'intel_correction'
    ) -> ExtractionResult:  ...

@dataclass
class ExtractionResult:
    success: bool
    patch: StatePatch | None
    error: str | None
```

#### Analyst

```python
class Analyst(ABC):
    provider_id: str

    async def analyze(self, state: dict) -> AnalysisResult: ...

@dataclass
class AnalysisResult:
    success: bool
    provider_id: str
    report: dict | None           # validated against intelligence schema
    error: str | None
    timestamp: datetime
```

#### Divergence (sub-module, not swappable)

```python
def compare(a: AnalysisResult, b: AnalysisResult) -> list[Divergence]: ...

@dataclass
class Divergence:
    field: str
    primary_value: str
    secondary_value: str
    note: str
```

#### Persona

```python
class Persona(ABC):
    async def get_base_prompt(self) -> str: ...
    async def build_round_context(
        self,
        round_number: int,
        rounds_remaining: int | None,
        coaching_context: CoachingContext
    ) -> str: ...

@dataclass
class CoachingContext:
    priorities: list[str]
    constraints: list[str]
    watch_items: list[str]
    tone_notes: list[str]
```

#### Context Assembler

```python
class ContextAssembler(ABC):
    async def assemble(
        self,
        persona_prompt: str,
        round_context: str,
        intelligence: dict,
        divergences: list[Divergence],
        recent_events: list[StoredEvent],
        free_coaching: list[CoachingEntry],
        review_gate_enabled: bool
    ) -> DecisionContext: ...

@dataclass
class DecisionContext:
    system_prompt: str
    user_prompt: str
    metadata: dict
```

#### Generation

```python
class Generator(ABC):
    async def generate(self, context: DecisionContext) -> GenerationResult: ...

@dataclass
class GenerationResult:
    success: bool
    response_text: str | None
    reasoning: str | None         # populated if review gate mode
    raw_response: dict | None
    error: str | None
```

#### Adversarial

```python
class AdversarialReader(ABC):
    async def read(self, draft: str) -> AdversarialResult: ...

@dataclass
class AdversarialResult:
    success: bool
    analysis: dict | None         # validated against adversarial schema
    error: str | None
```

#### Coaching

```python
class CoachingParser(ABC):
    def parse(self, raw_input: str) -> CoachingEvent | Command: ...

@dataclass
class CoachingEvent:
    coaching_type: str    # 'PRIORITY'|'CONSTRAINT'|'INTEL'|'TONE'|'WATCH'|'FREE'
    content: str
    route: str            # 'state_updater' | 'coaching_queue'

@dataclass
class Command:
    name: str             # 'preview'|'approve'|'edit'|'block'|'status'|etc.
    args: dict
```

#### Review Gate

```python
class ReviewGate(ABC):
    async def submit(
        self,
        draft: GenerationResult,
        adversarial: AdversarialResult,
        round_number: int
    ) -> ReviewDecision: ...

@dataclass
class ReviewDecision:
    action: str                   # 'approved' | 'edited' | 'blocked'
    final_text: str | None        # None if blocked
    edit_notes: str | None
```

### 3.4 Toolkit Dependencies

Diplomat consumes the following toolkit modules. No Diplomat module imports a provider SDK (`anthropic`, `openai`, `python-telegram-bot`) directly — all external API calls go through toolkit abstractions.

| Toolkit Module | Diplomat Consumer(s) | What it replaces |
|---|---|---|
| `toolkit/llm_client` | Extraction, Analyst (×2), Generation, Adversarial | Direct `anthropic` / `openai` SDK calls |
| `toolkit/telegram_client` | Transport (`TelegramBotTransport`) | `python-telegram-bot` library |
| `toolkit/cost_accountant` | Orchestrator (wraps all LLM calls) | Nothing — fills a gap in the original spec |

**LLM Client** (`toolkit/llm_client`) — provider-agnostic interface with `complete(messages, config, tier)`. Supports Anthropic, OpenAI, Google, and OpenRouter. Provides model tiers (`QUALITY` / `DEFAULT` / `COMMODITY`), rate-limit tracking, and multi-provider rotation via `complete_with_rotation()`. Each Diplomat module that calls an LLM receives an `LLMConfig` from the Orchestrator at startup; the module passes it to `toolkit/llm_client.complete()` with the appropriate tier.

**Telegram Client** (`toolkit/telegram_client`) — async Telegram Bot API client with `send_message()`, `start_polling()` / `get_next_update()`, `edit_message()`, MarkdownV2 formatting, message splitting, and Telegraph overflow. Used by `TelegramBotTransport` and `TelegramReviewGate` instead of the `python-telegram-bot` library.

**Cost Accountant** (`toolkit/cost_accountant`) — wraps `toolkit/llm_client` with pre-call cost estimation, per-call / per-operation / per-session budget enforcement, and an append-only JSONL cost ledger. The Orchestrator routes all LLM calls through a `CostAccountant` instance with per-round budgets. Prevents runaway API spend during heavy message rounds.

Toolkit reference: `toolkit/ARCHITECTURE.md`, individual module specs in `toolkit/ARCH_*.md`.

### 3.5 Configuration vs. Code

The rule: if it describes *what* the system does in a specific domain, it is config. If it describes *how* to do something generically, it is code.

| Item | Type | Location |
|---|---|---|
| Pipeline topology | Code (Orchestrator) | `src/orchestrator.py` |
| Module implementation selection | Config | `config/pipeline.yaml` |
| Provider credentials | Config | `config/.env` |
| LLM provider/model/tier mapping | Config | `config/pipeline.yaml` (mapped to `toolkit.llm_client.LLMConfig`) |
| Cost budgets (per-round, per-session) | Config | `config/pipeline.yaml` (mapped to `toolkit.cost_accountant.CostBudget`) |
| State patch schema | Config | `config/schemas/state_patch.json` |
| Intelligence report schema | Config | `config/schemas/intelligence.json` |
| Adversarial analysis schema | Config | `config/schemas/adversarial.json` |
| State updater prompt | Config | `config/prompts/state_updater.txt` |
| Analyst prompt | Config | `config/prompts/analyst.txt` |
| Adversarial prompt | Config | `config/prompts/adversarial.txt` |
| Faction persona | Config | `config/faction_prompt.txt` |
| Coaching tag routing rules | Config | `config/coaching_routes.yaml` |
| Round detection pattern | Config | `config/pipeline.yaml` |

A different application reuses all code and replaces the config directory. A different faction is a different `faction_prompt.txt`. A different platform is a different Transport implementation registered in `pipeline.yaml`.

### 3.6 Pipeline Configuration File

`config/pipeline.yaml` is the single file that wires the system:

```yaml
transport:
  implementation: TelegramBotTransport   # or TelethonUserTransport, CLITransport
  public_channel_id: "-100xxxxxxxxxx"
  coaching_channel_id: "-100xxxxxxxxxx"
  # TelegramBotTransport wraps toolkit/telegram_client internally

event_store:
  implementation: SQLiteEventStore
  path: data/game.db

state_manager:
  implementation: SQLiteStateManager
  path: data/game.db
  schema: config/schemas/state_patch.json

extraction:
  implementation: OpenAIStructuredExtractor
  tier: commodity                         # maps to toolkit ModelTier.COMMODITY
  schema: config/schemas/state_patch.json
  prompt: config/prompts/state_updater.txt
  debounce_seconds: 2
  fallback: RuleBasedExtractor           # used if API unavailable

analyst:
  primary:
    implementation: LLMAnalyst
    provider: anthropic                   # uses llm_providers.anthropic config
    tier: quality                         # maps to toolkit ModelTier.QUALITY
    prompt: config/prompts/analyst.txt
    schema: config/schemas/intelligence.json
  secondary:
    implementation: LLMAnalyst
    provider: openai                      # uses llm_providers.openai config
    tier: quality
    prompt: config/prompts/analyst.txt
    schema: config/schemas/intelligence.json
  divergence_threshold:
    threat_level_steps: 1
    missing_leverage_item: true
    coalition_stability_mismatch: true

persona:
  implementation: FileBasedPersona
  path: config/faction_prompt.txt

context_assembler:
  implementation: DefaultContextAssembler
  recent_events_limit: 30

generation:
  implementation: LLMGenerator
  provider: anthropic                     # uses llm_providers.anthropic config
  tier: quality
  max_tokens: 1024

adversarial:
  implementation: LLMAdversarialReader
  provider: openai                        # uses llm_providers.openai config
  tier: quality
  prompt: config/prompts/adversarial.txt
  schema: config/schemas/adversarial.json
  enabled: true                          # set false to skip step

coaching:
  implementation: TaggedCoachingParser
  routes: config/coaching_routes.yaml

review_gate:
  implementation: TelegramReviewGate
  enabled: true                          # set false to auto-approve

round:
  mode: signal                           # 'signal' | 'time'
  signal_pattern: "[ROUND END]"
  duration_minutes: 30                   # used if mode=time

game:
  total_rounds: unknown
  faction_id: your_faction_id
  faction_map:
    username1: faction_id_1
    username2: faction_id_2
    username3: faction_id_3
    username4: faction_id_4

# --- Toolkit integration ---

llm_providers:
  anthropic:
    api_key: ${ANTHROPIC_API_KEY}
    models:
      quality: claude-sonnet-4-20250514   # verify before use
      default: claude-sonnet-4-20250514
      commodity: claude-haiku-4-5
  openai:
    api_key: ${OPENAI_API_KEY}
    models:
      quality: gpt-4o                     # verify before use
      default: gpt-4o
      commodity: gpt-4o-mini

cost:
  ledger_path: data/cost_ledger.jsonl
  per_round_budget_usd: 2.00
  per_session_budget_usd: 50.00
  per_call_max_usd: 0.50
  abort_on_rate_limit: true
  abort_on_spending_cap: true
```

---

## 4. System Architecture

### 4.1 Module Boundary Diagram

```
┌─────────────────────────────────────────────────────────────┐
│  MODULE: TRANSPORT                                           │
│  Impl: TelegramBotTransport | TelethonUserTransport | ...   │
│  Uses: toolkit/telegram_client                               │
│  Exposes: InboundEvent stream, send(OutboundMessage)         │
└────────────────┬──────────────────────────────┬─────────────┘
                 │ InboundEvent                 │ OutboundMessage
    ┌────────────▼──────────────────────────────▼─────────────┐
    │                    ORCHESTRATOR                          │
    │  Wires modules. Owns pipeline topology.                  │
    │  Selects implementations from pipeline.yaml.             │
    │  Owns CostAccountant (toolkit/cost_accountant).          │
    └──┬────────────┬──────────────┬───────────────┬──────────┘
       │            │              │               │
       ▼            ▼              ▼               ▼
┌──────────┐ ┌────────────┐ ┌──────────┐  ┌──────────────────┐
│  MODULE  │ │   MODULE   │ │  MODULE  │  │     MODULE       │
│  EVENT   │ │   STATE    │ │ COACHING │  │   ROUND MGR      │
│  STORE   │ │  MANAGER   │ │  PARSER  │  │  (in Orchestr.)  │
└──┬───────┘ └──────┬─────┘ └────┬─────┘  └──────────────────┘
   │                │            │
   │         ┌──────▼─────┐      │
   │         │  MODULE    │      │ INTEL route
   │         │ EXTRACTION │◄─────┘
   │         │ (via t/llm)│
   │         └──────┬─────┘
   │                │ StatePatch
   │         ┌──────▼─────┐
   │         │  (State    │
   │         │  Manager   │
   │         │  apply)    │
   │         └────────────┘
   │
   │    (round boundary)
   │         ┌─────────────────────────────┐
   │         │  MODULE: ANALYST (PRIMARY)  │
   │         │  Impl: LLMAnalyst           │
   │         │  Provider: anthropic        │
   │         └──────────────┬──────────────┘
   │                        │ AnalysisResult
   │         ┌──────────────▼──────────────┐
   │         │  MODULE: ANALYST (SECONDARY)│
   │         │  Impl: LLMAnalyst           │
   │         │  Provider: openai           │
   │         └──────────────┬──────────────┘
   │                        │ AnalysisResult ×2
   │                  DIVERGENCE sub-module
   │                        │ List[Divergence]
   │                        ▼
   │         ┌──────────────────────────────┐
   │         │  MODULE: PERSONA             │
   │         │  Impl: FileBasedPersona      │
   │         └──────────────┬───────────────┘
   │                        │ persona_prompt + round_context
   └───────────────────┐    │
   StoredEvents        │    │
                ┌──────▼────▼───────────────┐
                │  MODULE: CONTEXT ASSEMBLER │
                │  Impl: DefaultAssembler    │
                └──────────────┬────────────┘
                               │ DecisionContext
                ┌──────────────▼────────────┐
                │  MODULE: GENERATION        │
                │  Impl: LLMGenerator        │
                │  (via toolkit/llm_client)  │
                └──────────────┬────────────┘
                               │ GenerationResult
                ┌──────────────▼────────────┐
                │  MODULE: ADVERSARIAL       │
                │  Impl: LLMAdversarial      │
                │  (via toolkit/llm_client)  │
                │  (skipped if disabled)     │
                └──────────────┬────────────┘
                               │ draft + AdversarialResult
                ┌──────────────▼────────────┐
                │  MODULE: REVIEW GATE       │
                │  Impl: TelegramReviewGate  │
                │  Uses: toolkit/tg_client   │
                │  (auto-approve if disabled)│
                └──────────────┬────────────┘
                               │ ReviewDecision.final_text
                        Transport.send()

    All LLM calls flow through toolkit/cost_accountant
    → toolkit/llm_client → provider SDK (anthropic | openai)
```

---

## 5. Module Implementations

### 5.1 Transport

**TelegramBotTransport** — wraps `toolkit/telegram_client.TelegramClient`. Uses `start_polling()` / `get_next_update()` for inbound events and `send_message()` for outbound. Default implementation.

**TelethonUserTransport** — uses `Telethon`. Required if bot-to-bot messaging is unavailable. Swap by changing `transport.implementation` in `pipeline.yaml`. No other files change.

**CLITransport** — reads from stdin, writes to stdout. Used for local testing without a live platform.

Outgoing messages include delay jitter (configurable range, default 50–200ms) applied inside the Transport implementation, not in the Orchestrator.

### 5.2 Event Store

**SQLiteEventStore** — append-only writes to `messages` table. WAL mode enabled on first connection. All queries parameterised. Returns `StoredEvent` objects; callers never see raw SQL.

### 5.3 State Manager

**SQLiteStateManager** — owns all domain tables: `faction_state`, `promises`, `coalitions`, `inconsistencies`, `state_change_log`. Every write goes through `apply_patch()`, which validates the patch against the schema in `config/schemas/state_patch.json` and writes an audit entry to `state_change_log` before applying changes.

No other module writes to domain tables directly.

`get_full_state()` returns a serialised dict of all current entity states for use as Analyst input. Format matches what the Analyst prompt expects.

### 5.4 Extraction

**OpenAIStructuredExtractor** — calls `toolkit/llm_client.complete()` with `ModelTier.COMMODITY` (maps to GPT-4o mini by default). System prompt from `config/prompts/state_updater.txt`. The schema from `config/schemas/state_patch.json` is passed in the prompt for structured output enforcement. Validates response before returning.

**RuleBasedExtractor** — pattern-matching fallback for testing and offline operation. Returns empty patches for inputs it cannot parse rather than failing.

Two trigger paths distinguished by `trigger_type`:
- `'message'`: input is raw game messages, treated as observed facts
- `'intel_correction'`: input is operator INTEL note, treated as high-confidence override. Flagged in `state_change_log` with `trigger_type='intel_coaching'`.

### 5.5 Analyst

**LLMAnalyst** — a single implementation parameterised by provider and tier from `pipeline.yaml`. The primary instance uses the `anthropic` provider at `ModelTier.QUALITY` (Claude Sonnet); the secondary instance uses the `openai` provider at the same tier (GPT-4o). Both call `toolkit/llm_client.complete()` with full structured state as input. System prompt from `config/prompts/analyst.txt`. Schema from `config/schemas/intelligence.json`. Returns `AnalysisResult` with `provider_id` set from the config.

The two instances are independent — the Orchestrator wires them from the `analyst.primary` and `analyst.secondary` blocks in `pipeline.yaml`. Adding a third analyst (e.g., Google) is a config change: add a new block and register its `LLMConfig` in `llm_providers`.

**Divergence sub-module** — pure Python comparison, no API call. Reads both `AnalysisResult` objects and applies thresholds from `pipeline.yaml` to identify material disagreements. Returns `List[Divergence]`. Stored in `intelligence.divergence_flags`.

Because both analyst instances now go through `toolkit/llm_client`, adding or swapping providers requires no code changes — only a new `llm_providers` entry in `pipeline.yaml` and an `analyst` block pointing at it.

### 5.6 Persona

**FileBasedPersona** — loads `config/faction_prompt.txt` at startup. `build_round_context()` fills in the dynamic section (round number, rounds remaining, coaching context from `CoachingContext` struct) and returns it as a formatted string. Reloads the file if it has changed on disk, allowing prompt updates between rounds without restarting the service.

For a different application: replace `faction_prompt.txt` with a role-appropriate persona file. No code changes.

### 5.7 Context Assembler

**DefaultContextAssembler** — assembles `DecisionContext` from all inputs in the order defined by the context template (see Section 9.5). The only module that knows the shape of the Decision Engine's context window. If the context structure changes, this is the only implementation that changes.

INTEL coaching notes are deliberately excluded from the assembled context — they have already been applied to the database by the Extraction module and will appear in the Analyst output. This prevents double-counting corrections.

### 5.8 Generation

**LLMGenerator** — calls `toolkit/llm_client.complete()` with `DecisionContext.system_prompt` and `DecisionContext.user_prompt`, using the provider and tier specified in `pipeline.yaml` (default: Anthropic at `ModelTier.QUALITY`). If `review_gate_enabled`, requests JSON output `{"response": string, "reasoning": string}`. Otherwise requests plain text.

Swapping providers (e.g., to OpenAI if Anthropic is unavailable) is a config change in `pipeline.yaml` — point `generation.provider` at a different `llm_providers` entry.

### 5.9 Adversarial

**LLMAdversarialReader** — calls `toolkit/llm_client.complete()` with draft response text, using the provider and tier from `pipeline.yaml` (default: OpenAI at `ModelTier.QUALITY`). System prompt from `config/prompts/adversarial.txt`. Schema from `config/schemas/adversarial.json`. Returns `AdversarialResult`.

If `adversarial.enabled: false` in `pipeline.yaml`, the Orchestrator skips this module entirely and passes an empty `AdversarialResult` to the Review Gate. The Review Gate handles the empty case by displaying the draft alone.

This module is fully decoupled from the pipeline. It can be imported and used standalone in other applications:

```python
from modules.adversarial import LLMAdversarialReader
reader = LLMAdversarialReader(llm_config, tier, schema, prompt)
result = await reader.read(draft_text)
```

### 5.10 Coaching

**TaggedCoachingParser** — parses raw operator input against routing rules in `config/coaching_routes.yaml`. Returns a `CoachingEvent` or `Command`.

`coaching_routes.yaml` defines the tag-to-route mapping:

```yaml
tags:
  PRIORITY:
    route: coaching_queue
    coaching_type: PRIORITY
  CONSTRAINT:
    route: coaching_queue
    coaching_type: CONSTRAINT
  INTEL:
    route: state_updater
    coaching_type: INTEL
  TONE:
    route: coaching_queue
    coaching_type: TONE
  WATCH:
    route: coaching_queue
    coaching_type: WATCH
  default:
    route: coaching_queue
    coaching_type: FREE

commands:
  - /preview
  - /approve
  - /edit
  - /block
  - /status
  - /state
  - /ledger
  - /intel
  - /divergences
  - /edits
```

The tag list and routing rules are fully configurable. A different application with different operator input conventions changes this file without touching any module code.

### 5.11 Review Gate

**TelegramReviewGate** — sends draft response and adversarial analysis to the operator's coaching channel via `toolkit/telegram_client`. Waits for an operator command (`/approve`, `/edit:`, `/block`). Logs outcome to `review_gate_edits` table via State Manager before returning `ReviewDecision`.

If `review_gate.enabled: false` in `pipeline.yaml`, the Orchestrator substitutes an `AutoApproveReviewGate` which immediately returns `ReviewDecision(action='approved', final_text=draft.response_text)`. No human interaction required.

---

## 6. Orchestrator

The Orchestrator is the only component that knows the full pipeline topology. It is not a module — it is the composition layer that wires module interfaces to selected implementations and defines the control flow.

### 6.1 Startup

```python
# Load .env and pipeline.yaml
# Build LLMConfig objects from llm_providers section
# Instantiate CostAccountant from cost section (ledger_path, budgets)
# Instantiate each module, injecting LLMConfig + CostAccountant where needed
# Connect Transport (via toolkit/telegram_client)
# Start event loop
```

Implementations are registered in a simple registry keyed by class name. `pipeline.yaml` references class names; the registry maps them to importable classes. Adding a new implementation means adding it to the registry — no changes to the Orchestrator's control flow.

**Toolkit wiring at startup:**
1. Parse `llm_providers` into `toolkit.llm_client.LLMConfig` objects (one per provider).
2. Construct a `toolkit.cost_accountant.CostAccountant` with the `cost.ledger_path`.
3. Each LLM-consuming module receives its `LLMConfig` and a reference to the shared `CostAccountant`. Modules call `cost_accountant.complete()` instead of `llm_client.complete()` directly. The Orchestrator creates a `CostBudget` per round from `cost.per_round_budget_usd` and passes it through.

### 6.2 Event Loop

On each `InboundEvent` from Transport:

```
1. Event Store: append(event)
2. Coaching Parser: check if source == 'operator'
   a. If Command: dispatch to command handler
   b. If CoachingEvent with route='state_updater':
      - Extraction: extract(content, current_state, 'intel_correction')
      - State Manager: apply_patch(patch, PatchSource('intel_coaching', coaching_id))
   c. If CoachingEvent with route='coaching_queue':
      - Store in coaching table, mark unconsumed
3. If source != 'operator':
   - Extraction: extract(content, current_state, 'message') [debounced]
   - State Manager: apply_patch(patch, PatchSource('message', event_id))
4. Check if response needed:
   - If direct address to our faction → trigger response pipeline
   - If operator /preview command → trigger response pipeline
   - If scheduled response time → trigger response pipeline
```

On round boundary:

```
1. Analyst Primary: analyze(state_manager.get_full_state())
2. Analyst Secondary: analyze(state_manager.get_full_state())
3. Divergence: compare(primary_result, secondary_result)
4. Store intelligence record (both outputs + divergences)
5. Increment round counter
```

On response trigger:

```
1. Persona: get_base_prompt(), build_round_context(...)
2. Context Assembler: assemble(...)
3. Generation: generate(context)
4. Adversarial: read(draft) [if enabled]
5. Review Gate: submit(draft, adversarial_result)
6. If ReviewDecision.action != 'blocked':
   Transport: send(OutboundMessage(final_text, 'public'))
7. Store adversarial_read record
8. Mark coaching entries consumed
```

### 6.3 Failure Handling

Each module returns a typed result with a `success` flag. The Orchestrator checks `success` after each step:

| Step | On failure |
|---|---|
| Extraction (message) | Log, skip patch for this batch, continue |
| Extraction (INTEL) | Log, retain coaching entry, retry at round boundary |
| Analyst Primary | Log, skip round analysis, alert operator |
| Analyst Secondary | Log, proceed with primary only, flag in intelligence record |
| Generation | Retry once with exponential backoff, then alert operator |
| Adversarial | Log, pass empty result to Review Gate with warning flag |
| Review Gate | Log, hold response, alert operator |
| Transport send | Retry three times, then log and discard |
| Cost budget exceeded | Log, alert operator, skip the LLM call. Do not retry — the budget is a hard limit. |
| Rate limit (via Cost Accountant) | If `abort_on_rate_limit`, stop immediately and alert operator. Otherwise fall through to provider rotation if configured. |

No failure propagates across module boundaries as an exception. The Orchestrator handles each locally. Cost Accountant errors (`BudgetExceededError`, `RateLimitAbortError`, `SpendingCapAbortError`) are treated as module failures and follow the same pattern.

---

## 7. Coaching System

### 7.1 Philosophy

Coaching is an intervention, not a feed. Frequent low-signal coaching creates noise in the Context Assembler's input and makes agent behavior erratic. The goal is sparse, high-signal input that steers without replacing the agent's judgment.

The agent executes negotiation, promise tracking, and faction heuristics. Coaching addresses what only the operator can see: the behavior of human coaches behind opposing agents, judgment calls outside the faction prompt's scope, and systematic biases in the configured heuristics.

Coaching should decrease over the game as the faction prompt improves from review gate feedback. Heavy coaching in final rounds indicates a prompt that needs updating, not a coaching cadence that needs increasing.

### 7.2 Coaching Types and Routes

| Tag | Route | Effect | When to use |
|---|---|---|---|
| `PRIORITY:` | Coaching queue | Included in next Generation call | Pre-round, set compass |
| `CONSTRAINT:` | Coaching queue | Included in next Generation call | Hard boundary, trap detected |
| `INTEL:` | State Updater → State Manager | Updates DB, persists across rounds | Factual correction |
| `TONE:` | Coaching queue | Included in next Generation call | Behavioral adjustment |
| `WATCH:` | Coaching queue | Included in next Generation call | Attention direction |
| Untagged | Coaching queue | Included in next Generation call | Anything else |

INTEL notes route through the Extraction module so the correction is validated against the state patch schema before being applied. The State Manager's audit log records the origin as `'intel_coaching'` — corrections are traceable and reversible.

### 7.3 Cadence

Typical round:
- Pre-round: one `PRIORITY`, one `CONSTRAINT` if a trap is visible
- Mid-round: zero to one targeted correction
- Pre-response: approve, edit, or block via the review gate

More than two or three inputs per round signals that either the faction prompt needs tightening or the operator is playing the game rather than coaching an agent.

### 7.4 Review Gate Edit Log and Prompt Refinement

Every review gate decision is written to `review_gate_edits`. At each round boundary, `/edits` returns this log. Recurring edit patterns — consistently softening tone, consistently removing a specific type of commitment — should be written into `config/faction_prompt.txt` directly. The coaching note correcting for a recurring pattern should eventually become unnecessary.

Target state: by mid-game, the review gate is mostly approving without edit.

### 7.5 What Coaching Does Not Affect

- Messages already posted (append-only event log)
- Analyst outputs already written for the current round
- INTEL corrections do not backfill past intelligence records

INTEL notes update state forward from the point of correction. The next Analyst run will reflect them.

---

## 8. Persona Configuration

`config/faction_prompt.txt` is the faction identity file. Loaded by the Persona module at startup, reloaded on change without restart.

```
IDENTITY
[Who your faction is, what they project publicly, tone and register]

CORE OBJECTIVE
[Single primary win condition, stated precisely]

GOALS HIERARCHY
[Priority-ordered list: what to optimise for when objectives conflict]

COMMITMENTS YOU NEVER BREAK
[Hard rules functioning as credible commitment devices]

NEGOTIATION HEURISTICS
[How to evaluate offers, when to accept, when to reject without closing the door,
how to respond to aggression, bluff vs. commit rules, betrayal triggers]

BEHAVIORAL RULES
[Tone in public vs. private, how to handle direct questions about intentions,
how to surface reasoning vs. keep it internal]

CURRENT ROUND CONTEXT
[This section is filled in dynamically by the Persona module at runtime.
Do not edit this section — it is replaced before each Generation call.]
```

For a different application: replace this file with a role-appropriate persona. Customer service agent, contract negotiator, project manager. No code changes required.

---

## 9. Storage Schema

All domain tables are owned by the State Manager. No other module reads or writes them directly.

```sql
-- Owned by Event Store
CREATE TABLE messages (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id        TEXT NOT NULL UNIQUE,
    round_number    INTEGER NOT NULL,
    timestamp       TEXT NOT NULL,
    sender_faction  TEXT NOT NULL,
    channel         TEXT NOT NULL,
    recipient       TEXT,
    content         TEXT NOT NULL,
    telegram_msg_id INTEGER
);

-- Owned by State Manager
CREATE TABLE faction_state (
    faction_id              TEXT PRIMARY KEY,
    display_name            TEXT NOT NULL,
    stated_goals            TEXT,
    revealed_preferences    TEXT,
    credibility_score       REAL DEFAULT 1.0,
    behavioral_notes        TEXT,
    language_patterns       TEXT,
    last_updated            TEXT
);

CREATE TABLE promises (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    round_made      INTEGER NOT NULL,
    from_faction    TEXT NOT NULL,
    to_faction      TEXT NOT NULL,
    content         TEXT NOT NULL,
    status          TEXT DEFAULT 'pending',
    round_resolved  INTEGER,
    notes           TEXT
);

CREATE TABLE coalitions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    faction_a       TEXT NOT NULL,
    faction_b       TEXT NOT NULL,
    strength        REAL DEFAULT 0.5,
    confidence      REAL DEFAULT 0.5,
    basis           TEXT,
    last_updated    TEXT,
    UNIQUE(faction_a, faction_b)
);

CREATE TABLE inconsistencies (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    round_number            INTEGER NOT NULL,
    faction                 TEXT NOT NULL,
    description             TEXT NOT NULL,
    previous_statement      TEXT,
    contradicting_action    TEXT,
    leverage_value          TEXT,
    spent                   INTEGER DEFAULT 0
);

CREATE TABLE state_change_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp       TEXT NOT NULL,
    round_number    INTEGER NOT NULL,
    trigger_type    TEXT NOT NULL,
    trigger_ref     TEXT,
    table_affected  TEXT NOT NULL,
    change_summary  TEXT NOT NULL
);

-- Owned by intelligence pipeline (written by Orchestrator via State Manager)
CREATE TABLE intelligence (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    round_number            INTEGER NOT NULL UNIQUE,
    timestamp               TEXT NOT NULL,
    primary_output          TEXT,
    secondary_output        TEXT,
    divergence_flags        TEXT,
    threat_model            TEXT,
    leverage_inventory      TEXT,
    behavioral_anomalies    TEXT,
    blind_spot_flags        TEXT,
    recommended_priorities  TEXT,
    spend_schedule          TEXT
);

CREATE TABLE adversarial_reads (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    round_number            INTEGER NOT NULL,
    timestamp               TEXT NOT NULL,
    draft_response          TEXT NOT NULL,
    analysis                TEXT,
    posted                  INTEGER DEFAULT 0,
    posted_text             TEXT
);

CREATE TABLE coaching (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp       TEXT NOT NULL,
    coaching_type   TEXT NOT NULL,
    content         TEXT NOT NULL,
    route           TEXT NOT NULL,
    consumed        INTEGER DEFAULT 0,
    consumed_at     TEXT,
    round_number    INTEGER
);

CREATE TABLE review_gate_edits (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    round_number    INTEGER NOT NULL,
    timestamp       TEXT NOT NULL,
    adversarial_read_id INTEGER,
    original_draft  TEXT NOT NULL,
    edited_text     TEXT,
    action          TEXT NOT NULL,
    edit_notes      TEXT
);

CREATE TABLE game_state (
    key     TEXT PRIMARY KEY,
    value   TEXT
);

INSERT INTO game_state VALUES ('current_round', '1');
INSERT INTO game_state VALUES ('total_rounds', 'unknown');
INSERT INTO game_state VALUES ('game_status', 'waiting');
```

---

## 10. Prompt Files

All prompts are plain text files in `config/prompts/`. The module loads the file; no prompt content is hardcoded in any module.

### 10.1 State Updater (`config/prompts/state_updater.txt`)

```
You are a structured data extraction system for a diplomatic simulation game.
Your job is to parse input and return a JSON object describing changes
to the game's structured state.

Input will be either:
- New game messages (automatic pipeline trigger)
- An operator intelligence correction marked [OPERATOR INTEL]
  (human-sourced, treat as high-confidence factual correction
  overriding prior assessments)

Output ONLY valid JSON conforming to the provided schema.
No explanation, no preamble, no markdown fences.
Do not invent updates. Only extract what is evidenced in the input.
Empty arrays for fields with no updates.
```

### 10.2 Analyst (`config/prompts/analyst.txt`)

```
You are a neutral strategic intelligence analyst for a diplomatic simulation game.
You have no faction allegiance. Produce an accurate, unbiased assessment
of the current game state.

Be specific. Vague assessments have no value. If uncertain, say so explicitly
within the relevant field — do not omit uncertain items.
Flag assumptions that could be wrong.
The quality of this analysis determines the quality of decisions made from it.

Output ONLY valid JSON conforming to the provided schema.
No explanation, no preamble, no markdown fences.
```

### 10.3 Adversarial (`config/prompts/adversarial.txt`)

```
You are an opposing faction in a diplomatic simulation game.
You have just received a message from another faction.
Analyse what this message reveals, commits to, and where it is exploitable.

Reason only from what the message text conveys.
You have no knowledge of the sender's true intentions.
Be specific and adversarial. Vague readings are useless.

Output ONLY valid JSON conforming to the provided schema.
No explanation, no preamble, no markdown fences.
```

### 10.4 Decision Engine Context Template

Assembled by the Context Assembler from the following blocks, in order:

```
[Persona.get_base_prompt()]

[Persona.build_round_context()]

--- INTELLIGENCE SUMMARY ---
[Primary intelligence report, pretty-printed]

--- ANALYST DIVERGENCES ---
[divergence_flags if any | 'No divergences. Both analysts agree.']

--- RECENT TRANSCRIPT (last {n} messages) ---
[Round N | Faction | channel — content]

--- COACHING FROM OPERATOR ---
[Unconsumed PRIORITY / CONSTRAINT / TONE / WATCH / FREE entries]
[INTEL notes excluded — already applied to database]
['No additional coaching this round.' if queue empty]

--- TASK ---
Generate your faction's next message for the diplomatic channel.
Treat analyst divergences as genuinely uncertain.
{JSON output instruction if review gate enabled | plain text instruction if not}
```

---

## 11. Directory Structure

```
/opt/diplomat/
├── config/
│   ├── .env                          # credentials only (API keys for llm_providers)
│   ├── pipeline.yaml                 # all wiring, llm_providers, cost budgets
│   ├── faction_prompt.txt            # persona (swap for different faction/app)
│   ├── coaching_routes.yaml          # tag routing rules
│   ├── prompts/
│   │   ├── state_updater.txt
│   │   ├── analyst.txt
│   │   └── adversarial.txt
│   └── schemas/
│       ├── state_patch.json          # Extraction output schema
│       ├── intelligence.json         # Analyst output schema
│       └── adversarial.json          # Adversarial output schema
├── src/
│   ├── main.py                       # entry point
│   ├── orchestrator.py               # pipeline topology, event loop, cost accountant
│   ├── registry.py                   # implementation class registry
│   └── modules/
│       ├── transport/
│       │   ├── __init__.py           # Transport interface + dataclasses
│       │   ├── telegram_bot.py       # wraps toolkit/telegram_client
│       │   ├── telethon_user.py      # wraps Telethon (only if bot-to-bot unavailable)
│       │   └── cli.py
│       ├── event_store/
│       │   ├── __init__.py
│       │   └── sqlite.py
│       ├── state_manager/
│       │   ├── __init__.py
│       │   └── sqlite.py
│       ├── extraction/
│       │   ├── __init__.py
│       │   ├── llm_structured.py     # uses toolkit/llm_client (COMMODITY tier)
│       │   └── rule_based.py
│       ├── analyst/
│       │   ├── __init__.py
│       │   ├── llm.py                # uses toolkit/llm_client (configurable provider)
│       │   └── divergence.py
│       ├── persona/
│       │   ├── __init__.py
│       │   └── file_based.py
│       ├── context_assembler/
│       │   ├── __init__.py
│       │   └── default.py
│       ├── generation/
│       │   ├── __init__.py
│       │   └── llm.py                # uses toolkit/llm_client (configurable provider)
│       ├── adversarial/
│       │   ├── __init__.py
│       │   └── llm.py                # uses toolkit/llm_client (configurable provider)
│       ├── coaching/
│       │   ├── __init__.py
│       │   └── tagged.py
│       └── review_gate/
│           ├── __init__.py
│           ├── telegram.py           # wraps toolkit/telegram_client
│           └── auto_approve.py
├── data/
│   ├── game.db
│   └── cost_ledger.jsonl             # toolkit/cost_accountant append-only ledger
├── logs/
│   └── diplomat.log
└── systemd/
    └── diplomat.service
```

---

## 12. Deployment

### 12.1 Initial Setup

```bash
sudo apt update && sudo apt install -y python3-pip python3-venv sqlite3

sudo mkdir -p /opt/diplomat/{config/prompts,config/schemas,src/modules,data,logs,systemd}
sudo chown -R $USER:$USER /opt/diplomat

python3 -m venv /opt/diplomat/venv
source /opt/diplomat/venv/bin/activate

# Verify current package versions before installing
# Install toolkit as editable dependency (provides llm_client, telegram_client, cost_accountant)
pip install -e /path/to/toolkit

pip install \
  telethon \
  aiofiles \
  python-dotenv \
  pyyaml

# Note: anthropic, openai SDKs are transitive dependencies of toolkit/llm_client.
# python-telegram-bot is NOT needed — Diplomat uses toolkit/telegram_client.
# telethon is only needed if using TelethonUserTransport.

cd /opt/diplomat
python3 src/main.py --init-db    # creates tables, seeds game_state

chmod 600 /opt/diplomat/config/.env
```

### 12.2 SQLite WAL Mode

Applied by SQLiteEventStore and SQLiteStateManager on first connection:

```python
conn.execute("PRAGMA journal_mode=WAL;")
conn.execute("PRAGMA synchronous=NORMAL;")
conn.execute("PRAGMA cache_size=10000;")
```

### 12.3 systemd Service

```ini
[Unit]
Description=AI Diplomat Game Agent
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=diplomat
WorkingDirectory=/opt/diplomat
EnvironmentFile=/opt/diplomat/config/.env
ExecStart=/opt/diplomat/venv/bin/python3 src/main.py
Restart=on-failure
RestartSec=10
StandardOutput=append:/opt/diplomat/logs/diplomat.log
StandardError=append:/opt/diplomat/logs/diplomat.log
WatchdogSec=120

[Install]
WantedBy=multi-user.target
```

### 12.4 Log Rotation

```
/opt/diplomat/logs/diplomat.log {
    daily
    rotate 7
    compress
    missingok
    notifempty
    copytruncate
}
```

---

## 13. Operational Notes

### Startup sequence

1. Load `.env` and `pipeline.yaml`
2. Build `toolkit.llm_client.LLMConfig` objects from `llm_providers` section
3. Construct `toolkit.cost_accountant.CostAccountant` from `cost` section
4. Instantiate module implementations from registry, injecting `LLMConfig` + `CostAccountant`
5. Initialise SQLite (WAL mode, schema if new)
6. Load prompt files (fail fast if missing)
7. Validate all API credentials with a lightweight test call (via `toolkit/llm_client`)
8. Start Transport listener (via `toolkit/telegram_client`)
9. Start Orchestrator event loop
10. Log: `DIPLOMAT ONLINE — Round {n} — {faction_id} — session budget $X.XX`

### Per-round API call budget

| Call | Module | Toolkit Tier | Default Provider | Frequency |
|---|---|---|---|---|
| Extraction (messages) | Extraction | COMMODITY | OpenAI (GPT-4o mini) | Per message batch |
| Extraction (INTEL) | Extraction | COMMODITY | OpenAI (GPT-4o mini) | Per INTEL coaching note |
| Analyst Primary | Analyst | QUALITY | Anthropic (Claude Sonnet) | Per round boundary |
| Analyst Secondary | Analyst | QUALITY | OpenAI (GPT-4o) | Per round boundary |
| Generation | Generation | QUALITY | Anthropic (Claude Sonnet) | Per response |
| Adversarial | Adversarial | QUALITY | OpenAI (GPT-4o) | Per response (if enabled) |

All calls go through `toolkit/cost_accountant.complete()`, which enforces `cost.per_round_budget_usd` and `cost.per_call_max_usd` from `pipeline.yaml`. The cost ledger at `data/cost_ledger.jsonl` provides a per-call spending record. Use `cost_accountant.report()` for post-game cost analysis.

### Between-round operator workflow

1. `/edits` — review edit log from completed round
2. `/divergences` — review analyst disagreements
3. Identify recurring edit patterns → update `config/faction_prompt.txt`
4. Set `PRIORITY:` and `CONSTRAINT:` coaching for next round
5. `/intel` — review new intelligence report before round opens

### Monitoring

```bash
# Live log
journalctl -u diplomat -f

# Game state
sqlite3 /opt/diplomat/data/game.db "SELECT * FROM game_state;"

# Promise ledger
sqlite3 /opt/diplomat/data/game.db \
  "SELECT from_faction, to_faction, content, status FROM promises ORDER BY round_made;"

# INTEL corrections applied
sqlite3 /opt/diplomat/data/game.db \
  "SELECT timestamp, table_affected, change_summary FROM state_change_log
   WHERE trigger_type='intel_coaching';"

# Edit log this round
sqlite3 /opt/diplomat/data/game.db \
  "SELECT action, original_draft, edited_text FROM review_gate_edits
   WHERE round_number=(SELECT value FROM game_state WHERE key='current_round');"

# Cost report (via Python — reads the toolkit cost ledger)
python3 -c "from toolkit.cost_accountant import CostAccountant; from pathlib import Path; \
  a = CostAccountant(Path('data/cost_ledger.jsonl')); r = a.report(); \
  print(f'Total: ${r.total_spend_usd:.2f}'); \
  [print(f'  {k}: ${v:.2f}') for k,v in r.by_operation.items()]"
```

### Pre-game checklist

- [ ] Bot-to-bot messaging resolved; Transport implementation selected in `pipeline.yaml`
- [ ] All faction usernames mapped in `pipeline.yaml`
- [ ] API credentials valid and tested (startup does this automatically via `toolkit/llm_client`)
- [ ] `llm_providers` section configured with correct model strings (verify against provider docs)
- [ ] `cost` section configured: per-round and per-session budgets set
- [ ] `config/faction_prompt.txt` written and reviewed
- [ ] `total_rounds` set in `pipeline.yaml` if known
- [ ] `round.mode` confirmed with game moderator
- [ ] `review_gate.enabled: true` for first game
- [ ] systemd service running: `systemctl status diplomat`
- [ ] Coaching channel confirmed: send `/status`, verify response
- [ ] Test INTEL routing: send `INTEL: test`, verify `state_change_log` entry
- [ ] Test Adversarial: send `/preview`, verify dual output reaches coaching channel
- [ ] Verify cost ledger is writing: check `data/cost_ledger.jsonl` after test cycle
- [ ] Run full pipeline cycle before game start

---

## 14. Open Questions

1. **Bot vs. user accounts** — Determines Transport implementation. Resolve with game moderator before anything else.
2. **Round structure** — Time-based or signal-based. Fixed or variable duration. Sets `round.mode` in `pipeline.yaml`.
3. **Total round count** — Known at start or not. Sets `total_rounds`. Affects spend schedule logic in Analyst output.
4. **Win condition mechanics** — How winner is determined. Affects late-game Analyst framing; may require prompt update.
5. **Response rate** — Posts at will or capped per round. Affects response trigger logic in Orchestrator.
6. **Moderator role** — Human referee or fully agent-driven.
7. **Provider API verification** — Model names and structured output APIs to be confirmed against current `toolkit/llm_client` provider implementations before use. Toolkit already supports Anthropic, OpenAI, Google, and OpenRouter.
8. **Structured output enforcement** — The Extraction module needs JSON schema enforcement on the LLM call. Toolkit's `llm_client.complete()` currently returns plain text; structured output (OpenAI's `response_format` / Anthropic's tool-use schema) would need to be handled in the module or added to Toolkit.
