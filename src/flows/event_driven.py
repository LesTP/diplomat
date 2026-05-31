from __future__ import annotations

import asyncio
import contextlib
import re
from collections.abc import Callable
from inspect import isawaitable
from typing import Any

from modules.transport import Transport
from modules.types import InboundEvent
from pipeline import Pipeline


RoundDetector = Callable[[InboundEvent], bool]
AddressDetector = Callable[[InboundEvent], bool]


class EventDrivenFlow:
    def __init__(
        self,
        *,
        pipeline: Pipeline,
        transport: Transport,
        round_detector: RoundDetector | None = None,
        address_detector: AddressDetector | None = None,
        message_debounce_seconds: float = 0.5,
    ) -> None:
        self.pipeline = pipeline
        self.transport = transport
        self.round_detector = round_detector or (lambda _event: False)
        self.address_detector = address_detector or (lambda _event: False)
        self.message_debounce_seconds = message_debounce_seconds
        self._running = False
        self._extraction_tasks: set[asyncio.Task[None]] = set()

    async def start(self) -> None:
        self._running = True
        try:
            async for event in self.transport.listen():
                if not self._running:
                    break
                await self.process_event(event)
        finally:
            self._running = False

    async def shutdown(self) -> None:
        self._running = False
        tasks = list(self._extraction_tasks)
        for task in tasks:
            if not task.done():
                task.cancel()
        for task in tasks:
            with contextlib.suppress(asyncio.CancelledError):
                await task
        self._extraction_tasks.clear()

        close = getattr(self.transport, "close", None)
        if close is None:
            close = getattr(self.transport, "aclose", None)
        if close is not None:
            await _maybe_await(close())

    async def process_event(self, event: InboundEvent) -> str:
        event_id = await self.pipeline.store_event(event)
        if event.sender_faction == "operator":
            await self.pipeline.dispatch_operator(event.content, event_id)
            return event_id

        self._enqueue_message_extraction(event, event_id)
        if await self._check_round_boundary(event):
            return event_id
        if self.address_detector(event):
            await self.pipeline.run_response(trigger_event=event)
        return event_id

    def _enqueue_message_extraction(
        self, event: InboundEvent, event_id: str
    ) -> None:
        task = asyncio.create_task(self._debounced_message_extraction(event, event_id))
        self._extraction_tasks.add(task)
        task.add_done_callback(self._extraction_tasks.discard)

    async def _debounced_message_extraction(
        self, event: InboundEvent, event_id: str
    ) -> None:
        await asyncio.sleep(self.message_debounce_seconds)
        await self.pipeline.extract_from(event, event_id=event_id)

    async def _check_round_boundary(self, event: InboundEvent) -> bool:
        if not self.round_detector(event):
            return False
        await self.pipeline.reconcile_and_analyze()
        return True


def signal_round_detector(pattern: str) -> RoundDetector:
    compiled = re.compile(pattern)
    return lambda event: bool(compiled.search(event.content))


def faction_address_detector(faction_id: str) -> AddressDetector:
    normalized = faction_id.lower()
    return (
        lambda event: event.channel == "public"
        and normalized in event.content.lower()
    )


async def _maybe_await(value: Any) -> Any:
    if isawaitable(value):
        return await value
    return value


__all__ = [
    "AddressDetector",
    "EventDrivenFlow",
    "RoundDetector",
    "faction_address_detector",
    "signal_round_detector",
]
