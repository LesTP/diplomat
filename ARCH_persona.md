# ARCH: Persona

## Purpose
Faction identity configuration. Loads the faction persona from `config/faction_prompt.txt` at startup and provides it in two parts: a stable base prompt (identity, goals, heuristics, behavioral rules) and a dynamic round context section (round number, rounds remaining, accumulated coaching context). Reloads the file on change without restart, allowing prompt updates between rounds.

## Public API

### get_base_prompt
- **Signature:** `async def get_base_prompt(self) -> str`
- **Parameters:** none
- **Returns:** str — the full faction persona text (everything except the CURRENT ROUND CONTEXT section). Reloads from disk if the file has changed since last read.
- **Errors:** FileNotFoundError if faction_prompt.txt is missing

### build_round_context
- **Signature:** `async def build_round_context(self, round_number: int, rounds_remaining: int | None, coaching_context: CoachingContext) -> str`
- **Parameters:**
  - round_number: int — current round
  - rounds_remaining: int | None — None if total rounds unknown
  - coaching_context: CoachingContext — accumulated coaching from the coaching table
- **Returns:** str — formatted round context section
- **Errors:** none

## Types

```python
@dataclass
class CoachingContext:
    priorities: list[str]
    constraints: list[str]
    watch_items: list[str]
    tone_notes: list[str]
```

## Inputs
- `config/faction_prompt.txt` — the persona definition file
- Round metadata from Orchestrator
- CoachingContext assembled from unconsumed coaching table entries

## Outputs
- Base prompt string (consumed by Context Assembler)
- Round context string (consumed by Context Assembler)

## State
- Cached file content and last-modified timestamp for hot-reload detection
- No persistent state

## Usage Example

```python
from modules.persona import FileBasedPersona, CoachingContext

persona = FileBasedPersona(path="config/faction_prompt.txt")

base = await persona.get_base_prompt()

context = await persona.build_round_context(
    round_number=4,
    rounds_remaining=6,
    coaching_context=CoachingContext(
        priorities=["Secure Beta alliance"],
        constraints=["Do not promise territory"],
        watch_items=["Delta's credibility dropping"],
        tone_notes=["More assertive this round"],
    ),
)
```
