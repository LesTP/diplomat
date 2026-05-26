from __future__ import annotations

import asyncio
import contextlib
import os
import signal
from typing import Any

from dotenv import load_dotenv

from orchestrator import Orchestrator, PipelineConfigError


def main() -> None:
    load_dotenv()
    config_path = os.getenv("DIPLOMAT_PIPELINE_CONFIG", "config/pipeline.yaml")
    asyncio.run(run(config_path))


async def run(config_path: str) -> None:
    orchestrator = Orchestrator(
        config_path=config_path,
        llm_client=_load_toolkit_module("llm_client"),
        telegram_client=_build_telegram_client(),
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
    telegram_client = _load_toolkit_module("telegram_client")
    for factory_name in ("build_client_from_env", "create_client_from_env", "create_client"):
        factory = getattr(telegram_client, factory_name, None)
        if factory is not None:
            return factory()
    return telegram_client


if __name__ == "__main__":
    main()
