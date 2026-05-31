from __future__ import annotations

from typing import Any


class ToolkitLLMAdapter:
    """Adapt toolkit LLM calls to Diplomat's module interface.

    When a ``cost_accountant`` is provided, all calls route through
    ``accountant.complete()`` which estimates cost, checks budgets,
    tracks spend in a JSONL ledger, and then calls the underlying
    ``llm_client.complete()``.  Without an accountant the adapter
    calls ``llm_client.complete()`` directly (test / offline mode).
    """

    def __init__(
        self,
        toolkit_llm: Any,
        cost_accountant: Any | None = None,
    ) -> None:
        self._toolkit = toolkit_llm
        self._accountant = cost_accountant

    def complete(
        self,
        *,
        messages: list[dict[str, str]],
        config: dict[str, Any],
        tier: Any = None,
        max_tokens: int | None = None,
        attribution: str | None = None,
        purpose: str | None = None,
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

        if self._accountant is not None:
            response = self._accountant.complete(
                messages=tk_messages,
                config=tk_config,
                tier=tk_tier,
                attribution=attribution,
                purpose=purpose,
            )
        else:
            # Use complete_with_retry for the direct path so test/offline
            # mode gets the same transient-failure handling as production.
            complete_fn = getattr(
                self._toolkit, "complete_with_retry", self._toolkit.complete
            )
            response = complete_fn(
                messages=tk_messages,
                config=tk_config,
                tier=tk_tier,
                attribution=attribution,
                purpose=purpose,
            )
        return response.content


class DiplomatCostGate:
    """Expose the budget-gate API expected by Diplomat's Orchestrator.

    Reads actual spend from the shared CostAccountant to enforce
    per-round budgets. The accountant tracks cumulative session spend;
    the gate compares current spend against the snapshot taken at
    round start to determine remaining round budget.
    """

    def __init__(self, accountant: Any, per_round_budget_usd: float) -> None:
        self._accountant = accountant
        self._per_round_budget_usd = per_round_budget_usd
        self._round_start_spend = getattr(accountant, "session_total", 0.0)

    def available_budget(self) -> float:
        current_spend = getattr(self._accountant, "session_total", 0.0)
        round_spend = current_spend - self._round_start_spend
        return max(0.0, self._per_round_budget_usd - round_spend)

    def reset_round_budget(self, amount: float) -> None:
        self._per_round_budget_usd = amount
        self._round_start_spend = getattr(self._accountant, "session_total", 0.0)

    def record_spend(self, cost_usd: float) -> None:
        # Kept for backwards compatibility but no longer needed —
        # spend is read directly from the accountant's session_total.
        pass

    @property
    def session_total(self) -> float:
        return getattr(self._accountant, "session_total", 0.0)


__all__ = ["ToolkitLLMAdapter", "DiplomatCostGate"]
