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

**OperatorReviewGate** — sends review messages through the pipeline's `Transport` instance (`channel="coaching"`). The draft section is pushed eagerly; reasoning and adversarial sections are lazy-fetched on operator request (D-40). Oversize messages are sent once and auto-chunked by the shared toolkit transport, so the review gate no longer owns message splitting. `max_message_chars` remains only as a config-compatibility knob (D-43 rename from TelegramReviewGate).

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
1. Composes a single message: `"Review Gate - Round N\n\nDraft:\n{draft_text}\n\nCommands: /approve | ..."`.
2. Sends it via one `transport.send(OutboundMessage(content=..., channel="coaching"))` call — auto-chunking at 4096 chars is handled transparently by the toolkit transport layer (D-46).
3. Awaits operator command(s) via the `handle_command()` callback loop.
4. Logs decision via `state_manager.log_review_decision` if state_manager is injected.

**AutoApproveReviewGate** — used when `review_gate.enabled: false`. Immediately returns `ReviewDecision(action='approved', final_text=draft.response_text)`. No human interaction.

## Lazy Fetch Contract

- Only the draft is sent eagerly on `submit()`.
- `/reasoning` → sends `"Reasoning:\n{draft.reasoning}"` or `"Reasoning:\n[not available]"` if unset.
- `/adversarial` → sends `"Adversarial:\n{formatted}"` (handles dict, str, None, success=False shapes).
- Both commands return `True` (consumed) and keep the review pending. Idempotent — can be re-requested.

## Command Pass-Through Contract

`Pipeline.dispatch_operator()` checks `review_gate.handle_command(content)` first on every slash command. If `handle_command` returns `True`, the command is consumed. If `False` (not a review command, or no pending review), the pipeline routes the command normally. The review gate never polls `get_next_update()` directly.

## Flow Wiring Requirement (consumers other than EventDrivenFlow)

`OperatorReviewGate` is a passive handler — it only resolves its pending future when *something else* calls `handle_command`. `EventDrivenFlow.process_event` provides that routing automatically by consuming `Transport.listen()` and dispatching `sender_faction == "operator"` events through `Pipeline.dispatch_operator`.

**Any flow that does not run an inbound listen-loop (e.g. `RoundSteppedFlow`) MUST provide its own bridge** that funnels operator messages into `pipeline.dispatch_operator`. Without this, the gate hangs forever at the first review. The reference implementation is `CoachedGameEnvironment._listen_for_operator` (`tests/self_play/coached_game.py`) — it reuses the wrapped `TelegramBotTransport.listen()` iterator to pick up operator-tagged events and forwards them to the coached agent's pipeline. The bridge task is started in `setup()` and cancelled in `teardown()`. See D-44.

## Transport Dependency

`OperatorReviewGate` takes a `transport` instance (the pipeline's already-built Transport module) and calls `transport.send(OutboundMessage(content=..., channel="coaching"))`. There is no direct `toolkit/telegram_client` import in the review gate. Oversize review text is now auto-chunked by the shared toolkit transport, so the gate only composes the full coaching message once. The orchestrator factory (`_build_module`) passes the already-built transport module when constructing `OperatorReviewGate` (requires `transport` to be built before `review_gate` in `REQUIRED_MODULES` — already the case).

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
