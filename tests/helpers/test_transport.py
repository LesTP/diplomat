from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

from modules.transport import OutboundMessage
from modules.types import InboundEvent


class TestTransport:
    __test__ = False

    def __init__(self) -> None:
        self._input: asyncio.Queue[InboundEvent | None] = asyncio.Queue()
        self._output: asyncio.Queue[OutboundMessage] = asyncio.Queue()
        self.closed = False

    async def inject(self, event: InboundEvent) -> None:
        if self.closed:
            raise RuntimeError("Cannot inject into a closed TestTransport")
        await self._input.put(event)

    async def send(self, message: OutboundMessage) -> None:
        await self._output.put(message)

    async def listen(self) -> AsyncIterator[InboundEvent]:
        while True:
            event = await self._input.get()
            if event is None:
                return
            yield event

    async def get_output(self) -> list[OutboundMessage]:
        messages: list[OutboundMessage] = []
        while True:
            try:
                messages.append(self._output.get_nowait())
            except asyncio.QueueEmpty:
                return messages

    async def clear_output(self) -> None:
        await self.get_output()

    async def close(self) -> None:
        if self.closed:
            return
        self.closed = True
        await self._input.put(None)

