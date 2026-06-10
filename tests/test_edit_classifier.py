from __future__ import annotations

from modules.edit_classifier import build_edit_classifier


class FakeLLMClient:
    """Minimal stand-in for the LLM client; factory test never invokes it."""

    async def complete(self, **kwargs):
        return "{}"


def test_build_edit_classifier_uses_primary_provider_config():
    classifier = build_edit_classifier(
        llm_client=FakeLLMClient(),
        llm_providers_config={
            "primary": {
                "provider": "google",
                "models": {"commodity": "gemini-2.5-flash-lite"},
                "api_key_env": "GOOGLE_API_KEY",
            }
        },
        tier="commodity",
        attribution="alpha",
    )

    assert classifier is not None
    assert classifier.llm_config["provider"] == "google"
    assert classifier.llm_config["models"]["commodity"] == "gemini-2.5-flash-lite"
    assert classifier.attribution == "alpha"


def test_build_edit_classifier_returns_none_without_primary():
    classifier = build_edit_classifier(
        llm_client=FakeLLMClient(),
        llm_providers_config={},
        tier="commodity",
    )
    assert classifier is None
