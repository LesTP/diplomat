from __future__ import annotations

import pytest

from modules.generation import GenerationResult
from modules.review_gate import AutoApproveReviewGate, ReviewDecision


def _draft(
    *,
    success: bool = True,
    response_text: str | None = "  France, we can coordinate in Belgium.  ",
    reasoning: str | None = "Keeps the promise limited.",
    error: str | None = None,
) -> GenerationResult:
    return GenerationResult(
        success=success,
        response_text=response_text,
        reasoning=reasoning,
        raw_response=None,
        error=error,
    )


@pytest.mark.asyncio
async def test_auto_approve_successful_draft():
    gate = AutoApproveReviewGate()

    decision = await gate.submit(_draft(), adversarial=None, round_number=3)

    assert decision == ReviewDecision(
        action="approved",
        final_text="France, we can coordinate in Belgium.",
        edit_notes=None,
    )


@pytest.mark.asyncio
async def test_auto_approve_blocks_failed_draft():
    gate = AutoApproveReviewGate()

    decision = await gate.submit(
        _draft(success=False, response_text=None, reasoning=None, error="provider down"),
        adversarial=None,
        round_number=3,
    )

    assert decision == ReviewDecision(
        action="blocked",
        final_text=None,
        edit_notes="provider down",
    )


@pytest.mark.asyncio
async def test_auto_approve_blocks_blank_draft():
    gate = AutoApproveReviewGate()

    decision = await gate.submit(
        _draft(response_text="   "),
        adversarial={"analysis": "ignored"},
        round_number=3,
    )

    assert decision == ReviewDecision(
        action="blocked",
        final_text=None,
        edit_notes="Draft response was blank",
    )


def test_review_decision_contract_fields():
    decision = ReviewDecision(
        action="edited",
        final_text="Edited message.",
        edit_notes="Trimmed promise.",
    )

    assert decision.action == "edited"
    assert decision.final_text == "Edited message."
    assert decision.edit_notes == "Trimmed promise."
