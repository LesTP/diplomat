"""Tests for state reconciliation module."""

from __future__ import annotations

import asyncio
import json

import pytest

from modules.reconciliation import (
    ReconciliationResult,
    StateReconciler,
    state_patch_entity_types,
)


class FakeLLMClient:
    def __init__(self, response: str) -> None:
        self.response = response
        self.calls: list[dict] = []

    def complete(self, **kwargs):
        self.calls.append(kwargs)
        return self.response


class TestReconciliationResult:
    def test_success_result(self) -> None:
        r = ReconciliationResult(success=True, merge_log=["merged A and B"])
        assert r.success
        assert r.error is None
        assert r.merge_log == ["merged A and B"]

    def test_failure_result(self) -> None:
        r = ReconciliationResult(success=False, error="LLM failed")
        assert not r.success
        assert r.error == "LLM failed"


class TestStateReconciler:
    @pytest.mark.asyncio
    async def test_reconcile_returns_structured_result(self) -> None:
        response = json.dumps({
            "merged_promises": [
                {"keep_id": "p1", "remove_ids": ["p2", "p3"], "reason": "same $2M commitment"}
            ],
            "status_updates": [
                {"promise_id": "p4", "new_status": "kept", "resolution": "delivered as promised"}
            ],
            "new_inconsistencies": [
                {"faction_id": "beta", "description": "shifted from 20M to 15M gallons", "leverage_value": 0.7}
            ],
            "missed_proposals": [
                {"promise_id": "p5", "from_faction": "alpha", "to_faction": "beta", "content": "offer pipeline rights", "status": "pending"}
            ],
            "merge_log": ["Merged p2, p3 into p1 (same $2M commitment)"],
        })

        client = FakeLLMClient(response)
        reconciler = StateReconciler(client, {"provider": "fake"}, tier="commodity")

        result = await reconciler.reconcile(
            current_state={"promises": [], "coalitions": [], "inconsistencies": []},
            recent_events=[],
            round_number=2,
        )

        assert result.success
        assert len(result.merged_promises) == 1
        assert result.merged_promises[0]["keep_id"] == "p1"
        assert result.merged_promises[0]["remove_ids"] == ["p2", "p3"]
        assert len(result.updated_statuses) == 1
        assert result.updated_statuses[0]["new_status"] == "kept"
        assert len(result.new_inconsistencies) == 1
        assert result.new_inconsistencies[0]["faction_id"] == "beta"
        assert len(result.missed_proposals) == 1
        assert result.missed_proposals[0]["from_faction"] == "alpha"
        assert result.merge_log == ["Merged p2, p3 into p1 (same $2M commitment)"]

    @pytest.mark.asyncio
    async def test_reconcile_empty_state_returns_empty(self) -> None:
        response = json.dumps({
            "merged_promises": [],
            "status_updates": [],
            "new_inconsistencies": [],
            "missed_proposals": [],
            "merge_log": [],
        })

        client = FakeLLMClient(response)
        reconciler = StateReconciler(client, {}, tier="commodity")

        result = await reconciler.reconcile(
            current_state={"promises": [], "coalitions": [], "inconsistencies": []},
            recent_events=[],
            round_number=1,
        )

        assert result.success
        assert result.merged_promises == []
        assert result.updated_statuses == []

    @pytest.mark.asyncio
    async def test_reconcile_formats_transcript(self) -> None:
        from modules.types import InboundEvent
        from datetime import datetime, timezone

        events = [
            InboundEvent(
                timestamp=datetime.now(timezone.utc),
                sender_faction="alpha",
                channel="public",
                content="I commit to releasing 15M gallons.",
            ),
        ]

        response = json.dumps({
            "merged_promises": [],
            "status_updates": [],
            "new_inconsistencies": [],
            "missed_proposals": [],
            "merge_log": [],
        })

        client = FakeLLMClient(response)
        reconciler = StateReconciler(client, {}, tier="commodity")

        await reconciler.reconcile(
            current_state={"promises": [], "coalitions": [], "inconsistencies": []},
            recent_events=events,
            round_number=1,
        )

        # Check that the transcript was formatted in the prompt
        user_prompt = client.calls[0]["messages"][1]["content"]
        assert "[alpha] I commit to releasing 15M gallons." in user_prompt

    @pytest.mark.asyncio
    async def test_reconcile_uses_entity_types_from_schema(self, tmp_path) -> None:
        schema_path = tmp_path / "state_patch.json"
        schema_path.write_text(
            json.dumps(
                {
                    "type": "object",
                    "properties": {
                        "promises": {"type": "array"},
                        "treaties": {"type": "array"},
                    },
                }
            ),
            encoding="utf-8",
        )
        response = json.dumps({
            "merged_promises": [],
            "status_updates": [],
            "new_inconsistencies": [],
            "missed_proposals": [],
            "merge_log": [],
        })
        client = FakeLLMClient(response)
        reconciler = StateReconciler(
            client,
            {},
            tier="commodity",
            state_patch_schema_path=schema_path,
        )

        await reconciler.reconcile(
            current_state={"promises": [], "treaties": [{"treaty_id": "t1"}]},
            recent_events=[],
            round_number=1,
        )

        assert state_patch_entity_types(schema_path) == ["promises", "treaties"]
        system_prompt = client.calls[0]["messages"][0]["content"]
        user_prompt = client.calls[0]["messages"][1]["content"]
        assert "(promises, treaties)" in system_prompt
        assert "Current tracked treaties:" in user_prompt

    @pytest.mark.asyncio
    async def test_reconcile_failure_returns_error(self) -> None:
        client = FakeLLMClient("not valid json")
        reconciler = StateReconciler(client, {}, tier="commodity")

        result = await reconciler.reconcile(
            current_state={"promises": []},
            recent_events=[],
            round_number=1,
        )

        assert not result.success
        assert result.error is not None
