# ARCH: Review Gate

## Purpose
Human approval workflow. Sends the draft response (and on-demand deeper context) to the operator's coaching channel via the pipeline's Transport abstraction. Waits for an operator command (`/approve`, `/edit:`, `/block`). Logs the outcome to the review_gate_edits table via State Manager before returning. When disabled, substitutes an auto-approve path.

The review gate is a passive handler — it does not poll for updates itself. The pipeline's `dispatch_operator()` passes each incoming operator command through `handle_command()` first; only commands unrecognized by the gate fall through to the normal operator dispatcher.

## Public API

### submit
- **Signature:** `async def submit(self, draft: GenerationResult, adversarial: Any, round_number: int) -> ReviewDecision`
- **Parameters:**
  - draft: GenerationResult — the generated response with optional reasoning
  - adversarial: Any — adversarial analysis result (may be None/empty)
  - round_number: int — current round for logging and message headers
- **Returns:** ReviewDecision
- **Errors:** raises `RuntimeError` if called while a review is already pending (D-41). On transport send failure, aborts with `ReviewDecision(action="blocked", edit_notes="transport error: ...")` and re-raises (D-42).
- **Timeout:** if `timeout_seconds` is set, blocks for at most that many seconds, then returns `ReviewDecision(action="blocked", edit_notes="Review timed out after N seconds")`.

### handle_command
- **Signature:** `async def handle_command(self, command: str) -> bool`
- **Returns:** `True` if the command was consumed by the gate (review still pending or just resolved), `False` if no review is pending or the command is not a review command.
- **Review commands:** `/approve`, `/edit: <text>`, `/edit <text>` (legacy), `/block` — resolve the pending review.
- **Lazy-fetch commands:** `/reasoning`, `/adversarial` — send the corresponding section through transport; review stays pending. Can be repeated.
- **Everything else** (e.g. `/state`, `/intel`) — returns `False`; pipeline routes normally.

## Types

```python
@dataclass
class ReviewDecision:
    action: str                   # 'approved' | 'edited' | 'blocked'
    final_text: str | None        # None if blocked
    edit_notes: str | None        # operator's edit text if action='edited'
```

## Implementations

**OperatorReviewGate** — sends review messages through the pipeline's `Transport` instance (`channel="coaching"`). The draft section is pushed eagerly; reasoning and adversarial sections are lazy-fetched on operator request (D-40). Long messages are split into chunks capped at `max_message_chars` (default 4000, below TG's 4096 limit) with `[continued ...]` markers (D-43 rename from TelegramReviewGate).

Constructor:
```python
OperatorReviewGate(
    transport,               # Transport — pipeline's already-built transport module
    *,
    max_message_chars=4000,
    state_manager=None,
    timeout_seconds=None,
)
```

Message flow on `submit()`:
1. Formats and chunks the draft with header `"Review Gate - Round N\n\nDraft:\n..."`.
2. Appends `"\n\nCommands: /approve | /edit: <text> | /block | /reasoning | /adversarial"` to the last draft chunk.
3. Sends each chunk via `transport.send(OutboundMessage(content=..., channel="coaching"))`.
4. Awaits operator command(s) via the `handle_command()` callback loop.
5. Logs decision via `state_manager.log_review_decision` if state_manager is injected.

**AutoApproveReviewGate** — used when `review_gate.enabled: false`. Immediately returns `ReviewDecision(action='approved', final_text=draft.response_text)`. No human interaction.

## Chunking Contract

`chunk_text(text, max_chars)` in `src/modules/review_gate/chunking.py`:
- If `len(text) <= max_chars`, returns `[text]`.
- Otherwise packs whole paragraphs (`\n\n` split), falling back to line split, then character split.
- Every chunk after the first is prefixed with `CONTINUATION_PREFIX = "[continued ...]\n\n"`, which is reserved from the `max_chars` budget.

## Lazy Fetch Contract

- Only the draft is sent eagerly on `submit()`.
- `/reasoning` → sends `"Reasoning:\n{draft.reasoning}"` or `"Reasoning:\n[not available]"` if unset.
- `/adversarial` → sends `"Adversarial:\n{formatted}"` (handles dict, str, None, success=False shapes).
- Both commands return `True` (consumed) and keep the review pending. Idempotent — can be re-requested.

## Command Pass-Through Contract

`Pipeline.dispatch_operator()` checks `review_gate.handle_command(content)` first on every slash command. If `handle_command` returns `True`, the command is consumed. If `False` (not a review command, or no pending review), the pipeline routes the command normally. The review gate never polls `get_next_update()` directly.

## Transport Dependency

`OperatorReviewGate` takes a `transport` instance (the pipeline's already-built Transport module) and calls `transport.send(OutboundMessage(content=..., channel="coaching"))`. There is no direct `toolkit/telegram_client` import in the review gate. The orchestrator factory (`_build_module`) passes the already-built transport module when constructing `OperatorReviewGate` (requires `transport` to be built before `review_gate` in `REQUIRED_MODULES` — already the case).

## Inputs
- GenerationResult from Generation module
- Adversarial result from Adversarial module (may be None/success=False if skipped)
- Round number from Pipeline

## Outputs
- ReviewDecision — consumed by Pipeline to decide whether to post via Transport
- Side effect: writes to review_gate_edits table via State Manager (when injected)

## State
- `_pending: (draft, adversarial, round_number, Future) | None` — in-memory single-slot pending state (D-41: concurrent submit raises RuntimeError)
- No persistent state beyond the review_gate_edits table (owned by State Manager)

## Usage Example

```python
from modules.review_gate import OperatorReviewGate, AutoApproveReviewGate

# With human review (wired by orchestrator factory)
gate = OperatorReviewGate(transport, max_message_chars=4000)

# In pipeline.dispatch_operator():
if content.startswith("/"):
    consumed = await gate.handle_command(content.strip())
    if consumed:
        return

# In response pipeline:
decision = await gate.submit(generation_result, adversarial_result, round_number=4)
if decision.action != 'blocked':
    await transport.send(OutboundMessage(decision.final_text, 'public', None))

# Without human review
gate = AutoApproveReviewGate()
decision = await gate.submit(generation_result, adversarial_result, round_number=4)
# decision.action == 'approved', decision.final_text == draft.response_text
```
