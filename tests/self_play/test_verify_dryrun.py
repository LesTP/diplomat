"""Regression test: verify_dryrun must accept bare-prompt live results.

Bare mode strips the full-mode scaffolding (per-round markers, adversarial /
analyst / extraction calls), so the round/marker/ADV invariants don't apply.
verify_dryrun detects `bare_mode` and checks the applicable subset instead
(GEN count per faction, transcript, SCORE, provider routing).
"""
from __future__ import annotations

import sys
from pathlib import Path

import tests.self_play.verify_dryrun as vd

_BARE_RESULT = (
    Path(__file__).parent / "results" / "run17_bare_deepseekchat_succ3b_1.json"
)


def test_verify_dryrun_accepts_bare_result(monkeypatch) -> None:
    assert _BARE_RESULT.exists(), f"missing committed bare result: {_BARE_RESULT}"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "verify_dryrun",
            "--results",
            str(_BARE_RESULT),
            "--num-factions",
            "3",
            "--rounds",
            "4",
            "--expect-providers",
            '{"alpha":"openrouter","beta":"openrouter","gamma":"openrouter"}',
        ],
    )
    assert vd.main() == 0
