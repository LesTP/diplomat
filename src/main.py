from __future__ import annotations

import asyncio
import contextlib
import os
import signal
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from adapters import DiplomatCostGate, ToolkitLLMAdapter
from orchestrator import Orchestrator, PipelineConfigError


def main() -> None:
    load_dotenv()
    config_path = os.getenv("DIPLOMAT_PIPELINE_CONFIG", "config/pipeline.yaml")
    asyncio.run(run(config_path))


async def run(config_path: str) -> None:
    llm_module = _load_toolkit_module("llm_client")
    cost_gate = _build_cost_gate(config_path)
    # Route all LLM calls through the cost accountant for spend tracking.
    accountant = cost_gate._accountant if cost_gate is not None else None
    llm_adapter = ToolkitLLMAdapter(llm_module, cost_accountant=accountant)
    telegram_client = _build_telegram_client()

    orchestrator = Orchestrator(
        config_path=config_path,
        llm_client=llm_adapter,
        telegram_client=telegram_client,
        cost_accountant=cost_gate,
    )
    _attach_reconciler(orchestrator, llm_adapter, config_path)
    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()

    for signum in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(signum, stop_event.set)
        except NotImplementedError:
            pass

    start_task = asyncio.create_task(orchestrator.start())
    stop_task = asyncio.create_task(stop_event.wait())
    done, pending = await asyncio.wait(
        {start_task, stop_task},
        return_when=asyncio.FIRST_COMPLETED,
    )
    for task in pending:
        task.cancel()
    await orchestrator.shutdown()
    for task in pending:
        with contextlib.suppress(asyncio.CancelledError):
            await task
    for task in done:
        task.result()


def _load_toolkit_module(name: str) -> Any:
    try:
        module = __import__(f"toolkit.{name}", fromlist=[name])
    except ImportError as exc:
        raise PipelineConfigError(
            f"Unable to import toolkit.{name}; install ../toolkit editable first"
        ) from exc
    return module


def _build_telegram_client() -> Any:
    """Construct a toolkit TelegramClient from env vars."""
    try:
        from toolkit.telegram_client import TelegramClient
    except ImportError as exc:
        raise PipelineConfigError(
            "Unable to import toolkit.telegram_client; "
            "install ../toolkit editable first"
        ) from exc

    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    if not bot_token:
        raise PipelineConfigError(
            "TELEGRAM_BOT_TOKEN environment variable is required"
        )
    return TelegramClient(bot_token=bot_token)


def _build_cost_gate(config_path: str) -> DiplomatCostGate | None:
    """Build a DiplomatCostGate wrapping toolkit's CostAccountant."""
    try:
        from toolkit.cost_accountant import CostAccountant
    except ImportError:
        return None

    import yaml
    config = yaml.safe_load(Path(config_path).read_text(encoding="utf-8"))
    cost_config = config.get("cost", {})
    per_round = float(cost_config.get("per_round_budget_usd", 1.0))
    ledger_path = Path(cost_config.get("ledger_path", "data/cost_ledger.jsonl"))

    accountant = CostAccountant(ledger_path=ledger_path)
    return DiplomatCostGate(accountant, per_round_budget_usd=per_round)


def _attach_reconciler(
    orchestrator: Any,
    llm_client: Any,
    config_path: str,
) -> None:
    """Attach a StateReconciler for post-round state cleanup.

    Reconciliation runs at the end of every round (before analyst calls) and:
    - Merges duplicate promises that the extractor logged with different IDs
    - Transitions promises pending → kept/broken when fulfilled or contradicted
    - Flags inconsistencies from position shifts
    - Catches proposals the per-message extractor missed

    Uses the *primary* provider's commodity tier (cheapest model on the main
    provider). The reconciler shares the same llm_client adapter as the rest
    of the pipeline, so calls flow through the cost accountant.

    To disable reconciliation in production, comment out the call to this
    function in run(). No feature flag — keeping the production path lean.
    Self-play has its own per-faction reconciler wiring that overrides this
    one with a LoggingLLMClient-tagged version for SCORE/RECON visibility.
    """
    from modules.reconciliation import StateReconciler

    import yaml
    config = yaml.safe_load(Path(config_path).read_text(encoding="utf-8"))
    primary = config.get("llm_providers", {}).get("primary", {})
    if not primary:
        # Without a primary provider config we can't build a reconciler;
        # silently skip (orchestrator handles missing reconciler gracefully).
        return

    api_key_env = primary.get("api_key_env", "")
    recon_config = {
        "provider": primary.get("provider", "openai"),
        "models": primary.get("models", {}),
        "api_key": os.getenv(api_key_env, "") if api_key_env else "",
    }
    orchestrator.reconciler = StateReconciler(
        llm_client=llm_client,
        llm_config=recon_config,
        tier="commodity",
    )


if __name__ == "__main__":
    main()
