"""Post-round state reconciliation.

Runs once per round boundary to merge duplicate promises, detect
fulfillments and broken commitments, flag inconsistencies, and catch
missed proposals. Uses a single structured_call with the full round
transcript and accumulated state.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any

from toolkit.structured_llm import structured_call


@dataclass
class ReconciliationResult:
    success: bool
    merged_promises: list[dict[str, Any]] = field(default_factory=list)
    updated_statuses: list[dict[str, Any]] = field(default_factory=list)
    new_inconsistencies: list[dict[str, Any]] = field(default_factory=list)
    missed_proposals: list[dict[str, Any]] = field(default_factory=list)
    merge_log: list[str] = field(default_factory=list)
    error: str | None = None


RECONCILIATION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "merged_promises",
        "status_updates",
        "new_inconsistencies",
        "missed_proposals",
        "merge_log",
    ],
    "properties": {
        "merged_promises": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["keep_id", "remove_ids", "reason"],
                "properties": {
                    "keep_id": {"type": "string"},
                    "remove_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "reason": {"type": "string"},
                },
            },
        },
        "status_updates": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["promise_id", "new_status", "resolution"],
                "properties": {
                    "promise_id": {"type": "string"},
                    "new_status": {"enum": ["pending", "kept", "broken", "void"]},
                    "resolution": {"type": "string"},
                },
            },
        },
        "new_inconsistencies": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["faction_id", "description"],
                "properties": {
                    "faction_id": {"type": "string"},
                    "description": {"type": "string"},
                    "leverage_value": {"type": "number", "minimum": 0, "maximum": 1},
                },
            },
        },
        "missed_proposals": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["promise_id", "from_faction", "to_faction", "content"],
                "properties": {
                    "promise_id": {"type": "string"},
                    "from_faction": {"type": "string"},
                    "to_faction": {"type": "string"},
                    "content": {"type": "string"},
                    "status": {"enum": ["pending", "kept", "broken", "void"]},
                },
            },
        },
        "merge_log": {
            "type": "array",
            "items": {"type": "string"},
        },
    },
}

RECONCILIATION_PROMPT = """\
You are a negotiation state reconciler. Given the current tracked state
(promises, coalitions, inconsistencies) and the round's transcript, perform
a cleanup pass.

Tasks:
1. MERGE DUPLICATES: Find promises with the same from_faction, to_faction,
   and semantically similar content (same commitment rephrased differently).
   Return the earliest/best ID to keep and the IDs to remove.

2. DETECT FULFILLMENTS: Check each pending promise against the transcript.
   If a faction demonstrably followed through on a commitment (delivered
   what they promised, granted the access they offered, paid what they
   committed to), update its status to "kept" with evidence.

3. DETECT BROKEN PROMISES: If a faction's current statements directly
   contradict a prior promise (offered X but now demands the opposite,
   committed to a number but walked it back), update status to "broken".

4. FLAG INCONSISTENCIES: Compare each faction's current-round statements
   against their tracked promises and prior positions. Flag significant
   shifts — changed numbers, reversed positions, contradicted commitments.
   Set leverage_value higher (0.7-1.0) for clear contradictions, lower
   (0.3-0.5) for subtle shifts.

5. CATCH MISSED PROPOSALS: Review the transcript for concrete proposals
   with specific terms (numbers, conditions, trades) that are NOT already
   tracked as promises. Add them as new promise entries.

Rules:
- Be conservative on fulfillment: "kept" requires clear evidence, not
  just restating the commitment.
- Be aggressive on inconsistency detection: if a number changed or a
  position reversed, flag it even if the faction didn't acknowledge it.
- For merge decisions, prefer the ID with the most specific content.
- If nothing needs reconciliation, return empty arrays.
"""


class StateReconciler:
    """Post-round state cleanup via LLM semantic analysis."""

    def __init__(
        self,
        llm_client: Any,
        llm_config: dict[str, Any],
        tier: str = "commodity",
        attribution: str | None = None,
    ) -> None:
        self.llm_client = llm_client
        self.llm_config = llm_config
        self.tier = tier
        self.attribution = attribution

    async def reconcile(
        self,
        current_state: dict[str, Any],
        recent_events: list[Any],
        round_number: int,
    ) -> ReconciliationResult:
        # Format transcript
        transcript_lines = []
        for event in recent_events:
            e = getattr(event, "event", event)
            sender = getattr(e, "sender_faction", "?")
            content = getattr(e, "content", str(e))
            transcript_lines.append(f"[{sender}] {content}")

        transcript_text = "\n".join(transcript_lines)

        # Build user prompt with full context
        user_prompt = "\n\n".join([
            f"Round: {round_number}",
            "Current tracked promises:",
            json.dumps(current_state.get("promises", []), indent=2, sort_keys=True),
            "Current tracked coalitions:",
            json.dumps(current_state.get("coalitions", []), indent=2, sort_keys=True),
            "Current tracked inconsistencies:",
            json.dumps(current_state.get("inconsistencies", []), indent=2, sort_keys=True),
            "This round's transcript:",
            transcript_text,
        ])

        result = await structured_call(
            self.llm_client,
            self.llm_config,
            self.tier,
            schema=RECONCILIATION_SCHEMA,
            system_prompt=RECONCILIATION_PROMPT,
            user_prompt=user_prompt,
            max_retries=1,
            attribution=self.attribution,
            purpose="reconciliation",
        )

        if not result.success:
            return ReconciliationResult(success=False, error=result.error)

        data = result.data or {}
        return ReconciliationResult(
            success=True,
            merged_promises=data.get("merged_promises", []),
            updated_statuses=data.get("status_updates", []),
            new_inconsistencies=data.get("new_inconsistencies", []),
            missed_proposals=data.get("missed_proposals", []),
            merge_log=data.get("merge_log", []),
        )


def subsystem_llm_config(primary: dict[str, Any], tier: str = "commodity") -> dict[str, Any]:
    """Build a minimal LLM config dict for a subsystem call.

    primary: pipeline.yaml llm_providers.primary format — keys: provider,
             models (dict of tier→model-name), api_key_env (env var name).
    """
    api_key_env = primary.get("api_key_env", "")
    return {
        "provider": primary.get("provider", "openai"),
        "models": {tier: primary.get("models", {}).get(tier, "")},
        "api_key": os.getenv(api_key_env, "") if api_key_env else "",
    }


def build_reconciler(
    llm_client: Any,
    llm_providers_config: dict[str, Any],
    tier: str = "commodity",
    attribution: str | None = None,
) -> "StateReconciler | None":
    """Factory: create a StateReconciler from a pipeline llm_providers config.

    llm_providers_config: the full llm_providers dict (must have "primary" key).
    Returns None if the primary config is missing (reconciler disabled).
    """
    primary = llm_providers_config.get("primary", {})
    if not primary:
        return None
    return StateReconciler(
        llm_client=llm_client,
        llm_config=subsystem_llm_config(primary, tier),
        tier=tier,
        attribution=attribution,
    )


__all__ = [
    "ReconciliationResult",
    "StateReconciler",
    "subsystem_llm_config",
    "build_reconciler",
]
