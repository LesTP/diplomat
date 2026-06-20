"""Tests for the scenario compiler (deterministic parts only — no LLM calls)."""

from __future__ import annotations

from pathlib import Path

from scenario_authoring.scenario_compiler import (
    DEFAULT_BATNA_FRACTION,
    SCENARIO_ANALYSIS_SCHEMA,
    build_compiler_system_prompt,
    force_batna_targets,
    generate_persona,
    max_possible_score,
    parse_batna_fractions_json,
    save_analysis,
    save_persona,
    validate_batna_pressure,
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
    "priority_collision": "soft",
    "pressure_profile": {"time_pressure": "medium", "external_shock": "low"},
    "deception_tactics": {
        "alpha": "Overstate interest in Environment to create a tradeable concession",
        "beta": "Claim Tariffs are critical, then concede for Labor gains",
        "gamma": "Pretend Labor is essential, trade it for Environment",
    },
    "logrolling": [
        "Alpha gets Strict Tariffs, Beta gets Strict Labor — both benefit",
        "Gamma gets Strict Environment, concedes on Tariffs to Alpha",
    ],
    "pressure": {
        "round_cost_decay": 1.5,
        "asymmetric_clocks": {"alpha": 4, "beta": 2, "gamma": 3},
        "penalty_floor_offset": 2.0,
    },
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

    def test_includes_pressure_summary_and_deadlines(self) -> None:
        persona = generate_persona("alpha", _SAMPLE_ANALYSIS)
        assert "### Pressure" in persona
        assert "Round cost decay: 1.5 points per round" in persona
        assert "Penalty floor offset: 2 points" in persona
        assert "### Opponent Deadlines" in persona
        assert "- beta: round 2" in persona
        assert "- gamma: round 3" in persona

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
        assert "pressure" in SCENARIO_ANALYSIS_SCHEMA["properties"]
        assert "pressure_profile" in SCENARIO_ANALYSIS_SCHEMA["properties"]
        assert "pressure" in SCENARIO_ANALYSIS_SCHEMA["required"]
        pressure = SCENARIO_ANALYSIS_SCHEMA["properties"]["pressure"]
        assert pressure["required"] == [
            "round_cost_decay",
            "asymmetric_clocks",
            "penalty_floor_offset",
        ]
        pressure_profile = SCENARIO_ANALYSIS_SCHEMA["properties"]["pressure_profile"]
        assert pressure_profile["required"] == [
            "time_pressure",
            "external_shock",
        ]

    def test_schema_has_optional_coalition_values(self) -> None:
        # Coalition values are scenario-property, not universal; field is optional.
        properties = SCENARIO_ANALYSIS_SCHEMA["properties"]
        assert "coalition_values" in properties
        assert "coalition_values" not in SCENARIO_ANALYSIS_SCHEMA["required"]
        cv = properties["coalition_values"]
        assert cv["type"] == "array"
        item = cv["items"]
        assert item["required"] == ["members", "values"]
        assert item["properties"]["members"]["items"]["type"] == "string"
        assert item["properties"]["values"]["additionalProperties"]["type"] == "number"


class TestBuildCompilerSystemPrompt:
    def test_default_fraction_renders_as_percent(self) -> None:
        prompt = build_compiler_system_prompt()
        # Default 0.50 -> 50%
        assert "50%" in prompt
        # Old hardcoded range must be gone
        assert "4-8 total" not in prompt

    def test_custom_fraction_overrides_percent(self) -> None:
        prompt = build_compiler_system_prompt(batna_fraction=0.65)
        assert "65%" in prompt
        assert "50%" not in prompt or prompt.count("65%") >= 1

    def test_lower_fraction(self) -> None:
        prompt = build_compiler_system_prompt(batna_fraction=0.30)
        assert "30%" in prompt

    def test_per_faction_fractions_render_as_overrides(self) -> None:
        prompt = build_compiler_system_prompt(
            batna_fraction=0.50,
            batna_fractions={"alpha": 0.65, "beta": 0.35},
        )
        assert "Faction-specific BATNA targets override" in prompt
        assert "alpha: 65%" in prompt
        assert "beta: 35%" in prompt

    def test_invalid_fraction_zero_raises(self) -> None:
        import pytest
        with pytest.raises(ValueError):
            build_compiler_system_prompt(batna_fraction=0.0)

    def test_invalid_fraction_one_raises(self) -> None:
        import pytest
        with pytest.raises(ValueError):
            build_compiler_system_prompt(batna_fraction=1.0)

    def test_invalid_fraction_negative_raises(self) -> None:
        import pytest
        with pytest.raises(ValueError):
            build_compiler_system_prompt(batna_fraction=-0.1)


class TestParseArgs:
    def test_supports_fill_narrative_only_and_domain_context(self, monkeypatch: object) -> None:
        import sys
        from scenario_authoring.scenario_compiler import _parse_args

        monkeypatch.setattr(
            sys,
            "argv",
            [
                "scenario_compiler",
                "--fill-narrative-only",
                "analysis.json",
                "--domain-context-file",
                "context.txt",
                "--scenario-title",
                "Joint Space Mission",
            ],
        )

        args = _parse_args()
        assert args.fill_narrative_only == "analysis.json"
        assert args.domain_context_file == "context.txt"
        assert args.scenario_title == "Joint Space Mission"

    def test_title_alias_still_works(self, monkeypatch: object) -> None:
        import sys
        from scenario_authoring.scenario_compiler import _parse_args

        monkeypatch.setattr(
            sys,
            "argv",
            ["scenario_compiler", "--scenario", "scenario.md", "--title", "Legacy Title"],
        )

        args = _parse_args()
        assert args.scenario == "scenario.md"
        assert args.scenario_title == "Legacy Title"


class TestMaxPossibleScore:
    def test_sums_max_outcome_per_issue(self) -> None:
        # alpha: max(8,5,1) + max(1,3,5) + max(3,5,4) = 8 + 5 + 5 = 18
        assert max_possible_score(_SAMPLE_ANALYSIS, "alpha") == 18

    def test_beta_max(self) -> None:
        # beta: max(2,4,6) + max(8,5,1) + max(4,5,3) = 6 + 8 + 5 = 19
        assert max_possible_score(_SAMPLE_ANALYSIS, "beta") == 19

    def test_unknown_faction_returns_zero(self) -> None:
        assert max_possible_score(_SAMPLE_ANALYSIS, "nonexistent") == 0


class TestValidateBatnaPressure:
    def test_passes_when_batna_meets_target(self) -> None:
        # _SAMPLE_ANALYSIS has alpha BATNA=6, max=18 → 33%.
        # With target=0.30 (below tolerance), all should pass.
        warnings = validate_batna_pressure(
            _SAMPLE_ANALYSIS, target_fraction=0.30, tolerance=0.05
        )
        assert warnings == []

    def test_warns_when_batna_well_below_target(self) -> None:
        # alpha BATNA=6, max=18 = 33%. Target=0.60, tolerance=0.10 → floor=0.50.
        # 33% < 50% → warn for all three (all factions have BATNA=6, max ~18-19).
        warnings = validate_batna_pressure(
            _SAMPLE_ANALYSIS, target_fraction=0.60, tolerance=0.10
        )
        assert len(warnings) == 3
        for w in warnings:
            assert "BATNA" in w
            assert "target" in w
            # Hint about how to fix should be mentioned
            assert "--analysis-json" in w or "--batna-fraction" in w

    def test_warns_only_low_factions(self) -> None:
        analysis = {
            "factions": ["high", "low"],
            "issues": [{"name": "i1", "outcomes": ["o1", "o2"]}],
            "scoring": {
                "high": {"i1": {"o1": 10, "o2": 1}},
                "low": {"i1": {"o1": 10, "o2": 1}},
            },
            "batna": {"high": 7, "low": 2},
        }
        # max=10 for both. target=0.50 → floor=0.40.
        # high: 7/10=70% — pass; low: 2/10=20% — warn.
        warnings = validate_batna_pressure(analysis, target_fraction=0.50, tolerance=0.10)
        assert len(warnings) == 1
        assert warnings[0].startswith("low:")

    def test_per_faction_targets_override_scalar(self) -> None:
        # alpha: 6/18=33%, beta: 6/19=32%, gamma: 6/19=32%.
        # Only alpha has a high asymmetric target; beta/gamma use low scalar fallback.
        warnings = validate_batna_pressure(
            _SAMPLE_ANALYSIS,
            target_fraction=0.30,
            target_fractions={"alpha": 0.60},
            tolerance=0.10,
        )
        assert len(warnings) == 1
        assert warnings[0].startswith("alpha:")
        assert "--batna-fractions" in warnings[0]

    def test_default_fraction_matches_module_constant(self) -> None:
        # Smoke check that the validator and CLI default agree
        assert 0.0 < DEFAULT_BATNA_FRACTION < 1.0


class TestForceBatnaTargets:
    def test_sets_batnas_to_scalar_fraction_of_max(self) -> None:
        updated = force_batna_targets(_SAMPLE_ANALYSIS, target_fraction=0.50)
        assert updated["batna"] == {"alpha": 9, "beta": 10, "gamma": 10}
        assert _SAMPLE_ANALYSIS["batna"] == {"alpha": 6, "beta": 6, "gamma": 6}

    def test_per_faction_targets_override_scalar(self) -> None:
        updated = force_batna_targets(
            _SAMPLE_ANALYSIS,
            target_fraction=0.30,
            target_fractions={"alpha": 0.60, "beta": 0.40},
        )
        assert updated["batna"] == {"alpha": 11, "beta": 8, "gamma": 6}

    def test_forced_batnas_clear_validation(self) -> None:
        updated = force_batna_targets(
            _SAMPLE_ANALYSIS,
            target_fraction=0.30,
            target_fractions={"alpha": 0.60},
        )
        warnings = validate_batna_pressure(
            updated,
            target_fraction=0.30,
            target_fractions={"alpha": 0.60},
            tolerance=0.0,
        )
        assert warnings == []


class TestParseBatnaFractionsJson:
    def test_parses_numeric_map(self) -> None:
        assert parse_batna_fractions_json('{"alpha":0.65,"beta":0.35}') == {
            "alpha": 0.65,
            "beta": 0.35,
        }

    def test_rejects_non_object(self) -> None:
        import pytest
        with pytest.raises(ValueError, match="JSON object"):
            parse_batna_fractions_json("[0.5]")

    def test_rejects_out_of_range_fraction(self) -> None:
        import pytest
        with pytest.raises(ValueError, match="alpha"):
            parse_batna_fractions_json('{"alpha":1.0}')


# ---------------------------------------------------------------------------
# fill_narrative tests
# ---------------------------------------------------------------------------

def _make_result(success: bool, data: dict | None = None, error: str | None = None):
    class _R:
        pass
    r = _R()
    r.success = success
    r.data = data
    r.error = error
    return r


class TestBuildFillNarrativeUserPrompt:
    def test_includes_title_factions_issues(self) -> None:
        from scenario_authoring.scenario_compiler import build_fill_narrative_user_prompt
        prompt = build_fill_narrative_user_prompt(_SAMPLE_ANALYSIS, "Trade Deal")
        assert "Trade Deal" in prompt
        assert "alpha" in prompt
        assert "Tariffs" in prompt

    def test_includes_domain_context_when_provided(self) -> None:
        from scenario_authoring.scenario_compiler import build_fill_narrative_user_prompt
        prompt = build_fill_narrative_user_prompt(
            _SAMPLE_ANALYSIS, "Trade Deal", domain_context="Domain: Custom framing."
        )
        assert "Domain: Custom framing." in prompt

    def test_omits_domain_context_section_when_empty(self) -> None:
        from scenario_authoring.scenario_compiler import build_fill_narrative_user_prompt
        prompt = build_fill_narrative_user_prompt(_SAMPLE_ANALYSIS, "Trade Deal")
        assert "Domain:" not in prompt


class TestFillNarrative:
    def test_merges_logrolling_and_deception(self, monkeypatch: object) -> None:
        import asyncio
        from scenario_authoring.scenario_compiler import fill_narrative

        new_logrolling = ["Alpha trades Labor for Gamma's Environment support"]
        new_deception = {
            "alpha": "Anchor on Environment early",
            "beta": "Claim Tariffs are critical",
            "gamma": "Pretend Labor matters",
        }

        async def fake_sc(*args, **kwargs):
            return _make_result(True, {"logrolling": new_logrolling, "deception_tactics": new_deception})

        monkeypatch.setattr("toolkit.structured_llm.structured_call", fake_sc)

        result = asyncio.run(
            fill_narrative(_SAMPLE_ANALYSIS, "Test", llm_client=None, llm_config={})
        )
        assert result["logrolling"] == new_logrolling
        assert result["deception_tactics"] == new_deception

    def test_does_not_mutate_input(self, monkeypatch: object) -> None:
        import asyncio
        import copy
        from scenario_authoring.scenario_compiler import fill_narrative

        original = copy.deepcopy(_SAMPLE_ANALYSIS)

        async def fake_sc(*args, **kwargs):
            return _make_result(True, {"logrolling": ["new"], "deception_tactics": {"alpha": "x"}})

        monkeypatch.setattr("toolkit.structured_llm.structured_call", fake_sc)
        asyncio.run(fill_narrative(_SAMPLE_ANALYSIS, "T", llm_client=None, llm_config={}))
        assert _SAMPLE_ANALYSIS == original

    def test_preserves_scoring_batna_factions_issues(self, monkeypatch: object) -> None:
        import asyncio
        from scenario_authoring.scenario_compiler import fill_narrative

        async def fake_sc(*args, **kwargs):
            return _make_result(True, {"logrolling": [], "deception_tactics": {}})

        monkeypatch.setattr("toolkit.structured_llm.structured_call", fake_sc)

        result = asyncio.run(
            fill_narrative(_SAMPLE_ANALYSIS, "T", llm_client=None, llm_config={})
        )
        assert result["scoring"] == _SAMPLE_ANALYSIS["scoring"]
        assert result["batna"] == _SAMPLE_ANALYSIS["batna"]
        assert result["factions"] == _SAMPLE_ANALYSIS["factions"]
        assert result["issues"] == _SAMPLE_ANALYSIS["issues"]

    def test_raises_on_llm_failure(self, monkeypatch: object) -> None:
        import asyncio
        import pytest
        from scenario_authoring.scenario_compiler import fill_narrative

        async def fake_sc(*args, **kwargs):
            return _make_result(False, error="timeout")

        monkeypatch.setattr("toolkit.structured_llm.structured_call", fake_sc)

        with pytest.raises(ValueError, match="Narrative fill failed"):
            asyncio.run(fill_narrative(_SAMPLE_ANALYSIS, "T", llm_client=None, llm_config={}))

    def test_domain_context_appears_in_prompt(self, monkeypatch: object) -> None:
        import asyncio
        from scenario_authoring.scenario_compiler import fill_narrative

        captured: dict = {}

        async def fake_sc(*args, **kwargs):
            captured.update(kwargs)
            return _make_result(True, {"logrolling": [], "deception_tactics": {}})

        monkeypatch.setattr("toolkit.structured_llm.structured_call", fake_sc)
        asyncio.run(fill_narrative(
            _SAMPLE_ANALYSIS, "T",
            llm_client=None, llm_config={},
            domain_context="Domain: Space agencies participate.",
        ))
        assert "Domain: Space agencies participate." in captured["user_prompt"]


class TestFillNarrativeCli:
    def test_fill_narrative_only_rewrites_fixture_analysis(
        self, tmp_path: Path, monkeypatch: object
    ) -> None:
        import asyncio
        import json
        import shutil
        from argparse import Namespace
        from scenario_authoring.scenario_compiler import _run

        fixture_dir = Path("scenarios/joint_space_mission_v1")
        working_dir = tmp_path / "joint_space_mission_v1"
        working_dir.mkdir()
        for source in fixture_dir.iterdir():
            if source.is_file():
                shutil.copy2(source, working_dir / source.name)

        expected = json.loads((fixture_dir / "scenario_analysis.json").read_text(encoding="utf-8"))
        stubbed = json.loads((working_dir / "scenario_analysis.json").read_text(encoding="utf-8"))
        stubbed["logrolling"] = []
        stubbed["deception_tactics"] = {}
        (working_dir / "scenario_analysis.json").write_text(
            json.dumps(stubbed, indent=2, sort_keys=True),
            encoding="utf-8",
        )

        domain_context_file = tmp_path / "domain_context.txt"
        domain_context_file.write_text(
            "Domain: Joint Space Mission. Three space agencies are negotiating.",
            encoding="utf-8",
        )

        captured: dict[str, object] = {}

        async def fake_sc(*args, **kwargs):
            captured.update(kwargs)
            return _make_result(
                True,
                {
                    "logrolling": expected["logrolling"],
                    "deception_tactics": expected["deception_tactics"],
                },
            )

        monkeypatch.setattr("toolkit.structured_llm.structured_call", fake_sc)

        args = Namespace(
            scenario=None,
            fill_narrative_only=str(working_dir / "scenario_analysis.json"),
            faction=None,
            output_dir=None,
            scenario_title="Joint Space Mission",
            domain_context_file=str(domain_context_file),
            batna_fraction=DEFAULT_BATNA_FRACTION,
            batna_fractions=None,
            force_batna_fraction=False,
        )

        asyncio.run(_run(args))

        updated = json.loads((working_dir / "scenario_analysis.json").read_text(encoding="utf-8"))
        assert updated == expected
        assert "Scenario title: Joint Space Mission" in captured["user_prompt"]
        assert "Domain: Joint Space Mission. Three space agencies are negotiating." in captured["user_prompt"]
        assert (working_dir / "alpha.txt").is_file()
        assert "DECEPTION TACTIC" in (working_dir / "alpha.txt").read_text(encoding="utf-8")
