"""Tests for the scenario compiler (deterministic parts only — no LLM calls)."""

from __future__ import annotations

from pathlib import Path

from tools.scenario_compiler import (
    SCENARIO_ANALYSIS_SCHEMA,
    generate_persona,
    save_analysis,
    save_persona,
)


_SAMPLE_ANALYSIS = {
    "factions": ["alpha", "beta", "gamma"],
    "issues": [
        {"name": "Tariffs", "outcomes": ["Strict", "Moderate", "Relaxed"], "description": "Trade barriers"},
        {"name": "Labor", "outcomes": ["Strict", "Moderate", "Relaxed"], "description": "Worker protections"},
        {"name": "Environment", "outcomes": ["Strict", "Moderate", "Relaxed"], "description": "Emissions rules"},
    ],
    "scoring": {
        "alpha": {"Tariffs": {"Strict": 8, "Moderate": 5, "Relaxed": 1}, "Labor": {"Strict": 1, "Moderate": 3, "Relaxed": 5}, "Environment": {"Strict": 3, "Moderate": 5, "Relaxed": 4}},
        "beta": {"Tariffs": {"Strict": 2, "Moderate": 4, "Relaxed": 6}, "Labor": {"Strict": 8, "Moderate": 5, "Relaxed": 1}, "Environment": {"Strict": 4, "Moderate": 5, "Relaxed": 3}},
        "gamma": {"Tariffs": {"Strict": 3, "Moderate": 5, "Relaxed": 6}, "Labor": {"Strict": 4, "Moderate": 5, "Relaxed": 3}, "Environment": {"Strict": 8, "Moderate": 5, "Relaxed": 1}},
    },
    "batna": {"alpha": 6, "beta": 6, "gamma": 6},
    "deception_tactics": {
        "alpha": "Overstate interest in Environment to create a tradeable concession",
        "beta": "Claim Tariffs are critical, then concede for Labor gains",
        "gamma": "Pretend Labor is essential, trade it for Environment",
    },
    "logrolling": [
        "Alpha gets Strict Tariffs, Beta gets Strict Labor — both benefit",
        "Gamma gets Strict Environment, concedes on Tariffs to Alpha",
    ],
}


class TestGeneratePersona:
    def test_includes_scoring_table(self) -> None:
        persona = generate_persona("alpha", _SAMPLE_ANALYSIS)
        assert "Tariffs:" in persona
        assert "Strict=8pts" in persona
        assert "Relaxed=1pt" in persona

    def test_identifies_true_priority(self) -> None:
        persona = generate_persona("alpha", _SAMPLE_ANALYSIS)
        assert "Tariffs" in persona
        assert "8pts" in persona

    def test_includes_batna(self) -> None:
        persona = generate_persona("alpha", _SAMPLE_ANALYSIS)
        assert "BATNA" in persona
        assert "6 points" in persona

    def test_includes_deception_tactic(self) -> None:
        persona = generate_persona("alpha", _SAMPLE_ANALYSIS)
        assert "DECEPTION TACTIC" in persona
        assert "Environment" in persona

    def test_includes_round_context_marker(self) -> None:
        persona = generate_persona("beta", _SAMPLE_ANALYSIS)
        assert "## CURRENT ROUND CONTEXT" in persona

    def test_faction_name_capitalized(self) -> None:
        persona = generate_persona("gamma", _SAMPLE_ANALYSIS)
        assert "You are Gamma" in persona

    def test_calculates_best_deal(self) -> None:
        # Alpha best: Tariffs=8, Labor=5, Environment=5 = 18
        persona = generate_persona("alpha", _SAMPLE_ANALYSIS)
        assert "18 points" in persona

    def test_each_faction_has_different_priority(self) -> None:
        alpha = generate_persona("alpha", _SAMPLE_ANALYSIS)
        beta = generate_persona("beta", _SAMPLE_ANALYSIS)
        gamma = generate_persona("gamma", _SAMPLE_ANALYSIS)
        assert "Tariffs" in alpha and "8pts" in alpha
        assert "Labor" in beta and "8pts" in beta
        assert "Environment" in gamma and "8pts" in gamma


class TestSaveFiles:
    def test_save_analysis_writes_json(self, tmp_path: Path) -> None:
        path = save_analysis(_SAMPLE_ANALYSIS, tmp_path)
        assert path.is_file()
        import json
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["factions"] == ["alpha", "beta", "gamma"]

    def test_save_persona_writes_txt(self, tmp_path: Path) -> None:
        persona_text = generate_persona("alpha", _SAMPLE_ANALYSIS)
        path = save_persona("alpha", persona_text, tmp_path)
        assert path.is_file()
        assert path.suffix == ".txt"
        assert "You are Alpha" in path.read_text(encoding="utf-8")


class TestSchema:
    def test_schema_has_required_keys(self) -> None:
        assert "factions" in SCENARIO_ANALYSIS_SCHEMA["properties"]
        assert "issues" in SCENARIO_ANALYSIS_SCHEMA["properties"]
        assert "scoring" in SCENARIO_ANALYSIS_SCHEMA["properties"]
        assert "batna" in SCENARIO_ANALYSIS_SCHEMA["properties"]
        assert "deception_tactics" in SCENARIO_ANALYSIS_SCHEMA["properties"]
        assert "logrolling" in SCENARIO_ANALYSIS_SCHEMA["properties"]
