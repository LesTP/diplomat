from __future__ import annotations

import asyncio

import pytest

from modules.generation import GenerationResult
from modules.review_gate import (
    AutoApproveReviewGate,
    OperatorReviewGate,
    ReviewDecision,
)
from modules.state_manager import SQLiteStateManager


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
        "\n\nCommands: /approve | /edit: <text> | /block | /revise: <directive>"
        " | /reasoning | /adversarial"
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


# --- /revise: command tests ---


@pytest.mark.asyncio
async def test_revise_no_pending_returns_true_with_error():
    transport = _FakeTransport()
    gate = OperatorReviewGate(transport)

    result = await gate.handle_command("/revise: make it softer")

    assert result is True
    assert len(transport.sent) == 1
    assert "no pending review" in transport.sent[0].content


@pytest.mark.asyncio
async def test_revise_no_pipeline_returns_true_with_error():
    transport = _FakeTransport()
    gate = OperatorReviewGate(transport, pipeline=None)

    task = asyncio.create_task(gate.submit(_draft(), adversarial=None, round_number=2))
    await asyncio.sleep(0)

    result = await gate.handle_command("/revise: be more assertive")

    assert result is True
    assert any("not available" in m.content for m in transport.sent)

    await gate.handle_command("/block")
    await task


@pytest.mark.asyncio
async def test_revise_happy_path_replaces_slot_and_submit_returns_revised():
    transport = _FakeTransport()
    revised_text = "England insists on an equitable arrangement."
    pipeline = _FakePipeline(revised_text)
    gate = OperatorReviewGate(transport, pipeline=pipeline)

    task = asyncio.create_task(gate.submit(_draft(), adversarial=None, round_number=3))
    await asyncio.sleep(0)
    assert len(transport.sent) == 1

    result = await gate.handle_command("/revise: be more assertive")

    assert result is True
    assert len(transport.sent) == 2
    revised_msg = transport.sent[1]
    assert revised_msg.channel == "coaching"
    assert "Round 3 — Revised Draft (revise 1/3)" in revised_msg.content
    assert revised_text in revised_msg.content
    assert gate._revise_count == 1

    await gate.handle_command("/approve")
    decision = await task

    assert decision.action == "approved"
    assert decision.final_text == revised_text


@pytest.mark.asyncio
async def test_revise_legacy_syntax_no_colon():
    transport = _FakeTransport()
    revised_text = "England proposes mutual restraint."
    pipeline = _FakePipeline(revised_text)
    gate = OperatorReviewGate(transport, pipeline=pipeline)

    task = asyncio.create_task(gate.submit(_draft(), adversarial=None, round_number=1))
    await asyncio.sleep(0)

    result = await gate.handle_command("/revise soften the tone")

    assert result is True
    assert gate._revise_count == 1
    assert pipeline.last_directive == "soften the tone"

    await gate.handle_command("/approve")
    decision = await task
    assert decision.action == "approved"
    assert decision.final_text == revised_text


@pytest.mark.asyncio
async def test_revise_chain_increments_counter():
    transport = _FakeTransport()
    pipeline = _FakePipeline("Draft v2")
    gate = OperatorReviewGate(transport, pipeline=pipeline)

    task = asyncio.create_task(gate.submit(_draft(), adversarial=None, round_number=5))
    await asyncio.sleep(0)

    await gate.handle_command("/revise: first revision")
    pipeline.next_response = "Draft v3"
    await gate.handle_command("/revise: second revision")

    assert gate._revise_count == 2
    assert "revise 2/3" in transport.sent[-1].content

    await gate.handle_command("/approve")
    decision = await task
    assert decision.action == "approved"
    assert decision.final_text == "Draft v3"


@pytest.mark.asyncio
async def test_revise_empty_directive_returns_false():
    transport = _FakeTransport()
    pipeline = _FakePipeline("Draft v2")
    gate = OperatorReviewGate(transport, pipeline=pipeline)

    task = asyncio.create_task(gate.submit(_draft(), adversarial=None, round_number=1))
    await asyncio.sleep(0)

    result = await gate.handle_command("/revise: ")
    assert result is False

    await gate.handle_command("/block")
    await task


