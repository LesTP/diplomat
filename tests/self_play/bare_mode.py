"""Bare-mode module stand-ins for ablation experiments.

When ``--bare-prompt`` is used in self-play, these no-op / minimal
implementations replace Extraction, Analyst (primary + secondary),
Adversarial, and Coaching, leaving only Transport, Persona,
Context Assembler (in bare mode), and Generation active.

Usage::

    from tests.self_play.bare_mode import bare_module_overrides, _BareReconciler

    # Pass overrides to GameEnvironment
    env = GameEnvironment(..., extra_module_overrides=bare_module_overrides(state_manager))

    # After setup(), override reconciler per agent
    for handle in env.agents.values():
        handle.orchestrator.reconciler = _BareReconciler()
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from modules.adversarial import AdversarialResult
from modules.extraction import ExtractionResult
from modules.reconciliation import ReconciliationResult
from modules.types import AnalysisResult, StatePatch
from toolkit.coaching import CoachingEvent


class _BareExtractor:
    """No-op extractor — returns an empty patch without calling any LLM."""

    async def extract(
        self, input_text: str, current_state: dict[str, Any], trigger_type: str
    ) -> ExtractionResult:
        return ExtractionResult(success=True, patch=StatePatch({}), error=None)


class _BareAnalyst:
    """No-op analyst — always returns failure so orchestrator skips intelligence storage."""

    def __init__(self, provider_id: str = "bare") -> None:
        self.provider_id = provider_id

    async def analyze(
        self,
        state: dict[str, Any],
        recent_events: list[Any] | None = None,
    ) -> AnalysisResult:
        return AnalysisResult(
            success=False,
            provider_id=self.provider_id,
            report=None,
            error="bare_mode",
            timestamp=datetime.now(timezone.utc),
        )


class _BareReconciler:
    """No-op reconciler — returns success without any LLM call or state mutation."""

    async def reconcile(
        self,
        current_state: dict[str, Any],
        recent_events: list[Any],
        round_number: int,
    ) -> ReconciliationResult:
        return ReconciliationResult(success=True)


class _BareAdversarial:
    """No-op adversarial reader — returns success with no analysis."""

    async def read(self, draft: str) -> AdversarialResult:
        return AdversarialResult(success=True, analysis=None, error=None)


class _BareCoaching:
    """No-op coaching parser — returns an empty free-coaching event for any input."""

    def parse(self, raw_input: str) -> CoachingEvent:
        return CoachingEvent(coaching_type="FREE", content="", route="free_coaching")


def bare_module_overrides(state_manager: Any) -> dict[str, Any]:
    """Return a module-overrides dict for bare-prompt ablation mode.

    Disables Extraction, Analyst (primary + secondary), Adversarial, and
    Coaching. Divergence callable is kept (it is never reached since primary
    analyst always returns success=False). Reconciler is NOT included here
    because it is attached externally after Orchestrator construction — callers
    must set ``orchestrator.reconciler = _BareReconciler()`` themselves after
    calling ``GameEnvironment.setup()``.

    Pass the returned dict as ``extra_module_overrides`` to
    ``GameEnvironment``.
    """
    from modules.analyst.divergence import compare

    return {
        "extractor": _BareExtractor(),
        "primary_analyst": _BareAnalyst(provider_id="bare_primary"),
        "secondary_analyst": _BareAnalyst(provider_id="bare_secondary"),
        "divergence": compare,
        "adversarial": _BareAdversarial(),
        "coaching_parser": _BareCoaching(),
    }


__all__ = ["bare_module_overrides", "_BareReconciler"]
