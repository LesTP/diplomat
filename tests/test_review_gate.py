from __future__ import annotations

import pytest

from modules.generation import GenerationResult
from modules.review_gate import AutoApproveReviewGate, ReviewDecision, TelegramReviewGate


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


@pytest.mark.asyncio
async def test_telegram_review_gate_sends_formatted_review_prompt():
    client = _FakeTelegramClient(
        updates=[{"chat_id": "coach", "text": "/approve"}],
    )
    gate = TelegramReviewGate(client, coaching_channel_id="coach")

    await gate.submit(
        _draft(),
        adversarial={"success": True, "analysis": "Promise is limited."},
        round_number=4,
    )

    assert client.sent[0][0] == "coach"
    message = client.sent[0][1]
    assert "Review Gate - Round 4" in message
    assert "Draft:\nFrance, we can coordinate in Belgium." in message
    assert "Reasoning:\nKeeps the promise limited." in message
    assert "Adversarial:\nPromise is limited." in message
    assert "/approve" in message
    assert "/edit: <replacement text>" in message
    assert "/block" in message


@pytest.mark.asyncio
async def test_telegram_review_gate_approve_decision():
    gate = TelegramReviewGate(
        _FakeTelegramClient(updates=[{"chat_id": "coach", "text": "/approve"}]),
        coaching_channel_id="coach",
    )

    decision = await gate.submit(_draft(), adversarial=None, round_number=3)

    assert decision == ReviewDecision(
        action="approved",
        final_text="France, we can coordinate in Belgium.",
        edit_notes=None,
    )


@pytest.mark.asyncio
async def test_telegram_review_gate_edit_decision():
    gate = TelegramReviewGate(
        _FakeTelegramClient(
            updates=[{"chat_id": "coach", "text": "/edit: Keep this softer."}]
        ),
        coaching_channel_id="coach",
    )

    decision = await gate.submit(_draft(), adversarial=None, round_number=3)

    assert decision == ReviewDecision(
        action="edited",
        final_text="Keep this softer.",
        edit_notes="Keep this softer.",
    )


@pytest.mark.asyncio
async def test_telegram_review_gate_block_decision():
    gate = TelegramReviewGate(
        _FakeTelegramClient(updates=[{"chat_id": "coach", "text": "/block"}]),
        coaching_channel_id="coach",
    )

    decision = await gate.submit(_draft(), adversarial=None, round_number=3)

    assert decision == ReviewDecision(
        action="blocked",
        final_text=None,
        edit_notes=None,
    )


@pytest.mark.asyncio
async def test_telegram_review_gate_filters_other_channels():
    gate = TelegramReviewGate(
        _FakeTelegramClient(
            updates=[
                {"chat_id": "public", "text": "/block"},
                {"chat": {"id": "coach"}, "message": "/approve"},
            ]
        ),
        coaching_channel_id="coach",
    )

    decision = await gate.submit(_draft(), adversarial=None, round_number=3)

    assert decision.action == "approved"


@pytest.mark.asyncio
async def test_telegram_review_gate_unknown_command_retries():
    client = _FakeTelegramClient(
        updates=[
            {"chat_id": "coach", "text": "maybe"},
            {"chat_id": "coach", "text": "/block"},
        ]
    )
    gate = TelegramReviewGate(client, coaching_channel_id="coach")

    decision = await gate.submit(_draft(), adversarial=None, round_number=3)

    assert decision.action == "blocked"
    assert client.sent[1] == (
        "coach",
        "Unknown review command. Use /approve, /edit: ..., or /block.",
    )


@pytest.mark.asyncio
async def test_telegram_review_gate_logs_decision_when_hook_exists():
    state_manager = _FakeStateManager()
    gate = TelegramReviewGate(
        _FakeTelegramClient(updates=[{"chat_id": "coach", "text": "/approve"}]),
        coaching_channel_id="coach",
        state_manager=state_manager,
    )

    decision = await gate.submit(_draft(), adversarial=None, round_number=3)

    assert state_manager.calls == [
        {
            "round_number": 3,
            "decision": decision,
            "draft_text": "  France, we can coordinate in Belgium.  ",
        }
    ]


@pytest.mark.asyncio
async def test_telegram_review_gate_formats_adversarial_failure_warning():
    client = _FakeTelegramClient(updates=[{"chat_id": "coach", "text": "/approve"}])
    gate = TelegramReviewGate(client, coaching_channel_id="coach")

    await gate.submit(
        _draft(reasoning=None),
        adversarial={"success": False, "error": "adversarial disabled"},
        round_number=3,
    )

    assert "Reasoning:" not in client.sent[0][1]
    assert "Adversarial:\nFailed: adversarial disabled" in client.sent[0][1]


class _FakeTelegramClient:
    def __init__(self, updates: list[object]) -> None:
        self.updates = list(updates)
        self.sent: list[tuple[str | int, str]] = []

    async def send_message(self, chat_id: str | int, content: str) -> None:
        self.sent.append((chat_id, content))

    async def get_next_update(self):
        if not self.updates:
            raise AssertionError("No fake Telegram updates remaining")
        return self.updates.pop(0)


class _FakeStateManager:
    def __init__(self) -> None:
        self.calls = []

    async def log_review_decision(self, **kwargs) -> None:
        self.calls.append(kwargs)
