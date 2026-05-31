from __future__ import annotations

import asyncio
from typing import Any

from pipeline import Pipeline


class RoundSteppedFlow:
    def __init__(
        self,
        *,
        pipelines: list[Pipeline],
        moderator: Any,
        total_rounds: int,
    ) -> None:
        self.pipelines = list(pipelines)
        self.moderator = moderator
        self.total_rounds = total_rounds
        self.round_update_settle_seconds = 0.5
        self.response_settle_seconds = 0.05
        self.message_settle_seconds = 2.0
        self.round_end_settle_seconds = 1.0

    async def run_round(self, round_number: int) -> dict[str, str]:
        self._print_round_header(round_number)
        for pipeline in self.pipelines:
            pipeline.advance_to_round(round_number)

        update = self._round_update(round_number)
        if update:
            print(f"\n[MODERATOR] {update[:120]}...")
            await self.moderator.broadcast_to_all("moderator", update)
            await asyncio.sleep(self.round_update_settle_seconds)

        round_responses: dict[str, str] = {}
        for pipeline in self.pipelines:
            faction_id = self._faction_id(pipeline)
            logging_client = getattr(self.moderator, "logging_client", None)
            if logging_client:
                logging_client.set_faction(faction_id)
            try:
                await pipeline.run_response()
            except Exception as exc:
                print(f"  [{faction_id}] response pipeline error: {exc}")
                continue

            await asyncio.sleep(self.response_settle_seconds)
            transport = self._transport(pipeline)
            outputs = await transport.get_output()
            public = [message for message in outputs if message.channel == "public"]
            if public:
                response_text = public[-1].content
                round_responses[faction_id] = response_text
                truncated = (
                    response_text[:200] + "..."
                    if len(response_text) > 200
                    else response_text
                )
                print(f"\n  [{faction_id.upper()}] {truncated}")

        for faction_id, response in round_responses.items():
            await self.moderator.broadcast(faction_id, response)

        await asyncio.sleep(self.message_settle_seconds)
        self._record_round_end()
        for pipeline in self.pipelines:
            await pipeline.reconcile_and_analyze()
        await asyncio.sleep(self.round_end_settle_seconds)
        return round_responses

    def _round_update(self, round_number: int) -> str | None:
        updates = getattr(self.moderator, "round_updates", {})
        return updates.get(round_number)

    def _record_round_end(self) -> None:
        recorder = getattr(self.moderator, "record_channel_message", None)
        if recorder is not None:
            recorder("moderator", "[ROUND END]", channel="public")

    @staticmethod
    def _faction_id(pipeline: Pipeline) -> str:
        return str(pipeline.orchestrator.faction_id)

    @staticmethod
    def _transport(pipeline: Pipeline) -> Any:
        return pipeline.orchestrator.transport

    @staticmethod
    def _print_round_header(round_number: int) -> None:
        print(f"\n{'='*60}")
        print(f"  ROUND {round_number}")
        print(f"{'='*60}")


__all__ = ["RoundSteppedFlow"]
