from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from registry import resolve_class


REQUIRED_TOP_LEVEL_KEYS = frozenset(
    {
        "faction_id",
        "database",
        "transport",
        "llm_providers",
        "modules",
        "cost",
        "round_detection",
        "feature_flags",
        "paths",
    }
)

REQUIRED_MODULES = frozenset(
    {
        "event_store",
        "state_manager",
        "extractor",
        "coaching_parser",
        "transport",
        "persona",
        "primary_analyst",
        "secondary_analyst",
        "divergence",
        "context_assembler",
        "generator",
        "adversarial",
        "review_gate",
    }
)


class PipelineConfigError(ValueError):
    pass


@dataclass(frozen=True)
class PipelinePaths:
    coaching_routes: Path
    faction_prompt: Path
    state_updater_prompt: Path
    analyst_prompt: Path
    generation_prompt: Path
    adversarial_prompt: Path
    state_patch_schema: Path
    intelligence_schema: Path
    adversarial_schema: Path


class Orchestrator:
    def __init__(
        self,
        config_path: str | Path = "config/pipeline.yaml",
        *,
        module_overrides: dict[str, Any] | None = None,
        llm_client: Any | None = None,
        telegram_client: Any | None = None,
        base_path: str | Path | None = None,
    ) -> None:
        self.config_path = Path(config_path)
        self.base_path = Path(base_path) if base_path is not None else Path.cwd()
        self.config = self._load_config(self.config_path)
        self._validate_config(self.config)

        self.faction_id = self._required_str(self.config, "faction_id")
        self.db_path = self._path(self.config["database"]["path"])
        self.paths = self._build_paths(self.config["paths"])
        self.prompts = self._load_prompt_files(self.paths)
        self.llm_configs = self._build_llm_configs(self.config["llm_providers"])
        self.cost_config = dict(self.config["cost"])
        self.feature_flags = dict(self.config["feature_flags"])
        self.round_detection = dict(self.config["round_detection"])
        self.current_round = 1

        self._initialize_sqlite(self.db_path)
        self.modules = self._build_modules(
            module_overrides=module_overrides or {},
            llm_client=llm_client,
            telegram_client=telegram_client,
        )
        for name, instance in self.modules.items():
            setattr(self, name, instance)

    def _load_config(self, config_path: Path) -> dict[str, Any]:
        try:
            text = config_path.read_text(encoding="utf-8")
        except OSError as exc:
            raise PipelineConfigError(f"Unable to read pipeline config: {exc}") from exc

        try:
            parsed = yaml.safe_load(text)
        except yaml.YAMLError as exc:
            raise PipelineConfigError(f"Pipeline config is not valid YAML: {exc}") from exc
        if not isinstance(parsed, dict):
            raise PipelineConfigError("Pipeline config must be a mapping")
        return parsed

    def _validate_config(self, config: dict[str, Any]) -> None:
        for key in sorted(REQUIRED_TOP_LEVEL_KEYS):
            if key not in config:
                raise PipelineConfigError(f"Pipeline config missing required key: {key}")

        self._require_mapping(config, "database")
        if not self._has_text(config["database"].get("path")):
            raise PipelineConfigError("Pipeline config requires database.path")

        self._require_mapping(config, "transport")
        self._require_mapping(config, "llm_providers")
        modules = self._require_mapping(config, "modules")
        for module_name in sorted(REQUIRED_MODULES):
            module_config = modules.get(module_name)
            if not isinstance(module_config, dict) or not self._has_text(
                module_config.get("class")
            ):
                raise PipelineConfigError(
                    f"Pipeline config requires modules.{module_name}.class"
                )

        cost = self._require_mapping(config, "cost")
        for key in ("per_round_budget_usd", "session_budget_usd"):
            if not isinstance(cost.get(key), int | float):
                raise PipelineConfigError(f"Pipeline config requires numeric cost.{key}")

        round_detection = self._require_mapping(config, "round_detection")
        mode = round_detection.get("mode")
        if mode not in {"signal", "time"}:
            raise PipelineConfigError(
                "Pipeline config round_detection.mode must be signal or time"
            )
        if mode == "signal" and not self._has_text(round_detection.get("pattern")):
            raise PipelineConfigError(
                "Pipeline config requires round_detection.pattern in signal mode"
            )
        if mode == "time" and not isinstance(
            round_detection.get("interval_seconds"), int | float
        ):
            raise PipelineConfigError(
                "Pipeline config requires round_detection.interval_seconds in time mode"
            )

        flags = self._require_mapping(config, "feature_flags")
        for flag_name in ("adversarial", "review_gate"):
            flag = flags.get(flag_name)
            if not isinstance(flag, dict) or not isinstance(flag.get("enabled"), bool):
                raise PipelineConfigError(
                    f"Pipeline config requires feature_flags.{flag_name}.enabled"
                )

        paths = self._require_mapping(config, "paths")
        self._require_mapping(paths, "prompts")
        self._require_mapping(paths, "schemas")

    def _build_paths(self, paths: dict[str, Any]) -> PipelinePaths:
        prompts = paths["prompts"]
        schemas = paths["schemas"]
        return PipelinePaths(
            coaching_routes=self._path(paths["coaching_routes"]),
            faction_prompt=self._path(paths["faction_prompt"]),
            state_updater_prompt=self._path(prompts["state_updater"]),
            analyst_prompt=self._path(prompts["analyst"]),
            generation_prompt=self._path(prompts["generation"]),
            adversarial_prompt=self._path(prompts["adversarial"]),
            state_patch_schema=self._path(schemas["state_patch"]),
            intelligence_schema=self._path(schemas["intelligence"]),
            adversarial_schema=self._path(schemas["adversarial"]),
        )

    def _load_prompt_files(self, paths: PipelinePaths) -> dict[str, str]:
        prompt_paths = {
            "state_updater": paths.state_updater_prompt,
            "analyst": paths.analyst_prompt,
            "generation": paths.generation_prompt,
            "adversarial": paths.adversarial_prompt,
            "faction": paths.faction_prompt,
        }
        prompts: dict[str, str] = {}
        for name, path in prompt_paths.items():
            try:
                prompts[name] = path.read_text(encoding="utf-8").strip()
            except OSError as exc:
                raise PipelineConfigError(f"Missing prompt file for {name}: {path}") from exc
            if not prompts[name]:
                raise PipelineConfigError(f"Prompt file for {name} is blank: {path}")

        for path in (
            paths.coaching_routes,
            paths.state_patch_schema,
            paths.intelligence_schema,
            paths.adversarial_schema,
        ):
            if not path.is_file():
                raise PipelineConfigError(f"Missing required config file: {path}")
        return prompts

    def _build_llm_configs(
        self, providers: dict[str, Any]
    ) -> dict[str, dict[str, Any]]:
        configs: dict[str, dict[str, Any]] = {}
        for provider_id, provider_config in providers.items():
            if not isinstance(provider_config, dict):
                raise PipelineConfigError(
                    f"Pipeline config llm_providers.{provider_id} must be a mapping"
                )
            for key in ("provider", "model", "api_key_env"):
                if not self._has_text(provider_config.get(key)):
                    raise PipelineConfigError(
                        f"Pipeline config requires llm_providers.{provider_id}.{key}"
                    )
            configs[str(provider_id)] = {
                "provider": provider_config["provider"],
                "model": provider_config["model"],
                "api_key_env": provider_config["api_key_env"],
                "api_key": os.getenv(provider_config["api_key_env"]),
            }
        return configs

    def _build_modules(
        self,
        *,
        module_overrides: dict[str, Any],
        llm_client: Any | None,
        telegram_client: Any | None,
    ) -> dict[str, Any]:
        modules: dict[str, Any] = {}
        module_config = self.config["modules"]
        for name in REQUIRED_MODULES:
            if name in module_overrides:
                modules[name] = module_overrides[name]
                continue
            modules[name] = self._build_module(
                name,
                module_config[name],
                llm_client=llm_client,
                telegram_client=telegram_client,
            )
        return modules

    def _build_module(
        self,
        name: str,
        config: dict[str, Any],
        *,
        llm_client: Any | None,
        telegram_client: Any | None,
    ) -> Any:
        class_name = config["class"]
        cls = resolve_class(class_name)
        if name == "event_store":
            return cls(self.db_path)
        if name == "state_manager":
            return cls(self.db_path, self.paths.state_patch_schema)
        if name == "extractor":
            if class_name == "RuleBasedExtractor":
                return cls(self.paths.state_patch_schema)
            provider_id = self._provider_id(config)
            return cls(
                llm_client,
                self.llm_configs[provider_id],
                self.paths.state_patch_schema,
                self.paths.state_updater_prompt,
            )
        if name == "coaching_parser":
            return cls(self.paths.coaching_routes)
        if name == "transport":
            if class_name == "CLITransport":
                return cls(reader=[], writer=_noop_writer)
            if telegram_client is None:
                raise PipelineConfigError(
                    "Telegram transport requires injected telegram_client"
                )
            transport = self.config["transport"]
            return cls(
                telegram_client,
                public_channel_id=self._env_value(
                    transport["public_channel_id_env"]
                ),
                coaching_channel_id=self._env_value(
                    transport["coaching_channel_id_env"]
                ),
                private_channel_ids=transport.get("private_channel_ids", {}),
                faction_map=transport.get("faction_map", {}),
                operator_user_ids=self._env_list(
                    transport.get("operator_user_ids_env")
                ),
            )
        if name == "persona":
            return cls(self.paths.faction_prompt)
        if name in {"primary_analyst", "secondary_analyst"}:
            provider_id = self._provider_id(config)
            return cls(
                llm_client,
                self.llm_configs[provider_id],
                config.get("tier", "quality"),
                self.paths.analyst_prompt,
                self.paths.intelligence_schema,
                provider_id,
            )
        if name == "divergence":
            return cls
        if name == "context_assembler":
            return cls()
        if name == "generator":
            provider_id = self._provider_id(config)
            return cls(
                llm_client,
                self.llm_configs[provider_id],
                config.get("tier", "quality"),
                max_tokens=int(config.get("max_tokens", 1024)),
                review_gate_enabled=self.feature_flags["review_gate"]["enabled"],
            )
        if name == "adversarial":
            provider_id = self._provider_id(config)
            return cls(
                llm_client,
                self.llm_configs[provider_id],
                config.get("tier", "quality"),
                self.paths.adversarial_prompt,
                self.paths.adversarial_schema,
            )
        if name == "review_gate":
            if class_name == "TelegramReviewGate":
                if telegram_client is None:
                    raise PipelineConfigError(
                        "Telegram review gate requires injected telegram_client"
                    )
                return cls(
                    telegram_client,
                    coaching_channel_id=self._env_value(
                        self.config["transport"]["coaching_channel_id_env"]
                    ),
                )
            return cls()
        raise PipelineConfigError(f"Unsupported module name: {name}")

    def _provider_id(self, config: dict[str, Any]) -> str:
        provider_id = str(config.get("provider", "primary"))
        if provider_id not in self.llm_configs:
            raise PipelineConfigError(f"Unknown LLM provider: {provider_id}")
        return provider_id

    def _initialize_sqlite(self, db_path: Path) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(db_path) as conn:
            conn.execute("PRAGMA journal_mode=WAL")

    def _path(self, value: Any) -> Path:
        if not self._has_text(value):
            raise PipelineConfigError("Expected nonblank path value")
        path = Path(value)
        if path.is_absolute():
            return path
        return self.base_path / path

    @staticmethod
    def _require_mapping(config: dict[str, Any], key: str) -> dict[str, Any]:
        value = config.get(key)
        if not isinstance(value, dict):
            raise PipelineConfigError(f"Pipeline config requires mapping: {key}")
        return value

    @staticmethod
    def _required_str(config: dict[str, Any], key: str) -> str:
        value = config.get(key)
        if not Orchestrator._has_text(value):
            raise PipelineConfigError(f"Pipeline config requires {key}")
        return value.strip()

    @staticmethod
    def _has_text(value: Any) -> bool:
        return isinstance(value, str) and bool(value.strip())

    @staticmethod
    def _env_value(env_var: str) -> str:
        value = os.getenv(env_var)
        if value is None or not value.strip():
            raise PipelineConfigError(f"Missing required environment variable: {env_var}")
        return value.strip()

    @staticmethod
    def _env_list(env_var: str | None) -> list[str]:
        if not env_var:
            return []
        value = os.getenv(env_var, "")
        return [item.strip() for item in value.split(",") if item.strip()]


async def _noop_writer(_line: str) -> None:
    return None


__all__ = ["Orchestrator", "PipelineConfigError", "PipelinePaths"]
