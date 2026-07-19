from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

import pytest


def _load_tool() -> object:
    path = Path("tools/classify_mechanisms.py").resolve()
    spec = importlib.util.spec_from_file_location("classify_mechanisms", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


classify_mechanisms = _load_tool()


class FakeClassifier:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def classify(self, result: dict) -> str:
        self.calls.append(result)
        return "breakdown"


def _args(results_dir: Path, *, dry_run: bool = False) -> argparse.Namespace:
    return argparse.Namespace(
        input_dir=str(results_dir),
        output=None,
        dry_run=dry_run,
        config="config/pipeline.yaml",
        tier="commodity",
        provider=None,
        model=None,
    )


def _result(rounds: int = 1) -> dict:
    return {
        "transcript": [{"round": 1, "faction": "alpha", "text": "I propose a deal."}],
        "round_responses": {str(rounds): {"alpha": "final position"}},
        "rounds_completed": rounds,
        "scores": {
            "deal_reached": False,
            "agreed_outcomes": {},
            "no_deal_reason": "no agreement",
        },
    }


@pytest.mark.asyncio
async def test_classify_mechanisms_processes_valid_json_and_skips_invalid(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    (tmp_path / "a.json").write_text(json.dumps(_result()), encoding="utf-8")
    (tmp_path / "b.json").write_text(json.dumps(_result()), encoding="utf-8")
    (tmp_path / "bad.json").write_text("{", encoding="utf-8")
    (tmp_path / "note.txt").write_text("ignored", encoding="utf-8")

    fake = FakeClassifier()
    monkeypatch.setattr(classify_mechanisms, "_build_classifier", lambda *_a, **_kw: fake)

    await classify_mechanisms._run(_args(tmp_path))
    output = capsys.readouterr().out

    assert len(fake.calls) == 2
    assert "| file | label | q1 | q2 | q3 | q4 | q5 |" in output
    assert "Summary: breakdown: 2" in output


@pytest.mark.asyncio
async def test_classify_mechanisms_dry_run_uses_fake_client(tmp_path: Path, capsys) -> None:
    (tmp_path / "a.json").write_text(json.dumps(_result()), encoding="utf-8")

    await classify_mechanisms._run(_args(tmp_path, dry_run=True))
    output = capsys.readouterr().out

    assert "breakdown" in output.lower()
    assert "q1" in output
