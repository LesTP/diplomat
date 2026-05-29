# State Reconciliation — Design

## Problem

Per-message extraction produces fragmented, inconsistent state:

1. **Duplicates:** Same commitment tracked multiple times with different IDs
   because wording varies between rounds ("commit $2M upfront" vs "activate
   $2M emergency fund" → different IDs → no dedup match).

2. **No fulfillment tracking:** Promises stay "pending" forever because each
   extraction call only sees one message — it can't compare current actions
   against prior commitments.

3. **No inconsistency detection:** Position shifts (20M gallons → 15M gallons)
   are never flagged because each extraction is stateless — it doesn't compare
   the new message against the faction's prior statements.

4. **Under-extraction:** Conservative per-message extraction misses proposals
   that don't use explicit commitment language.

## Root Cause

Extraction runs **per-message** with the current state as context, but:
- It generates new IDs from content rather than matching against existing ones
- It can't do semantic matching ("is this the same commitment rephrased?")
- It sees one message at a time, so it can't detect cross-message patterns
  like fulfillment or contradiction

## Solution: Post-Round State Reconciliation

Add a reconciliation step that runs **once per round boundary**, after all
per-message extractions have completed. It takes the full picture — all
tracked promises/coalitions/inconsistencies plus the round's transcript —
and produces a reconciled state patch.

### What It Does

1. **Merge duplicates:** Identify promises with the same from_faction,
   to_faction, and semantically similar content. Keep the earliest ID,
   merge status (prefer non-pending over pending).

2. **Detect fulfillments:** Compare each pending promise's content against
   actions described in the transcript. If a faction followed through on
   a commitment, update status to "kept" with a resolution note.

3. **Detect broken promises:** If a faction's current position contradicts
   a prior promise, update status to "broken" and create an inconsistency
   entry.

4. **Flag inconsistencies:** Compare each faction's current-round statements
   against their prior-round positions. Flag significant shifts (changed
   numbers, reversed positions, contradicted commitments).

5. **Catch missed proposals:** Review the transcript for concrete proposals
   that weren't caught by per-message extraction.

### Where It Runs

In the Orchestrator's `handle_round_boundary()`, after the dual-analyst
calls complete and before the round number increments. The reconciliation
sees the full round's events and the accumulated state.

```
Per-message extraction (throughout the round)
    ↓
Round boundary signal
    ↓
State reconciliation (new) ← full transcript + full state
    ↓
Dual analyst calls
    ↓
Round increment
```

### Interface

```python
class StateReconciler:
    def __init__(self, llm_client, llm_config, tier="commodity"):
        ...

    async def reconcile(
        self,
        current_state: dict,    # full state from state_manager
        recent_events: list,    # this round's transcript
        round_number: int,
    ) -> ReconciliationResult:
        ...

@dataclass
class ReconciliationResult:
    success: bool
    merged_promises: list[dict]      # deduped promise list
    updated_statuses: list[dict]     # promise_id → new status + resolution
    new_inconsistencies: list[dict]  # newly detected inconsistencies
    missed_proposals: list[dict]     # proposals not caught by extraction
    merge_log: list[str]             # human-readable log of what was merged
    error: str | None
```

### Schema for the LLM Call

The reconciler uses a single `structured_call` with this schema:

```json
{
  "type": "object",
  "required": ["merged_promises", "status_updates", "new_inconsistencies",
               "missed_proposals", "merge_log"],
  "properties": {
    "merged_promises": {
      "description": "Groups of promise IDs that refer to the same commitment",
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "keep_id": "string (the canonical promise ID to keep)",
          "remove_ids": "string[] (duplicate IDs to remove)",
          "reason": "string (why these are the same)"
        }
      }
    },
    "status_updates": {
      "description": "Promises whose status should change",
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "promise_id": "string",
          "new_status": "pending | kept | broken | void",
          "resolution": "string (evidence for the change)"
        }
      }
    },
    "new_inconsistencies": {
      "description": "Contradictions between current statements and prior positions",
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "faction_id": "string",
          "description": "string",
          "leverage_value": "number 0-1"
        }
      }
    },
    "missed_proposals": {
      "description": "Concrete proposals from the transcript not in current state",
      "type": "array",
      "items": {
        "type": "object (same shape as promise)"
      }
    },
    "merge_log": {
      "description": "Human-readable summary of reconciliation actions",
      "type": "array",
      "items": "string"
    }
  }
}
```

### Cost

One LLM call per agent per round boundary. With 3 agents and 4 rounds,
that's 12 additional calls at commodity tier — ~$0.03-0.05 with gpt-4.1-mini.

### What This Does NOT Do

- Does not replace per-message extraction — that still runs for real-time
  state updates during the round
- Does not modify the extraction prompt — the reconciler is a separate
  cleanup pass
- Does not change the state patch schema — it produces standard promises,
  coalitions, and inconsistencies
- Does not require changes to the analyst or generation modules — they
  read from state_manager which will have cleaner data after reconciliation

### Empirical Justification

From 7 self-play runs:
- Run 4 (water rights): 4 duplicates of Gamma's $2M commitment, 0/21
  fulfillments detected, 0 inconsistencies despite Beta's 20M→15M shift
- Run 5 (dirty bargaining): Alpha's Environment concession duplicated
  with different to_factions, Beta's 4-round tariff shift undetected
- Run 6 (coalition): 1 promise tracked out of 12 concrete proposals,
  coalition strength=None slipped through
