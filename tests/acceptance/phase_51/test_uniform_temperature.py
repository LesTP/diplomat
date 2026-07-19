"""Phase 51, Item 1 — Uniform temperature across all provider slots.

Contract: _generate_faction_config must apply the temperature override to every
provider slot present in the emitted per-faction config, not just the generator
slot. Reasoning models (gpt-5.x / o-series) are the documented exception: those
slots are excluded from temperature injection and must be named explicitly in the
emitted config so a cell's true temperature profile is recorded rather than
implied.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
PERSONAS_DIR = PROJECT_ROOT / "tests" / "self_play" / "personas"


def _make_env(
    tmp_path: Path,
    *,
    temperature: float | None = None,
    per_faction_providers: dict | None = None,
):
    """Minimal GameEnvironment for config-generation tests — no setup() required."""
    from tests.helpers.factories import FakeCostAccountant, FakeLLMClient
    from tests.self_play.game_environment import GameEnvironment

    return GameEnvironment(
        faction_personas={"alpha": PERSONAS_DIR / "alpha.txt"},
        llm_client=FakeLLMClient([]),
        cost_accountant=FakeCostAccountant(),
        base_path=PROJECT_ROOT,
        tmp_dir=tmp_path,
        temperature=temperature,
        per_faction_providers=per_faction_providers or {},
    )


def _emitted_config(env, tmp_path: Path) -> dict:
    config_path = env._generate_faction_config(
        "alpha", PERSONAS_DIR / "alpha.txt", tmp_path / "alpha.db"
    )
    return yaml.safe_load(config_path.read_text(encoding="utf-8"))


class TestUniformTemperature:
    """AC 1 — temperature=X applied to every provider slot."""

    def test_primary_slot_gets_temperature(self, tmp_path: Path) -> None:
        """Primary provider slot must carry the temperature override."""
        env = _make_env(tmp_path, temperature=0.3)
        config = _emitted_config(env, tmp_path)
        primary = config["llm_providers"].get("primary", {})
        assert primary.get("temperature") == pytest.approx(0.3), (
            "primary slot missing temperature override"
        )

    def test_secondary_slot_gets_temperature(self, tmp_path: Path) -> None:
        """Secondary provider slot must carry the temperature override."""
        env = _make_env(tmp_path, temperature=0.3)
        config = _emitted_config(env, tmp_path)
        secondary = config["llm_providers"].get("secondary", {})
        assert secondary.get("temperature") == pytest.approx(0.3), (
            "secondary slot missing temperature override"
        )

    def test_all_slots_get_temperature(self, tmp_path: Path) -> None:
        """Every provider slot in the emitted config must have temperature: X."""
        env = _make_env(tmp_path, temperature=0.5)
        config = _emitted_config(env, tmp_path)
        providers = config["llm_providers"]
        for slot_name, slot_config in providers.items():
            # Reasoning-model slots are the exception (tested separately).
            # For a standard run every slot should carry the temperature.
            assert "temperature" in slot_config, (
                f"Provider slot '{slot_name}' is missing the temperature override"
            )
            assert slot_config["temperature"] == pytest.approx(0.5), (
                f"Provider slot '{slot_name}' has wrong temperature value"
            )


class TestTemperatureNoneRegression:
    """AC 2 — temperature=None must not inject any temperature key."""

    def test_no_temperature_key_when_none(self, tmp_path: Path) -> None:
        """With temperature=None, no slot in the emitted config carries a temperature key."""
        env = _make_env(tmp_path, temperature=None)
        config = _emitted_config(env, tmp_path)
        providers = config["llm_providers"]
        for slot_name, slot_config in providers.items():
            assert "temperature" not in slot_config, (
                f"Slot '{slot_name}' has a spurious temperature key (temperature=None)"
            )


class TestGeneratorOverrideSlot:
    """Temperature propagates to the per-faction generator_override slot too."""

    def test_generator_override_gets_temperature(self, tmp_path: Path) -> None:
        """When a per-faction provider override creates generator_override, it also gets temperature."""
        env = _make_env(
            tmp_path,
            temperature=0.4,
            per_faction_providers={"alpha": {"provider": "openai", "model": "gpt-4.1-mini"}},
        )
        config = _emitted_config(env, tmp_path)
        providers = config["llm_providers"]
        assert "generator_override" in providers, "generator_override slot must be present"
        assert providers["generator_override"].get("temperature") == pytest.approx(0.4), (
            "generator_override slot missing temperature override"
        )

    def test_generator_override_none_no_temperature(self, tmp_path: Path) -> None:
        """With temperature=None, generator_override slot also carries no temperature key."""
        env = _make_env(
            tmp_path,
            temperature=None,
            per_faction_providers={"alpha": {"provider": "openai", "model": "gpt-4.1-mini"}},
        )
        config = _emitted_config(env, tmp_path)
        providers = config["llm_providers"]
        if "generator_override" in providers:
            assert "temperature" not in providers["generator_override"], (
                "generator_override has spurious temperature key when temperature=None"
            )


class TestReasoningModelExemption:
    """AC 3 — reasoning model slots are exempt and documented."""

    def test_reasoning_model_slot_documented_as_exempt(self, tmp_path: Path) -> None:
        """When a gpt-5.x model occupies a slot, the emitted config names it as exempt."""
        env = _make_env(
            tmp_path,
            temperature=0.7,
            per_faction_providers={"alpha": {"provider": "openai", "model": "gpt-5.5"}},
        )
        config = _emitted_config(env, tmp_path)
        # Contract: the config must carry a field documenting temperature-exempt slots.
        # Acceptable key names: temperature_exempt_slots, temperature_profile, etc.
        has_exempt_doc = (
            "temperature_exempt_slots" in config
            or "temperature_profile" in config
        )
        assert has_exempt_doc, (
            "Config must document temperature-exempt slots when a reasoning model is present. "
            "Expected a 'temperature_exempt_slots' or 'temperature_profile' key."
        )

    def test_reasoning_model_exempt_list_is_nonempty(self, tmp_path: Path) -> None:
        """The exempt-slots field must be non-empty when a reasoning model is in the generator slot."""
        env = _make_env(
            tmp_path,
            temperature=0.7,
            per_faction_providers={"alpha": {"provider": "openai", "model": "gpt-5.5"}},
        )
        config = _emitted_config(env, tmp_path)
        exempt = config.get("temperature_exempt_slots") or (
            config.get("temperature_profile") or {}
        ).get("exempt_slots")
        assert exempt, (
            "temperature_exempt_slots must be non-empty when a gpt-5.x model is present"
        )

    def test_non_reasoning_model_no_exempt_entry(self, tmp_path: Path) -> None:
        """With no reasoning models, the exempt-slots field is absent or empty."""
        env = _make_env(tmp_path, temperature=0.5)
        config = _emitted_config(env, tmp_path)
        exempt = config.get("temperature_exempt_slots") or (
            config.get("temperature_profile") or {}
        ).get("exempt_slots")
        assert not exempt, (
            "temperature_exempt_slots must be absent or empty when no reasoning models are present"
        )
