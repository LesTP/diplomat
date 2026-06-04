from __future__ import annotations

import asyncio

import pytest

from modules.generation import GenerationResult
from modules.review_gate import (
    AutoApproveReviewGate,
    OperatorReviewGate,
    ReviewDecision,
)


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


@pytest.mark.asyncio
async def test_operator_review_gate_approve_decision():
    transport = _FakeTransport()
    gate = OperatorReviewGate(transport)

    task = asyncio.create_task(gate.submit(_draft(), adversarial=None, round_number=4))
    await asyncio.sleep(0)

    assert len(transport.sent) == 1
    assert transport.sent[0].channel == "coaching"
    assert transport.sent[0].content.startswith("Review Gate - Round 4\n\nDraft:\n")
    assert transport.sent[0].content.endswith(
        "\n\nCommands: /approve | /edit: <text> | /block | /reasoning | /adversarial"
    )

    assert await gate.handle_command("/approve") is True
    decision = await task

    assert decision == ReviewDecision(
        action="approved",
        final_text="France, we can coordinate in Belgium.",
        edit_notes=None,
    )


@pytest.mark.asyncio
async def test_operator_review_gate_edit_legacy_decision():
    transport = _FakeTransport()
    gate = OperatorReviewGate(transport)

    task = asyncio.create_task(gate.submit(_draft(), adversarial=None, round_number=4))
    await asyncio.sleep(0)

    assert await gate.handle_command("/edit Keep this softer.") is True
    decision = await task

    assert decision == ReviewDecision(
        action="edited",
        final_text="Keep this softer.",
        edit_notes="Keep this softer.",
    )


@pytest.mark.asyncio
async def test_operator_review_gate_block_decision():
    transport = _FakeTransport()
    gate = OperatorReviewGate(transport)

    task = asyncio.create_task(gate.submit(_draft(), adversarial=None, round_number=4))
    await asyncio.sleep(0)

    assert await gate.handle_command("/block") is True
    decision = await task

    assert decision == ReviewDecision(
        action="blocked",
        final_text=None,
        edit_notes=None,
    )


@pytest.mark.asyncio
async def test_operator_review_gate_state_command_passthrough():
    transport = _FakeTransport()
    gate = OperatorReviewGate(transport)

    task = asyncio.create_task(gate.submit(_draft(), adversarial=None, round_number=4))
    await asyncio.sleep(0)

    assert await gate.handle_command("/state") is False
    assert not task.done()
    assert len(transport.sent) == 1

    assert await gate.handle_command("/approve") is True
    decision = await task

    assert decision.action == "approved"


@pytest.mark.asyncio
async def test_operator_review_gate_reasoning_fetch_then_approve():
    transport = _FakeTransport()
    gate = OperatorReviewGate(transport)

    task = asyncio.create_task(gate.submit(_draft(), adversarial=None, round_number=4))
    await asyncio.sleep(0)

    assert await gate.handle_command("/reasoning") is True
    assert len(transport.sent) == 2
    assert transport.sent[1].content == "Reasoning:\nKeeps the promise limited."

    assert await gate.handle_command("/approve") is True
    decision = await task

    assert decision.action == "approved"


@pytest.mark.asyncio
async def test_operator_review_gate_adversarial_fetch_then_approve():
    transport = _FakeTransport()
    gate = OperatorReviewGate(transport)

    task = asyncio.create_task(
        gate.submit(
            _draft(),
            adversarial={"success": True, "analysis": "Promise is limited."},
            round_number=4,
        )
    )
    await asyncio.sleep(0)

    assert await gate.handle_command("/adversarial") is True
    assert len(transport.sent) == 2
    assert transport.sent[1].content == "Adversarial:\nPromise is limited."

    assert await gate.handle_command("/approve") is True
    decision = await task

    assert decision.action == "approved"


@pytest.mark.asyncio
async def test_operator_review_gate_reasoning_missing_sends_placeholder():
    transport = _FakeTransport()
    gate = OperatorReviewGate(transport)

    task = asyncio.create_task(
        gate.submit(_draft(reasoning=None), adversarial=None, round_number=4)
    )
    await asyncio.sleep(0)

    assert await gate.handle_command("/reasoning") is True
    assert transport.sent[1].content == "Reasoning:\n[not available]"

    assert await gate.handle_command("/approve") is True
    await task


@pytest.mark.asyncio
async def test_operator_review_gate_adversarial_missing_sends_placeholder():
    transport = _FakeTransport()
    gate = OperatorReviewGate(transport)

    task = asyncio.create_task(gate.submit(_draft(), adversarial=None, round_number=4))
    await asyncio.sleep(0)

    assert await gate.handle_command("/adversarial") is True
    assert transport.sent[1].content == "Adversarial:\nSkipped or unavailable."

    assert await gate.handle_command("/approve") is True
    await task


