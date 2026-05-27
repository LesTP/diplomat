from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import asdict, is_dataclass
from inspect import isawaitable
from pathlib import Path
from typing import Any, Callable

from modules.context_assembler import DecisionContext
from modules.extraction import RuleBasedExtractor
from modules.generation import LLMGenerator

from tests.prompt_regression.judge import LLMJudge
from tests.prompt_regression.types import (
    PropertyResult,
    RunReport,
    ScenarioResult,
    json_path_exists,
    json_path_get,
    load_scenarios,
)


ModuleBuilder = Callable[[], Any]


class ScenarioRunner:
    def __init__(
        self,
        llm_client: Any,
        llm_config: dict[str, Any],
        module_builders: dict[str, ModuleBuilder],
    ) -> None:
        self.llm_client = llm_client
        self.llm_config = llm_config
        self.module_builders = module_builders
        self.judge = LLMJudge(llm_client, llm_config, tier="commodity")

    async def run_scenario(self, scenario: dict[str, Any]) -> ScenarioResult:
        module_name = scenario["module"]
        if module_name not in self.module_builders:
            raise ValueError(f"No module builder configured for '{module_name}'")

        module = self.module_builders[module_name]()
        raw_output = await self._call_module(module_name, module, scenario["input"])
        output = _normalize_output(raw_output)

        property_results = [
            await self._evaluate_property(property_data, output)
            for property_data in scenario["expected_properties"]
        ]
        return ScenarioResult(
            scenario_id=scenario["scenario_id"],
            description=scenario["description"],
            properties=property_results,
            passed=all(result.passed for result in property_results),
        )

    async def run_all(
        self, scenario_dir: str | Path, module_filter: str | None = None
    ) -> RunReport:
        scenarios = [
            scenario
            for scenario in load_scenarios(scenario_dir)
            if module_filter is None or scenario["module"] == module_filter
        ]
        results = []
        for scenario in scenarios:
            result = await self.run_scenario(scenario)
            results.append(result)
            status = "PASS" if result.passed else "FAIL"
            print(f"{status} {result.scenario_id}: {result.description}")

        passed = sum(1 for result in results if result.passed)
        print(f"Summary: {passed}/{len(results)} scenarios passed")
        return RunReport(results=results, total=len(results), passed=passed)

    async def _call_module(self, module_name: str, module: Any, input_data: dict) -> Any:
        if module_name == "extraction":
            result = module.extract(
                input_data["text"],
                input_data.get("current_state", {}),
                input_data.get("trigger_type", "message"),
            )
        elif module_name == "generation":
            context_data = input_data["context"]
            result = module.generate(
                DecisionContext(
                    system_prompt=context_data["system_prompt"],
                    user_prompt=context_data["user_prompt"],
                    metadata=context_data.get("metadata", {}),
                )
            )
        elif module_name == "analyst":
            result = module.analyze(input_data.get("state", {}))
        elif module_name == "adversarial":
            result = module.read(input_data["draft"])
        else:
            raise ValueError(f"Unsupported scenario module: {module_name}")

        if isawaitable(result):
            return await result
        return result

    async def _evaluate_property(
        self, property_data: dict[str, Any], output: dict[str, Any]
    ) -> PropertyResult:
        check_type = property_data["type"]
        description = property_data["description"]

        if check_type == "json_path_exists":
            exists = json_path_exists(output, property_data["path"])
            return PropertyResult(
                passed=exists,
                description=description,
                expected=True,
                actual=exists,
            )

        if check_type == "json_path_equals":
            expected = property_data["value"]
            try:
                actual = json_path_get(output, property_data["path"])
            except (KeyError, IndexError, TypeError, ValueError) as exc:
                actual = f"{type(exc).__name__}: {exc}"
            return PropertyResult(
                passed=actual == expected,
                description=description,
                expected=expected,
                actual=actual,
            )

        if check_type == "llm_judge":
            response_text = _judge_response_text(property_data, output)
            judge_result = await self.judge.evaluate(
                response_text=response_text,
                criteria=property_data["criteria"],
                pass_instruction=property_data["pass_instruction"],
                fail_instruction=property_data["fail_instruction"],
                context=json.dumps(output, sort_keys=True, default=str),
            )
            return PropertyResult(
                passed=judge_result.verdict == "PASS",
                description=description,
                expected="PASS",
                actual=judge_result.verdict,
                judge_explanation=judge_result.explanation,
            )

        raise ValueError(f"Unsupported property type: {check_type}")


def _normalize_output(value: Any) -> dict[str, Any]:
    if is_dataclass(value):
        normalized = asdict(value)
    elif isinstance(value, dict):
        normalized = value
    else:
        raise ValueError("Module output must be a dataclass or dict")

    if not isinstance(normalized, dict):
        raise ValueError("Module output must normalize to a dict")
    return normalized


def _judge_response_text(property_data: dict[str, Any], output: dict[str, Any]) -> str:
    path = property_data.get("path")
    if path:
        try:
            value = json_path_get(output, path)
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise ValueError(
                f"Cannot extract judge response text from path '{path}': {exc}"
            ) from exc
    else:
        value = output.get("response_text", output)
    if isinstance(value, str):
        return value
    return json.dumps(value, sort_keys=True, default=str)


def _default_module_builders(
    llm_client: Any, llm_config: dict[str, Any]
) -> dict[str, ModuleBuilder]:
    return {
        "extraction": lambda: RuleBasedExtractor("config/schemas/state_patch.json"),
        "generation": lambda: LLMGenerator(
            llm_client,
            llm_config,
            tier="commodity",
            review_gate_enabled=False,
        ),
    }


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
        module_builders=_default_module_builders(_UnavailableLLMClient(), {}),
    )
    report = await runner.run_all(args.scenarios, module_filter=args.module)
    return 0 if report.passed == report.total else 1


def main() -> None:
    raise SystemExit(asyncio.run(_main_async()))


if __name__ == "__main__":
    main()
