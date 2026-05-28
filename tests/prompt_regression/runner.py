"""Diplomat-specific prompt regression runner.

Provides diplomat module dispatch and CLI entry point.
Generic runner infrastructure is in toolkit.prompt_regression.
"""

from __future__ import annotations

import argparse
import asyncio
from inspect import isawaitable
from typing import Any

from modules.context_assembler import DecisionContext
from modules.extraction import RuleBasedExtractor
from modules.generation import LLMGenerator

from toolkit.prompt_regression.runner import ScenarioRunner  # noqa: F401 — re-export
from toolkit.prompt_regression.types import RunReport  # noqa: F401


async def diplomat_module_caller(
    module_name: str, input_data: Any, metadata: dict[str, Any]
) -> Any:
    """Diplomat-specific module dispatch for prompt regression scenarios."""
    if module_name == "extraction":
        extractor = RuleBasedExtractor("config/schemas/state_patch.json")
        result = extractor.extract(
            input_data["text"],
            input_data.get("current_state", {}),
            input_data.get("trigger_type", "message"),
        )
    elif module_name == "generation":
        # Generation requires an injected LLM client — not available in CLI mode
        raise ValueError(
            "Generation scenarios require an injected LLM client; "
            "use ScenarioRunner with a configured client, not the CLI."
        )
    elif module_name == "analyst":
        raise ValueError(
            "Analyst scenarios require an injected LLM client; "
            "use ScenarioRunner with a configured client, not the CLI."
        )
    elif module_name == "adversarial":
        raise ValueError(
            "Adversarial scenarios require an injected LLM client; "
            "use ScenarioRunner with a configured client, not the CLI."
        )
    else:
        raise ValueError(f"Unsupported scenario module: {module_name}")

    if isawaitable(result):
        return await result
    return result


class _UnavailableLLMClient:
    async def complete(self, **kwargs: Any) -> str:
        raise RuntimeError(
            "No LLM client is configured for this CLI run; use extraction scenarios "
            "or construct ScenarioRunner with an injected client."
        )


async def _main_async(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run prompt regression scenarios.")
    parser.add_argument("--scenarios", required=True, help="Scenario directory")
    parser.add_argument("--module", help="Optional module filter")
    args = parser.parse_args(argv)

    runner = ScenarioRunner(
        llm_client=_UnavailableLLMClient(),
        llm_config={},
        module_caller=diplomat_module_caller,
    )
    report = await runner.run_all(args.scenarios, module_filter=args.module)
    return 0 if report.passed == report.total else 1


def main() -> None:
    raise SystemExit(asyncio.run(_main_async()))


if __name__ == "__main__":
    main()
