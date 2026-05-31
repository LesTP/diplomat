from __future__ import annotations

from importlib import import_module
from typing import Any


class RegistryLookupError(LookupError):
    pass


REGISTRY: dict[str, str] = {
    "SQLiteEventStore": "modules.event_store:SQLiteEventStore",
    "SQLiteStateManager": "modules.state_manager:SQLiteStateManager",
    "RuleBasedExtractor": "modules.extraction:RuleBasedExtractor",
    "OpenAIStructuredExtractor": "modules.extraction:OpenAIStructuredExtractor",
    "TaggedCoachingParser": "modules.coaching:TaggedCoachingParser",
    "CLITransport": "modules.transport:CLITransport",
    "TelegramBotTransport": "modules.transport:TelegramBotTransport",
    "FileBasedPersona": "modules.persona:FileBasedPersona",
    "LLMAnalyst": "modules.analyst:LLMAnalyst",
    "DefaultContextAssembler": (
        "modules.context_assembler:DefaultContextAssembler"
    ),
    "LLMGenerator": "modules.generation:LLMGenerator",
    "LLMAdversarialReader": "modules.adversarial:LLMAdversarialReader",
    "AutoApproveReviewGate": "modules.review_gate:AutoApproveReviewGate",
    "TelegramReviewGate": "modules.review_gate:TelegramReviewGate",
    "modules.analyst.divergence.compare": "modules.analyst.divergence:compare",
}


def resolve_class(name: str) -> Any:
    if not isinstance(name, str) or not name.strip():
        raise RegistryLookupError("Registry lookup requires a class name")

    target = REGISTRY.get(name.strip(), name.strip())
    module_name, separator, attribute_name = target.partition(":")
    if not separator:
        module_name, separator, attribute_name = target.rpartition(".")
    if not module_name or not attribute_name:
        raise RegistryLookupError(f"Invalid registry target: {name}")

    try:
        module = import_module(module_name)
        return getattr(module, attribute_name)
    except (ImportError, AttributeError) as exc:
        raise RegistryLookupError(f"Unable to resolve registry target: {name}") from exc


def build(name: str, *args: Any, **kwargs: Any) -> Any:
    return resolve_class(name)(*args, **kwargs)


__all__ = ["REGISTRY", "RegistryLookupError", "build", "resolve_class"]
