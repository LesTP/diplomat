from __future__ import annotations


async def test_pipeline_fixture_starts(pipeline):
    assert pipeline.orchestrator._running is True
    assert pipeline.transport.closed is False
    assert pipeline.orchestrator.db_path.exists()
