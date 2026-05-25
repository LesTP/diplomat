from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from modules.generation import GenerationResult


@dataclass(frozen=True)
class ReviewDecision:
    action: str
    final_text: str | None
    edit_notes: str | None


class AutoApproveReviewGate:
    async def submit(
        self,
        draft: GenerationResult,
        adversarial: Any,
        round_number: int,
    ) -> ReviewDecision:
        if not draft.success:
            return ReviewDecision(
                action="blocked",
                final_text=None,
                edit_notes=draft.error or "Draft generation failed",
            )

        response_text = draft.response_text or ""
        if not response_text.strip():
            return ReviewDecision(
                action="blocked",
                final_text=None,
                edit_notes="Draft response was blank",
            )

        return ReviewDecision(
            action="approved",
            final_text=response_text.strip(),
            edit_notes=None,
        )


__all__ = ["AutoApproveReviewGate", "ReviewDecision"]
