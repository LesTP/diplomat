from __future__ import annotations

import json
from collections.abc import Iterable
from datetime import datetime, timezone
from typing import Any

from modules.types import InboundEvent


def make_event(
    content: str = "France proposes a western coalition.",
    *,
    sender_faction: str = "france",
    channel: str = "public",
    recipient: str | None = None,
    timestamp: datetime | None = None,
    telegram_msg_id: int | None = None,
) -> InboundEvent:
    return InboundEvent(
        timestamp=timestamp or datetime(2026, 5, 27, tzinfo=timezone.utc),
        sender_faction=sender_faction,
        channel=channel,
        content=content,
        recipient=recipient,
        telegram_msg_id=telegram_msg_id,
    )


def make_round_end_event() -> InboundEvent:
    return make_event("[ROUND END]", sender_faction="moderator")


class FakeLLMClient:
    def __init__(self, responses: Iterable[str | dict[str, Any]] | None = None) -> None:
        self.responses = list(responses or [_default_generation_response()])
        self.calls: list[dict[str, Any]] = []

    async def complete(self, **kwargs: Any) -> str:
        self.calls.append(kwargs)
        if not self.responses:
            return _default_generation_response()
        response = self.responses.pop(0)
        if isinstance(response, str):
            return response
        return json.dumps(response, sort_keys=True)


class FakeCostAccountant:
    def __init__(self, budgets: Iterable[float] | None = None, session_total: float = 0.0) -> None:
        self.budgets = list(budgets or [])
        self.checks = 0
        self.resets: list[float] = []
        self._session_total = session_total

    @property
    def session_total(self) -> float:
        return self._session_total

    def available_budget(self) -> float:
        self.checks += 1
        if self.budgets:
            return self.budgets.pop(0)
        return 1.0

    def reset_round_budget(self, amount: float) -> None:
        self.resets.append(amount)


def _default_generation_response() -> str:
    return json.dumps(
        {
            "response": "England will support a balanced settlement.",
            "reasoning": "Maintains flexibility while acknowledging the offer.",
        },
        sort_keys=True,
    )