@pytest.mark.asyncio
async def test_revise_resets_count_on_new_submit():
    transport = _FakeTransport()
    pipeline = _FakePipeline("Draft v2")
    gate = OperatorReviewGate(transport, pipeline=pipeline)

    task = asyncio.create_task(gate.submit(_draft(), adversarial=None, round_number=1))
    await asyncio.sleep(0)
    await gate.handle_command("/revise: first")
    await gate.handle_command("/approve")
    await task

    assert gate._revise_count == 1

    task2 = asyncio.create_task(gate.submit(_draft(), adversarial=None, round_number=2))
    await asyncio.sleep(0)
    assert gate._revise_count == 0

    await gate.handle_command("/approve")
    await task2


@pytest.mark.asyncio
async def test_revise_cap_rejects_fourth_directive_without_changing_pending_draft():
    transport = _FakeTransport()
    pipeline = _FakePipeline("Draft v2")
    gate = OperatorReviewGate(transport, pipeline=pipeline, max_revises=3)

    task = asyncio.create_task(gate.submit(_draft(), adversarial=None, round_number=5))
    await asyncio.sleep(0)

    pipeline.next_response = "Draft v2"
    await gate.handle_command("/revise: first revision")
    pipeline.next_response = "Draft v3"
    await gate.handle_command("/revise: second revision")
    pipeline.next_response = "Draft v4"
    await gate.handle_command("/revise: third revision")

    assert gate._revise_count == 3
    assert len(pipeline.calls) == 3

    result = await gate.handle_command("/revise: fourth revision")

    assert result is True
    assert transport.sent[-1].content == (
        "[revise limit reached — /approve, /edit:, or /block to resolve]"
    )
    assert gate._revise_count == 3
    assert len(pipeline.calls) == 3

    await gate.handle_command("/approve")
    decision = await task

    assert decision.action == "approved"
    assert decision.final_text == "Draft v4"


@pytest.mark.asyncio
async def test_revise_cap_logs_directive_chain_in_state_manager(tmp_path):
    transport = _FakeTransport()
    pipeline = _FakePipeline("Draft v2")
    state_manager = SQLiteStateManager(
        tmp_path / "review_gate.db",
        "config/schemas/state_patch.json",
    )
    gate = OperatorReviewGate(
        transport,
        pipeline=pipeline,
        state_manager=state_manager,
        max_revises=3,
    )

    task = asyncio.create_task(gate.submit(_draft(), adversarial=None, round_number=7))
    await asyncio.sleep(0)

    pipeline.next_response = "Draft v2"
    await gate.handle_command("/revise: first revision")
    pipeline.next_response = "Draft v3"
    await gate.handle_command("/revise: second revision")
    pipeline.next_response = "Draft v4"
    await gate.handle_command("/revise: third revision")

    assert await gate.handle_command("/revise: fourth revision") is True
    assert transport.sent[-1].content == (
        "[revise limit reached — /approve, /edit:, or /block to resolve]"
    )

    await gate.handle_command("/approve")
    decision = await task

    rows = await state_manager.query("review_gate_edits", {})

    assert decision.action == "approved"
    assert len(rows) == 1
    assert rows[0]["decision"] == "approved"
    assert rows[0]["edit_text"] == "Draft v4"
    assert rows[0]["revise_directives"] == [
        "first revision",
        "second revision",
        "third revision",
    ]


class _FakePipeline:
    def __init__(self, response: str) -> None:
        self.next_response = response
        self.last_directive: str | None = None
        self.calls: list[dict] = []

    async def regenerate_with_directive(
        self, directive: str, previous_draft: str
    ) -> Any:
        self.last_directive = directive
        self.calls.append({"directive": directive, "previous_draft": previous_draft})
        from modules.generation import GenerationResult

        return GenerationResult(
            success=True,
            response_text=self.next_response,
            reasoning="Revised per directive.",
            raw_response=None,
            error=None,
        )


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
