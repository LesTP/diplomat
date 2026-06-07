from __future__ import annotations

import argparse
import importlib.util
from datetime import datetime, timezone
from pathlib import Path

import pytest

from modules.edit_classifier import EditClassification
from modules.review_gate import ReviewDecision
from modules.state_manager import SQLiteStateManager


def _load_tool() -> object:
    path = Path("tools/classify_edit_log.py").resolve()
    spec = importlib.util.spec_from_file_location("classify_edit_log", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


classify_edit_log = _load_tool()


class FakeClassifier:
    def __init__(self, category: str = "tone_harder") -> None:
        self.category = category
        self.calls: list[tuple[str, str, str | None]] = []

    async def classify(
        self, original: str, edited: str, edit_notes: str | None
    ) -> EditClassification:
        self.calls.append((original, edited, edit_notes))
        return EditClassification(
            category=self.category,
            confidence=0.87,
            rationale="Fixture classification.",
            classifier_model="fake-model",
            classified_at=datetime(2026, 6, 7, tzinfo=timezone.utc),
        )


def _manager(tmp_path) -> SQLiteStateManager:
    return SQLiteStateManager(tmp_path / "game.db", "config/schemas/state_patch.json")


def _args(db_path, *, force: bool = False) -> argparse.Namespace:
    return argparse.Namespace(
        db=str(db_path),
        game_id=None,
        force=force,
        config="config/pipeline.yaml",
        tier="commodity",
        provider=None,
        model=None,
    )


@pytest.mark.asyncio
async def test_classify_edit_log_skips_existing_rows_and_prints_summary(
    tmp_path, monkeypatch, capsys
):
    sm = _manager(tmp_path)

    await sm.log_review_decision(
        round_number=1,
        decision=ReviewDecision(
            action="edited",
            final_text="We can push back on the proposal.",
            edit_notes="We can push back on the proposal.",
        ),
        draft_text="We will crush the proposal.",
        revise_directives=["soften tone"],
    )
    await sm.log_review_decision(
        round_number=2,
        decision=ReviewDecision(
            action="edited",
            final_text="We will support the coalition.",
            edit_notes="We will support the coalition.",
        ),
        draft_text="We might support the coalition.",
        revise_directives=None,
    )
    await sm.log_review_decision(
        round_number=3,
        decision=ReviewDecision(action="approved", final_text="Keep this.", edit_notes=None),
        draft_text="Keep this.",
        revise_directives=None,
    )

    review_rows = await sm.query("review_gate_edits", {})
    await sm.store_edit_classification(
        review_rows[0]["id"],
        EditClassification(
            category="tone_softer",
            confidence=0.93,
            rationale="Existing classification.",
            classifier_model="gemini-2.5-flash-lite",
            classified_at=datetime(2026, 6, 7, tzinfo=timezone.utc),
        ),
    )

    fake_classifier = FakeClassifier(category="commitment_removed")
    monkeypatch.setattr(
        classify_edit_log,
        "_load_pipeline_config",
        lambda _path: {
            "llm_providers": {
                "primary": {
                    "provider": "openai",
                    "models": {"commodity": "gpt-4.1-mini"},
                    "api_key_env": "OPENAI_API_KEY",
                }
            }
        },
    )
    monkeypatch.setattr(
        classify_edit_log,
        "_build_classifier",
        lambda _config, _args: fake_classifier,
    )

    await classify_edit_log._run(_args(tmp_path / "game.db"))
    first_output = capsys.readouterr().out

    rows = await sm.query("edit_classifications", {})
    assert len(rows) == 2
    assert len(fake_classifier.calls) == 1
    assert "| category | count | most_recent_example_id |" in first_output
    assert "| commitment_removed | 1 |" in first_output
    assert "| tone_softer | 1 |" in first_output

    await classify_edit_log._run(_args(tmp_path / "game.db"))
    second_output = capsys.readouterr().out

    rows_after_second_run = await sm.query("edit_classifications", {})
    assert len(rows_after_second_run) == 2
    assert len(fake_classifier.calls) == 1
    assert "| category | count | most_recent_example_id |" in second_output


@pytest.mark.asyncio
async def test_classify_edit_log_force_reclassifies_rows(tmp_path, monkeypatch):
    sm = _manager(tmp_path)

    await sm.log_review_decision(
        round_number=4,
        decision=ReviewDecision(
            action="edited",
            final_text="We can soften this.",
            edit_notes="We can soften this.",
        ),
        draft_text="We will crush this.",
        revise_directives=None,
    )

    fake_classifier = FakeClassifier(category="tone_softer")
    monkeypatch.setattr(
        classify_edit_log,
        "_load_pipeline_config",
        lambda _path: {
            "llm_providers": {
                "primary": {
                    "provider": "google",
                    "models": {"commodity": "gemini-2.5-flash-lite"},
                    "api_key_env": "GOOGLE_API_KEY",
                }
            }
        },
    )
    monkeypatch.setattr(
        classify_edit_log,
        "_build_classifier",
        lambda _config, _args: fake_classifier,
    )

    await classify_edit_log._run(_args(tmp_path / "game.db"))
    await classify_edit_log._run(_args(tmp_path / "game.db", force=True))

    rows = await sm.query("edit_classifications", {})
    assert len(rows) == 2
    assert len(fake_classifier.calls) == 2
