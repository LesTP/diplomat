from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from adapters import ToolkitLLMAdapter


@dataclass
class FakeMessage:
    role: str
    content: str


@dataclass
class FakeLLMConfig:
    provider: str
    api_key: str
    models: dict[str, str]
    max_tokens: int = 4096


class FakeModelTier(str):
    DEFAULT = "default"

    def __new__(cls, value: str):
        return str.__new__(cls, value)


@dataclass
class FakeResponse:
    content: str


class FakeToolkit:
    Message = FakeMessage
    LLMConfig = FakeLLMConfig
    ModelTier = FakeModelTier

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def complete_with_retry(self, **kwargs: Any) -> FakeResponse:
        self.calls.append(kwargs)
        return FakeResponse("ok")

    def complete(self, **kwargs: Any) -> FakeResponse:
        self.calls.append(kwargs)
        return FakeResponse("fallback")


class FakeAccountant:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def complete(self, **kwargs: Any) -> FakeResponse:
        self.calls.append(kwargs)
        return FakeResponse("accounted")


def test_toolkit_adapter_forwards_attribution_and_purpose_direct_path():
    toolkit = FakeToolkit()
    adapter = ToolkitLLMAdapter(toolkit)

    result = adapter.complete(
        messages=[{"role": "user", "content": "hello"}],
        config={"provider": "fake", "models": {"default": "fake-model"}},
        tier="default",
        attribution="alpha",
        purpose="generation",
    )

    assert result == "ok"
    assert toolkit.calls[0]["attribution"] == "alpha"
    assert toolkit.calls[0]["purpose"] == "generation"


def test_toolkit_adapter_forwards_attribution_and_purpose_accounted_path():
    toolkit = FakeToolkit()
    accountant = FakeAccountant()
    adapter = ToolkitLLMAdapter(toolkit, cost_accountant=accountant)

    result = adapter.complete(
        messages=[{"role": "user", "content": "hello"}],
        config={"provider": "fake", "models": {"default": "fake-model"}},
        tier="default",
        attribution="beta",
        purpose="analysis",
    )

    assert result == "accounted"
    assert accountant.calls[0]["attribution"] == "beta"
    assert accountant.calls[0]["purpose"] == "analysis"