@pytest.mark.asyncio
async def test_operator_review_gate_reasoning_re_request_is_idempotent():
    transport = _FakeTransport()
    gate = OperatorReviewGate(transport)

    task = asyncio.create_task(gate.submit(_draft(), adversarial=None, round_number=4))
    await asyncio.sleep(0)

    assert await gate.handle_command("/reasoning") is True
    assert len(transport.sent) == 2
    assert await gate.handle_command("/reasoning") is True
    assert len(transport.sent) == 3
    assert transport.sent[2].content == "Reasoning:\nKeeps the promise limited."

    assert await gate.handle_command("/approve") is True
    await task


@pytest.mark.asyncio
async def test_operator_review_gate_chunks_large_reasoning_through_transport():
    transport = _FakeTransport()
    gate = OperatorReviewGate(transport)
    draft = _draft(reasoning="Reasoning section. " * 300)

    task = asyncio.create_task(gate.submit(draft, adversarial=None, round_number=4))
    await asyncio.sleep(0)

    assert await gate.handle_command("/reasoning") is True
    assert len(transport.sent) == 2
    assert transport.sent[1].content.startswith("Reasoning:\n")
    assert len(transport.sent[1].content) > 4096

    assert await gate.handle_command("/approve") is True
    await task


@pytest.mark.asyncio
async def test_operator_review_gate_rejects_concurrent_submit():
    transport = _FakeTransport()
    gate = OperatorReviewGate(transport)

    task = asyncio.create_task(gate.submit(_draft(), adversarial=None, round_number=4))
    await asyncio.sleep(0)

    with pytest.raises(RuntimeError, match="pending review"):
        await gate.submit(_draft(), adversarial=None, round_number=4)

    assert await gate.handle_command("/block") is True
    await task


@pytest.mark.asyncio
async def test_operator_review_gate_handle_command_before_submit_returns_false():
    gate = OperatorReviewGate(_FakeTransport())

    assert await gate.handle_command("/approve") is False


@pytest.mark.asyncio
async def test_operator_review_gate_timeout_auto_blocks_and_logs():
    state_manager = _FakeStateManager()
    gate = OperatorReviewGate(
        _NeverTransport(),
        state_manager=state_manager,
        timeout_seconds=0.05,
    )

    decision = await gate.submit(_draft(), adversarial=None, round_number=4)

    assert decision == ReviewDecision(
        action="blocked",
        final_text=None,
        edit_notes="Review timed out after 0.05 seconds",
    )
    assert state_manager.calls == [
        {
            "round_number": 4,
            "decision": decision,
            "draft_text": "  France, we can coordinate in Belgium.  ",
        }
    ]


@pytest.mark.asyncio
async def test_operator_review_gate_chunks_large_draft_through_transport():
    transport = _FakeTransport()
    gate = OperatorReviewGate(transport)
    draft = _draft(
        response_text="Lorem ipsum dolor sit amet, consectetur adipiscing elit. " * 100,
    )

    task = asyncio.create_task(gate.submit(draft, adversarial=None, round_number=4))
    await asyncio.sleep(0)

    assert len(transport.sent) == 1
    assert all(message.channel == "coaching" for message in transport.sent)
    assert transport.sent[0].content.startswith("Review Gate - Round 4\n\nDraft:\n")
    assert len(transport.sent[0].content) > 4096

    assert await gate.handle_command("/approve") is True
    decision = await task

    assert decision.action == "approved"


@pytest.mark.asyncio
async def test_operator_review_gate_logs_decision_once():
    state_manager = _FakeStateManager()
    gate = OperatorReviewGate(_FakeTransport(), state_manager=state_manager)

    task = asyncio.create_task(gate.submit(_draft(), adversarial=None, round_number=4))
    await asyncio.sleep(0)

    assert await gate.handle_command("/approve") is True
    decision = await task

    assert decision == ReviewDecision(
        action="approved",
        final_text="France, we can coordinate in Belgium.",
        edit_notes=None,
    )
    assert state_manager.calls == [
        {
            "round_number": 4,
            "decision": decision,
            "draft_text": "  France, we can coordinate in Belgium.  ",
        }
    ]


def test_review_decision_contract_fields():
    decision = ReviewDecision(
        action="edited",
        final_text="Edited message.",
        edit_notes="Trimmed promise.",
    )

    assert decision.action == "edited"
    assert decision.final_text == "Edited message."
    assert decision.edit_notes == "Trimmed promise."



class _FakeStateManager:
    def __init__(self) -> None:
        self.calls = []

    async def log_review_decision(self, **kwargs) -> None:
        self.calls.append(kwargs)


class _FakeTransport:
    def __init__(self) -> None:
        self.sent: list[object] = []

    async def send(self, message) -> None:
        self.sent.append(message)

    async def listen(self):
        if False:
            yield None


class _NeverTransport:
    def __init__(self) -> None:
        self.sent: list[object] = []

    async def send(self, message) -> None:
        self.sent.append(message)

    async def listen(self):
        if False:
            yield None
