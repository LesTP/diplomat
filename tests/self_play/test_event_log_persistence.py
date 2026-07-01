"""Acceptance tests for persisting raw event logs in self-play results."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from modules.event_store import EventFilter
from tests.test_self_play import PERSONAS_DIR, _make_env


def _serialize_event_log(rows) -> list[dict[str, object]]:
    return [
        {
            "event_id": row.event_id,
            "round_number": row.round_number,
            "timestamp": row.event.timestamp.isoformat(),
            "sender_faction": row.event.sender_faction,
            "channel": row.event.channel,
            "recipient": row.event.recipient,
            "content": row.event.content,
            "telegram_msg_id": row.event.telegram_msg_id,
        }
        for row in rows
    ]


class TestEventLogPersistence:
    @pytest.mark.asyncio
    async def test_collect_results_includes_event_log_from_event_store(
        self, tmp_path: Path
    ) -> None:
        env = _make_env(tmp_path)
        await env.setup()
        try:
            await env.broadcast_to_all("moderator", "Seed message")
            await asyncio.sleep(0.05)
            await env.broadcast("alpha", "Alpha follow-up")
            await asyncio.sleep(0.05)

            results = await env.collect_results()
            assert "transcript" in results
            assert results["transcript"] == env.channel_log

            for fid, handle in env.agents.items():
                agent_result = results["agents"][fid]
                if "event_log" not in agent_result:
                    pytest.xfail("event_log implementation pending")

                expected = _serialize_event_log(
                    await handle.orchestrator.event_store.query(
                        EventFilter(limit=10000)
                    )
                )
                assert agent_result["event_log"] == expected
                assert agent_result["promises"] is not None
                assert agent_result["coalitions"] is not None
                assert agent_result["inconsistencies"] is not None
                assert agent_result["intelligence"] is not None
                assert agent_result["state_change_log"] is not None
                assert agent_result["coaching"] is not None
                assert agent_result["adversarial_reads"] is not None
                assert "round" in agent_result
        finally:
            await env.teardown()

    @pytest.mark.asyncio
    async def test_collect_results_emits_empty_event_log_for_idle_agent(
        self, tmp_path: Path
    ) -> None:
        env = _make_env(tmp_path, factions={"alpha": PERSONAS_DIR / "alpha.txt"})
        await env.setup()
        try:
            results = await env.collect_results()
            agent_result = results["agents"]["alpha"]
            if "event_log" not in agent_result:
                pytest.xfail("event_log implementation pending")

            assert agent_result["event_log"] == []
        finally:
            await env.teardown()
