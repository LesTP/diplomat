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
from logging_config import get_logger


RoundDetector = Callable[[InboundEvent], bool]
AddressDetector = Callable[[InboundEvent], bool]
logger = get_logger(__name__)


class EventDrivenFlow:
    def __init__(
        self,
        *,
        pipeline: Pipeline,
        transport: Transport,
        round_detector: RoundDetector | None = None,
        address_detector: AddressDetector | None = None,
        message_debounce_seconds: float = 0.5,
        round_interval_seconds: float | None = None,
    ) -> None:
        self.pipeline = pipeline
        self.transport = transport
        self.round_detector = round_detector or (lambda _event: False)
        self.address_detector = address_detector or (lambda _event: False)
        self.message_debounce_seconds = message_debounce_seconds
        self.round_interval_seconds = round_interval_seconds
        self._running = False
        self._extraction_tasks: set[asyncio.Task[None]] = set()
        self._round_timer_task: asyncio.Task[None] | None = None

    def __getattr__(self, name: str) -> Any:
        return getattr(self.pipeline.orchestrator, name)

    def __setattr__(self, name: str, value: Any) -> None:
        flow_attrs = {
            "pipeline",
            "transport",
            "round_detector",
            "address_detector",
            "message_debounce_seconds",
            "round_interval_seconds",
            "_running",
            "_extraction_tasks",
            "_round_timer_task",
        }
        if name in flow_attrs or "pipeline" not in self.__dict__:
            object.__setattr__(self, name, value)
            return
        setattr(self.pipeline.orchestrator, name, value)

    async def start(self) -> None:
        self._running = True
        self._print_online_banner()
        if self.round_interval_seconds is not None:
            self._round_timer_task = asyncio.create_task(self._time_round_loop())
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
        if self._round_timer_task is not None and not self._round_timer_task.done():
            self._round_timer_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._round_timer_task

        close = getattr(self.transport, "close", None)
        if close is None:
            close = getattr(self.transport, "aclose", None)
        if close is not None:
            await _maybe_await(close())

    async def process_event(self, event: InboundEvent) -> str:
        event_id = await self.pipeline.store_event(event)
        if event.sender_faction == "operator":
            logger.info(
                "event.routed event_id=%s route=operator channel=%s",
                event_id,
                event.channel,
            )
            await self.pipeline.dispatch_operator(event.content, event_id)
            return event_id

        self._enqueue_message_extraction(event, event_id)
        route = (
            "system"
            if event.sender_faction == "system"
            else "faction_extraction"
        )
        logger.info(
            "event.routed event_id=%s route=%s sender_faction=%s channel=%s",
            event_id,
            route,
            event.sender_faction,
            event.channel,
        )
        if await self._check_round_boundary(event, event_id):
            return event_id
        if self.address_detector(event):
            logger.info(
                "pipeline.trigger event_id=%s trigger=direct_address sender_faction=%s",
                event_id,
                event.sender_faction,
            )
            asyncio.create_task(self.pipeline.run_response(trigger_event=event))
            logger.info(
                "pipeline.complete event_id=%s success=scheduled trigger=direct_address",
                event_id,
            )
        return event_id

    def _enqueue_message_extraction(
        self, event: InboundEvent, event_id: str
    ) -> None:
        task = asyncio.create_task(self._debounced_message_extraction(event, event_id))
        self._extraction_tasks.add(task)
        task.add_done_callback(self._extraction_tasks.discard)
        logger.info(
            "extraction.scheduled event_id=%s sender_faction=%s debounce_seconds=%.3f",
            event_id,
            event.sender_faction,
            self.message_debounce_seconds,
        )

    async def _debounced_message_extraction(
        self, event: InboundEvent, event_id: str
    ) -> None:
        await asyncio.sleep(self.message_debounce_seconds)
        await self.pipeline.extract_from(event, event_id=event_id)

    async def _check_round_boundary(self, event: InboundEvent, event_id: str) -> bool:
        if not self.round_detector(event):
            return False
        logger.info(
            "round.boundary event_id=%s detector=signal pattern=%s",
            event_id,
            getattr(self.round_detector, "pattern", "unknown"),
        )
        await self.pipeline.reconcile_and_analyze()
        return True

    async def _time_round_loop(self) -> None:
        if self.round_interval_seconds is None:
            return
        while self._running:
            await asyncio.sleep(self.round_interval_seconds)
            await self.pipeline.reconcile_and_analyze()

    def _print_online_banner(self) -> None:
        orchestrator = getattr(self.pipeline, "orchestrator", None)
        if orchestrator is None:
            return
        session_budget = float(
            orchestrator.cost_config.get("session_budget_usd", 0.0)
        )
        logger.info(
            "startup.online DIPLOMAT ONLINE - Round %s - %s - session budget $%.2f",
            orchestrator.current_round,
            orchestrator.faction_id,
            session_budget,
        )


def signal_round_detector(pattern: str) -> RoundDetector:
    compiled = re.compile(pattern)
    def detect(event: InboundEvent) -> bool:
        return bool(compiled.search(event.content))

    setattr(detect, "pattern", pattern)
    return detect


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
