"""Tests for production entry point (src/main.py) wiring.

Mostly covers the _attach_reconciler helper since main.py's other paths
require real toolkit imports + .env + Telegram credentials.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml


PROJECT_ROOT = Path(__file__).resolve().parent.parent


class FakeOrchestrator:
    """Minimal target for reconciler attachment."""
    def __init__(self) -> None:
        # Attribute should not exist initially — production main never sets it.
        pass


class FakeLLMAdapter:
    """No-op adapter; reconciler holds the reference but never calls it in
    these tests."""
    pass


class TestAttachReconciler:
    def test_attaches_when_primary_provider_present(self, tmp_path, monkeypatch):
        """Happy path: pipeline.yaml has llm_providers.primary → reconciler attached."""
        from main import _attach_reconciler
        config_path = tmp_path / "pipeline.yaml"
        config_path.write_text(yaml.safe_dump({
            "llm_providers": {
                "primary": {
                    "provider": "openai",
                    "models": {"commodity": "gpt-4.1-mini"},
                    "api_key_env": "OPENAI_API_KEY",
                },
            },
        }), encoding="utf-8")
        monkeypatch.setenv("OPENAI_API_KEY", "test-key-value")

        orch = FakeOrchestrator()
        _attach_reconciler(orch, FakeLLMAdapter(), str(config_path))

        assert hasattr(orch, "reconciler")
        # The reconciler should carry the resolved config.
        rec = orch.reconciler
        assert rec.llm_config["provider"] == "openai"
        assert rec.llm_config["models"]["commodity"] == "gpt-4.1-mini"
        assert rec.llm_config["api_key"] == "test-key-value"
        assert rec.tier == "commodity"

    def test_no_primary_means_no_attach(self, tmp_path):
        """If pipeline.yaml lacks llm_providers.primary, skip silently —
        orchestrator handles missing reconciler gracefully."""
        from main import _attach_reconciler
        config_path = tmp_path / "pipeline.yaml"
        config_path.write_text(yaml.safe_dump({"llm_providers": {}}), encoding="utf-8")

        orch = FakeOrchestrator()
        _attach_reconciler(orch, FakeLLMAdapter(), str(config_path))

        assert not hasattr(orch, "reconciler")

    def test_missing_api_key_env_handled(self, tmp_path, monkeypatch):
        """Missing api_key_env in config produces empty key but still attaches
        — caller is responsible for ensuring the env var exists; we don't
        block on it here because reconciler isn't called at attach time."""
        from main import _attach_reconciler
        config_path = tmp_path / "pipeline.yaml"
        config_path.write_text(yaml.safe_dump({
            "llm_providers": {
                "primary": {
                    "provider": "openai",
                    "models": {"commodity": "gpt-4.1-mini"},
                    # no api_key_env
                },
            },
        }), encoding="utf-8")

        orch = FakeOrchestrator()
        _attach_reconciler(orch, FakeLLMAdapter(), str(config_path))

        assert hasattr(orch, "reconciler")
        assert orch.reconciler.llm_config["api_key"] == ""

    def test_unset_api_key_env_produces_empty_string(self, tmp_path, monkeypatch):
        """When api_key_env is set but the env var is missing, api_key is ''
        — reconciler attachment still succeeds (failure surfaces later when
        reconciler actually calls the LLM)."""
        from main import _attach_reconciler
        config_path = tmp_path / "pipeline.yaml"
        config_path.write_text(yaml.safe_dump({
            "llm_providers": {
                "primary": {
                    "provider": "openai",
                    "models": {"commodity": "gpt-4.1-mini"},
                    "api_key_env": "NONEXISTENT_VAR_FOR_TEST",
                },
            },
        }), encoding="utf-8")
        monkeypatch.delenv("NONEXISTENT_VAR_FOR_TEST", raising=False)

        orch = FakeOrchestrator()
        _attach_reconciler(orch, FakeLLMAdapter(), str(config_path))

        assert hasattr(orch, "reconciler")
        assert orch.reconciler.llm_config["api_key"] == ""
