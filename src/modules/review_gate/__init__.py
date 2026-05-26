from __future__ import annotations

import asyncio
from dataclasses import dataclass
from inspect import isawaitable
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


__all__ = ["AutoApproveReviewGate", "ReviewDecision", "TelegramReviewGate"]
