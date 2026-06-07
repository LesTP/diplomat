from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from inspect import isawaitable
from typing import Any

from modules.generation import GenerationResult
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


_COMMANDS_HINT = (
    "\n\nCommands: /approve | /edit: <text> | /block | /revise: <directive>"
    " | /reasoning | /adversarial"
)


class OperatorReviewGate:
    def __init__(
        self,
        transport: Any,
        *,
        pipeline: Any | None = None,
        max_message_chars: int = 4000,
        state_manager: Any | None = None,
        timeout_seconds: float | None = None,
    ) -> None:
        if timeout_seconds is not None and timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive when set")
        self._transport = transport
        self._pipeline = pipeline
        # Retained for config compatibility; transport auto-chunks oversize text.
        self._max_message_chars = max_message_chars
        self._state_manager = state_manager
        self._timeout_seconds = timeout_seconds
        self._pending: tuple[
            GenerationResult,
            Any,
            int,
            asyncio.Future[ReviewDecision],
        ] | None = None
        self._revise_count: int = 0

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
        self._revise_count = 0
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
        normalized = command.strip().lower()

        # /revise: is recognized even when no pending review (returns error to operator)
        if normalized.startswith("/revise:"):
            directive = command.split(":", 1)[1].strip()
            return await self._handle_revise_command(directive)
        if normalized.startswith("/revise "):
            directive = command[8:].strip()
            return await self._handle_revise_command(directive)

        if self._pending is None:
            return False

        draft, adversarial, round_number, future = self._pending
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
            await self._send_section(
                "Reasoning:\n",
                (draft.reasoning or "").strip() or "[not available]",
            )
            return True
        elif normalized == "/adversarial":
            await self._send_section(
                "Adversarial:\n",
                _format_adversarial(adversarial),
            )
            return True
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

    async def _handle_revise_command(self, directive: str) -> bool:
        if not directive:
            return False

        if self._pending is None:
            await _maybe_await(
                self._transport.send(
                    OutboundMessage(
                        content="[no pending review — /revise: requires a draft in the queue]",
                        channel="coaching",
                    )
                )
            )
            return True

        if self._pipeline is None:
            await _maybe_await(
                self._transport.send(
                    OutboundMessage(
                        content="[/revise: not available — no pipeline configured]",
                        channel="coaching",
                    )
                )
            )
            return True

        draft, adversarial, round_number, future = self._pending
        new_draft = await self._pipeline.regenerate_with_directive(
            directive, draft.response_text or ""
        )
        self._revise_count += 1
        self._pending = (new_draft, None, round_number, future)

        draft_text = (new_draft.response_text or "").strip() or "[no draft text]"
        header = f"Round {round_number} — Revised Draft (revise {self._revise_count}/3)"
        content = header + "\n\nDraft:\n" + draft_text + _COMMANDS_HINT
        await _maybe_await(
            self._transport.send(OutboundMessage(content=content, channel="coaching"))
        )
        return True

    async def _send_draft(
        self,
        draft: GenerationResult,
        round_number: int,
    ) -> None:
        draft_text = (draft.response_text or "").strip() or "[no draft text]"
        header = f"Review Gate - Round {round_number}\n\nDraft:\n"
        content = header + draft_text + _COMMANDS_HINT
        await _maybe_await(
            self._transport.send(OutboundMessage(content=content, channel="coaching"))
        )

    async def _send_section(self, title: str, body: str) -> None:
        content = f"{title}{body}"
        await _maybe_await(
            self._transport.send(OutboundMessage(content=content, channel="coaching"))
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


def _get_any(value: Any, key: str, *, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(key, default)
    return getattr(value, key, default)


def _format_adversarial(adversarial: Any) -> str:
    if adversarial is None:
        return "Skipped or unavailable."
    success = _get_any(adversarial, "success", default=None)
    error = _get_any(adversarial, "error", default=None)
    analysis = _get_any(adversarial, "analysis", default=None)
    if success is False:
        return f"Failed: {error or 'no analysis available'}"
    if analysis is not None:
        if isinstance(analysis, str):
            stripped = analysis.strip()
            if stripped:
                return stripped
        return json.dumps(analysis, sort_keys=True)
    if isinstance(adversarial, str) and adversarial.strip():
        return adversarial.strip()
    return "Skipped or unavailable."


async def _maybe_await(value: Any) -> Any:
    if isawaitable(value):
        return await value
    return value


__all__ = [
    "AutoApproveReviewGate",
    "OperatorReviewGate",
    "ReviewDecision",
]
