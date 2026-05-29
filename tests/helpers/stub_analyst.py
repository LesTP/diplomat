from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from modules.types import AnalysisResult


class StubAnalyst:
    def __init__(
        self,
        fixture_path: str | Path,
        *,
        provider_id: str = "stub",
        timestamp: datetime | None = None,
    ) -> None:
        self.fixture_path = Path(fixture_path)
        self.provider_id = provider_id
        self.timestamp = timestamp or datetime(2026, 5, 27, tzinfo=timezone.utc)
        self.calls: list[dict[str, Any]] = []

    async def analyze(self, state: dict[str, Any], **kwargs) -> AnalysisResult:
        self.calls.append(state)
        return AnalysisResult(
            success=True,
            provider_id=self.provider_id,
            report=json.loads(self.fixture_path.read_text(encoding="utf-8")),
            error=None,
            timestamp=self.timestamp,
        )

