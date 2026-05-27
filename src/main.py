from __future__ import annotations

import asyncio
import contextlib
import os
import signal
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from orchestrator import (
    DiplomatCostGate,
    Orchestrator,
    PipelineConfigError,
    ToolkitLLMAdapter,
)


def main() -> None:
    load_dotenv()
    config_path = os.getenv("DIPLOMAT_PIPELINE_CONFIG", "config/pipeline.yaml")
    asyncio.run(run(config_path))


async def run(config_path: str) -> None:
    llm_module = _load_toolkit_module("llm_client")
    llm_adapter = ToolkitLLMAdapter(llm_module)
    telegram_client = _build_telegram_client()
    cost_gate = _build_cost_gate(config_path)

    orchestrator = Orchestrator(
        config_path=config_path,
        llm_client=llm_adapter,
        telegram_client=telegram_client,
        cost_accountant=cost_gate,
    )
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


if __name__ == "__main__":
    main()
