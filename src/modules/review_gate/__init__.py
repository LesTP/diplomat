from __future__ import annotations

import asyncio
from dataclasses import dataclass
from inspect import isawaitable
from typing import Any

from modules.generation import GenerationResult
from modules.review_gate.chunking import CONTINUATION_PREFIX, chunk_text
from modules.transport import OutboundMessage


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


class OperatorReviewGate:
    def __init__(
        self,
        transport: Any,
        *,
        max_message_chars: int = 4000,
        state_manager: Any | None = None,
        timeout_seconds: float | None = None,
    ) -> None:
        if timeout_seconds is not None and timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive when set")
        self._transport = transport
        self._max_message_chars = max_message_chars
        self._state_manager = state_manager
        self._timeout_seconds = timeout_seconds
        self._pending: tuple[
            GenerationResult,
            Any,
            int,
            asyncio.Future[ReviewDecision],
        ] | None = None

    async def submit(
        self,
        draft: GenerationResult,
        adversarial: Any,
        round_number: int,
    ) -> ReviewDecision:
        if self._pending is not None:
            raise RuntimeError("OperatorReviewGate has a pending review")

        loop = asyncio.get_running_loop()
        future: asyncio.Future[ReviewDecision] = loop.create_future()
        self._pending = (draft, adversarial, round_number, future)
        decision: ReviewDecision | None = None
        try:
            await self._send_draft(draft, round_number)
        except Exception as exc:
            decision = ReviewDecision(
                action="blocked",
                final_text=None,
                edit_notes=f"transport error: {exc}",
            )
            self._pending = None
            await self._log_decision(decision, draft, round_number)
            raise

        try:
            if self._timeout_seconds is None:
                decision = await future
            else:
                decision = await asyncio.wait_for(
                    future, timeout=self._timeout_seconds
                )
        except asyncio.TimeoutError:
            decision = ReviewDecision(
                action="blocked",
                final_text=None,
                edit_notes=f"Review timed out after {self._timeout_seconds} seconds",
            )
            if not future.done():
                future.cancel()
        finally:
            self._pending = None

        assert decision is not None
        await self._log_decision(decision, draft, round_number)
        return decision

    async def handle_command(self, command: str) -> bool:
        if self._pending is None:
            return False

        draft, adversarial, round_number, future = self._pending
        normalized = command.strip().lower()
        if normalized == "/approve":
            self._resolve_pending(
                future,
                ReviewDecision(
                    action="approved",
                    final_text=(draft.response_text or "").strip() or None,
                    edit_notes=None,
                ),
            )
            return True
        if normalized == "/block":
            self._resolve_pending(
                future,
                ReviewDecision(action="blocked", final_text=None, edit_notes=None),
            )
            return True
        if normalized.startswith("/edit:"):
            edited_text = command.split(":", 1)[1].strip()
        elif normalized.startswith("/edit "):
            edited_text = command[6:].strip()
        elif normalized == "/reasoning":
            # TODO 31.3: lazy-fetch the reasoning section through transport.
            return False
        elif normalized == "/adversarial":
            # TODO 31.3: lazy-fetch the adversarial section through transport.
            return False
        else:
            return False

        if not edited_text:
            return False

        self._resolve_pending(
            future,
            ReviewDecision(
                action="edited",
                final_text=edited_text,
                edit_notes=edited_text,
            ),
        )
        return True

    async def _send_draft(
        self,
        draft: GenerationResult,
        round_number: int,
    ) -> None:
        draft_text = (draft.response_text or "").strip() or "[no draft text]"
        header = f"Review Gate - Round {round_number}\n\nDraft:\n"
        commands_hint = (
            "\n\nCommands: /approve | /edit: <text> | /block | /reasoning | /adversarial"
        )
        raw_limit = (
            self._max_message_chars
            - len(commands_hint)
            - max(len(header), len(CONTINUATION_PREFIX))
        )
        if raw_limit <= 0:
            raise ValueError("max_message_chars is too small for review messages")

        chunks = chunk_text(draft_text, raw_limit)
        for index, chunk in enumerate(chunks):
            content = chunk
            if index == 0:
                content = header + content
            if index == len(chunks) - 1:
                content += commands_hint
            await _maybe_await(
                self._transport.send(
                    OutboundMessage(content=content, channel="coaching")
                )
            )

    def _resolve_pending(
        self,
        future: asyncio.Future[ReviewDecision],
        decision: ReviewDecision,
    ) -> None:
        if not future.done():
            future.set_result(decision)

    async def _log_decision(
        self,
        decision: ReviewDecision,
        draft: GenerationResult,
        round_number: int,
    ) -> None:
        if self._state_manager is None:
            return
        log_review_decision = getattr(
            self._state_manager, "log_review_decision", None
        )
        if log_review_decision is None:
            return
        await _maybe_await(
            log_review_decision(
                round_number=round_number,
                decision=decision,
                draft_text=draft.response_text,
            )
        )


