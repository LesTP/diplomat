from __future__ import annotations

from typing import Any


class ToolkitLLMAdapter:
    """Adapt toolkit.llm_client.complete() to Diplomat's module interface."""

    def __init__(self, toolkit_llm: Any) -> None:
        self._toolkit = toolkit_llm

    def complete(
        self,
        *,
        messages: list[dict[str, str]],
        config: dict[str, Any],
        tier: Any = None,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> str:
        Message = self._toolkit.Message
        LLMConfig = self._toolkit.LLMConfig
        ModelTier = self._toolkit.ModelTier

        tk_messages = [
            Message(role=message["role"], content=message["content"])
            for message in messages
        ]

        models = config.get("models", {})
        if not models and "model" in config:
            single_model = config["model"]
            models = {
                "quality": single_model,
                "default": single_model,
                "commodity": single_model,
            }

        tk_config = LLMConfig(
            provider=config["provider"],
            api_key=config.get("api_key") or "",
            models=models,
            max_tokens=max_tokens or 4096,
        )

        tier_str = tier.value if hasattr(tier, "value") else str(tier or "default")
        try:
            tk_tier = ModelTier(tier_str)
        except ValueError:
            tk_tier = ModelTier.DEFAULT

        response = self._toolkit.complete(
            messages=tk_messages,
            config=tk_config,
            tier=tk_tier,
        )
        return response.content


class DiplomatCostGate:
    """Expose the budget-gate API expected by Diplomat's Orchestrator."""

    def __init__(self, accountant: Any, per_round_budget_usd: float) -> None:
        self._accountant = accountant
        self._per_round_budget_usd = per_round_budget_usd
        self._round_spend = 0.0

    def available_budget(self) -> float:
        return max(0.0, self._per_round_budget_usd - self._round_spend)

    def reset_round_budget(self, amount: float) -> None:
        self._per_round_budget_usd = amount
        self._round_spend = 0.0

    def record_spend(self, cost_usd: float) -> None:
        self._round_spend += cost_usd

    @property
    def session_total(self) -> float:
        return getattr(self._accountant, "session_total", 0.0)


__all__ = ["ToolkitLLMAdapter", "DiplomatCostGate"]
