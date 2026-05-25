# ARCH: Review Gate

## Purpose
Human approval workflow. Sends the draft response and adversarial analysis to the operator's coaching channel via toolkit/telegram_client. Waits for an operator command (/approve, /edit:, /block). Logs the outcome to the review_gate_edits table via State Manager before returning. When disabled, substitutes an auto-approve path.

## Public API

### submit
- **Signature:** `async def submit(self, draft: GenerationResult, adversarial: AdversarialResult, round_number: int) -> ReviewDecision`
- **Parameters:**
  - draft: GenerationResult — the generated response with optional reasoning
  - adversarial: AdversarialResult — the adversarial analysis (may be empty if adversarial disabled)
  - round_number: int — current round for logging
- **Returns:** ReviewDecision
- **Errors:** none — blocks until operator responds or returns a blocked decision on configured timeout

## Types

```python
@dataclass
class ReviewDecision:
    action: str                   # 'approved' | 'edited' | 'blocked'
    final_text: str | None        # None if blocked
    edit_notes: str | None        # operator's edit notes if action='edited'
```

## Implementations

**TelegramReviewGate** — sends a formatted message to the coaching channel containing:
1. The draft response text
2. The reasoning (if review gate JSON mode)
3. The adversarial analysis (if available, or a warning that it was skipped/failed)
4. Action buttons / command instructions (/approve, /edit: ..., /block)

Waits for the next operator command on the coaching channel. Logs the decision to the `review_gate_edits` table via State Manager.

**AutoApproveReviewGate** — used when `review_gate.enabled: false`. Immediately returns `ReviewDecision(action='approved', final_text=draft.response_text)`. No human interaction.

## Timeout Behavior
`TelegramReviewGate` accepts optional `timeout_seconds`. When unset, `submit()` waits indefinitely for an operator command. When set, timeout returns `ReviewDecision(action='blocked', final_text=None, edit_notes='Review timed out after ... seconds')` and logs the blocked decision through the configured State Manager hook when available.

## Inputs
- GenerationResult from Generation module
- AdversarialResult from Adversarial module (may have success=False if module was skipped/failed)
- Round number from Orchestrator

## Outputs
- ReviewDecision — consumed by Orchestrator to decide whether to post via Transport
- Side effect: writes to review_gate_edits table via State Manager

## State
- Pending review state (in-memory): tracks whether a review is in progress
- No persistent state beyond the review_gate_edits table (owned by State Manager)

## Usage Example

```python
from modules.review_gate import TelegramReviewGate, AutoApproveReviewGate

# With human review
gate = TelegramReviewGate(
    telegram_client=tg_client,
    coaching_channel_id="-100yyy",
    state_manager=sm,
)

decision = await gate.submit(generation_result, adversarial_result, round_number=4)
if decision.action != 'blocked':
    await transport.send(OutboundMessage(decision.final_text, 'public', None))

# Without human review
gate = AutoApproveReviewGate()
decision = await gate.submit(generation_result, adversarial_result, round_number=4)
# decision.action == 'approved', decision.final_text == draft.response_text
```