class TelegramReviewGate:
    def __init__(
        self,
        telegram_client: Any,
        *,
        coaching_channel_id: str | int,
        state_manager: Any | None = None,
        timeout_seconds: float | None = None,
    ) -> None:
        if timeout_seconds is not None and timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive when set")
        self._telegram_client = telegram_client
        self._coaching_channel_id = coaching_channel_id
        self._state_manager = state_manager
        self._timeout_seconds = timeout_seconds

    async def submit(
        self,
        draft: GenerationResult,
        adversarial: Any,
        round_number: int,
    ) -> ReviewDecision:
        await _maybe_await(
            self._telegram_client.send_message(
                self._coaching_channel_id,
                self._format_review_message(draft, adversarial, round_number),
            )
        )
        decision = await self._wait_with_optional_timeout(draft)
        await self._log_decision(decision, draft, round_number)
        return decision

    async def _wait_with_optional_timeout(
        self, draft: GenerationResult
    ) -> ReviewDecision:
        if self._timeout_seconds is None:
            return await self._wait_for_decision(draft)
        try:
            return await asyncio.wait_for(
                self._wait_for_decision(draft),
                timeout=self._timeout_seconds,
            )
        except asyncio.TimeoutError:
            return ReviewDecision(
                action="blocked",
                final_text=None,
                edit_notes=f"Review timed out after {self._timeout_seconds} seconds",
            )

    async def _wait_for_decision(self, draft: GenerationResult) -> ReviewDecision:
        while True:
            update = await _maybe_await(self._telegram_client.get_next_update())
            if update is None:
                continue
            if str(_get_update_value(update, "chat_id", "chat.id", default="")) != str(
                self._coaching_channel_id
            ):
                continue

            text = _get_update_value(
                update,
                "content",
                "text",
                "message_text",
                "message",
                default="",
            )
            if not isinstance(text, str):
                continue

            decision = self._parse_command(text, draft)
            if decision is not None:
                return decision

            await _maybe_await(
                self._telegram_client.send_message(
                    self._coaching_channel_id,
                    "Unknown review command. Use /approve, /edit: ..., or /block.",
                )
            )

    def _parse_command(
        self, text: str, draft: GenerationResult
    ) -> ReviewDecision | None:
        command = text.strip()
        lowered = command.lower()
        if lowered == "/approve":
            final_text = (draft.response_text or "").strip()
            return ReviewDecision(
                action="approved",
                final_text=final_text or None,
                edit_notes=None,
            )
        if lowered == "/block":
            return ReviewDecision(action="blocked", final_text=None, edit_notes=None)
        if lowered.startswith("/edit:"):
            edited_text = command.split(":", 1)[1].strip()
        elif lowered.startswith("/edit "):
            edited_text = command[6:].strip()
        else:
            return None

        if not edited_text:
            return None
        return ReviewDecision(
            action="edited",
            final_text=edited_text,
            edit_notes=edited_text,
        )

    def _format_review_message(
        self,
        draft: GenerationResult,
        adversarial: Any,
        round_number: int,
    ) -> str:
        sections = [
            f"Review Gate - Round {round_number}",
            "",
            "Draft:",
            (draft.response_text or "").strip() or "[no draft text]",
        ]
        if draft.reasoning:
            sections.extend(["", "Reasoning:", draft.reasoning.strip()])
        sections.extend(["", "Adversarial:", self._format_adversarial(adversarial)])
        sections.extend(
            [
                "",
                "Commands:",
                "/approve",
                "/edit: <replacement text>",
                "/block",
            ]
        )
        return "\n".join(sections)

    def _format_adversarial(self, adversarial: Any) -> str:
        if adversarial is None:
            return "Skipped or unavailable."
        success = _get_any(adversarial, "success", default=None)
        error = _get_any(adversarial, "error", default=None)
        analysis = _get_any(adversarial, "analysis", default=None)
        if success is False:
            return f"Failed: {error or 'no analysis available'}"
        if isinstance(analysis, str) and analysis.strip():
            return analysis.strip()
        if isinstance(adversarial, str) and adversarial.strip():
            return adversarial.strip()
        return "Skipped or unavailable."

    async def _log_decision(
        self,
        decision: ReviewDecision,
        draft: GenerationResult,
        round_number: int,
    ) -> None:
        if self._state_manager is None:
            return
        log_review_decision = getattr(
            self._state_manager, "log_review_decision", None
        )
        if log_review_decision is None:
            return
        await _maybe_await(
            log_review_decision(
                round_number=round_number,
                decision=decision,
                draft_text=draft.response_text,
            )
        )


def _get_any(value: Any, key: str, *, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(key, default)
    return getattr(value, key, default)


def _get_update_value(update: Any, *keys: str, default: Any = ...):
    for key in keys:
        current = update
        found = True
        for part in key.split("."):
            if isinstance(current, dict) and part in current:
                current = current[part]
            elif hasattr(current, part):
                current = getattr(current, part)
            else:
                found = False
                break
        if found:
            return current
    if default is not ...:
        return default
    raise ValueError(f"Telegram update requires one of: {', '.join(keys)}")


async def _maybe_await(value: Any) -> Any:
    if isawaitable(value):
        return await value
    return value


__all__ = [
    "AutoApproveReviewGate",
    "OperatorReviewGate",
    "ReviewDecision",
    "TelegramReviewGate",
]
