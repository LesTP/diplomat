from __future__ import annotations

import asyncio
import contextlib
import json
import os
import re
import sqlite3  # Used only for pre-flight database initialization.
import uuid
from dataclasses import asdict, dataclass, is_dataclass
from datetime import datetime, timezone
from inspect import isawaitable
from pathlib import Path
from typing import Any

import yaml

from modules.coaching import CoachingEvent, Command
from modules.context_assembler import CoachingEntry
from modules.generation import GenerationResult
from modules.persona import CoachingContext
from modules.transport import OutboundMessage
from modules.types import Divergence, EventFilter, InboundEvent, PatchSource
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
        cost_accountant: Any | None = None,
        cost_accountant_factory: Any | None = None,
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
        self.cost_accountant = cost_accountant or self._build_cost_accountant(
            cost_accountant_factory
        )
        self.feature_flags = dict(self.config["feature_flags"])
        self.round_detection = dict(self.config["round_detection"])
        self.message_debounce_seconds = float(
            self.config.get("message_debounce_seconds", 0.5)
        )
        self.current_round = 1
        self._running = False
        self._extraction_tasks: set[asyncio.Task[None]] = set()
        self._round_timer_task: asyncio.Task[None] | None = None

        self._initialize_sqlite(self.db_path)
        self._reset_round_budget()
        self.modules = self._build_modules(
            module_overrides=module_overrides or {},
            llm_client=llm_client,
            telegram_client=telegram_client,
        )
        for name, instance in self.modules.items():
            setattr(self, name, instance)

    async def start(self) -> None:
        session_budget = float(self.cost_config.get("session_budget_usd", 0.0))
        print(
            f"DIPLOMAT ONLINE - Round {self.current_round} - {self.faction_id}"
            f" - session budget ${session_budget:.2f}"
        )
        self._running = True
        if self.round_detection["mode"] == "time":
            self._round_timer_task = asyncio.create_task(self._time_round_loop())
        try:
            async for event in self.transport.listen():
                if not self._running:
                    break
                await self.process_event(event)
        finally:
            self._running = False

    async def shutdown(self) -> None:
        self._running = False
        tasks = list(self._extraction_tasks)  # snapshot to avoid mutation during iteration
        for task in tasks:
            if not task.done():
                task.cancel()
        for task in tasks:
            with contextlib.suppress(asyncio.CancelledError):
                await task
        self._extraction_tasks.clear()
        if self._round_timer_task is not None and not self._round_timer_task.done():
            self._round_timer_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._round_timer_task

        close = getattr(self.transport, "close", None)
        if close is None:
            close = getattr(self.transport, "aclose", None)
        if close is not None:
            await _maybe_await(close())

    async def process_event(self, event: InboundEvent) -> str:
        event_id = await self.event_store.append(event, self.current_round)
        if event.sender_faction == "operator":
            await self._route_operator_event(event, event_id)
            return event_id

        self._enqueue_message_extraction(event, event_id)
        if await self._check_round_boundary(event):
            return event_id
        if self._is_direct_address(event):
            await self.run_response_pipeline(trigger_event=event)
        return event_id

    async def _route_operator_event(self, event: Any, event_id: str) -> None:
        parsed = self.coaching_parser.parse(event.content)
        if isinstance(parsed, Command):
            await self._dispatch_command(parsed)
            return
        if isinstance(parsed, CoachingEvent) and parsed.route == "state_updater":
            await self._apply_extraction(parsed.content, "intel_correction", event_id)
            return
        if isinstance(parsed, CoachingEvent):
            await self._store_coaching(parsed)
            return
        raise RuntimeError(f"Unsupported coaching parser result: {parsed!r}")

    def _enqueue_message_extraction(self, event: Any, event_id: str) -> None:
        task = asyncio.create_task(
            self._debounced_message_extraction(event, event_id)
        )
        self._extraction_tasks.add(task)
        task.add_done_callback(self._extraction_tasks.discard)

    async def _debounced_message_extraction(self, event: Any, event_id: str) -> None:
        try:
            await asyncio.sleep(self.message_debounce_seconds)
            await self._apply_extraction(event.content, "message", event_id)
        except asyncio.CancelledError:
            raise

    async def _apply_extraction(
        self, content: str, trigger_type: str, trigger_ref: str
    ) -> None:
        if not await self._budget_available(f"extraction:{trigger_type}"):
            return
        current_state = await self.state_manager.get_full_state()
        result = await self.extractor.extract(content, current_state, trigger_type)
        if not getattr(result, "success", False):
            print(
                f"Extraction failed ({trigger_type}): {getattr(result, 'error', 'no patch')}"
            )
            return
        if result.patch is None:
            return
        await self.state_manager.apply_patch(
            result.patch,
            PatchSource(trigger_type=trigger_type, trigger_ref=trigger_ref),
        )

    async def _store_coaching(self, event: CoachingEvent) -> str:
        coaching_id = f"coaching-{uuid.uuid4()}"
        await self.state_manager.store_coaching(
            coaching_id,
            event.coaching_type,
            event.content,
            False,
        )
        return coaching_id

    async def _dispatch_command(self, command: Command) -> None:
        handlers = {
            "preview": self._command_preview,
            "status": self._command_status,
            "state": self._command_state,
            "ledger": self._command_ledger,
            "intel": self._command_intel,
            "divergences": self._command_divergences,
            "edits": self._command_edits,
            "commands": self._command_commands,
            "block": self._command_block,
        }
        handler = handlers.get(command.name)
        if handler is None:
            await self._send_operator(f"Unsupported command: /{command.name}")
            return
        reply = await handler(command)
        if reply is not None:
            await self._send_operator(reply)

    async def _command_preview(self, _command: Command) -> str | None:
        await self.run_response_pipeline()
        return None

    async def _command_status(self, _command: Command) -> str:
        coaching_count = len(await self._query_state("coaching", {"consumed": False}))
        return "\n".join(
            [
                "Status",
                f"Faction: {self.faction_id}",
                f"Round: {self.current_round}",
                f"State: running={self._running}",
                f"Unconsumed coaching: {coaching_count}",
            ]
        )

    async def _command_state(self, _command: Command) -> str:
        state = await self.state_manager.get_full_state()
        return "State\n" + json.dumps(state, indent=2, sort_keys=True)

    async def _command_ledger(self, _command: Command) -> str:
        return "\n".join(
            [
                "Ledger",
                f"Per-round budget: ${self.cost_config['per_round_budget_usd']:.2f}",
                f"Session budget: ${self.cost_config['session_budget_usd']:.2f}",
            ]
        )

    async def _command_intel(self, _command: Command) -> str:
        rows = await self._query_state("intelligence", {})
        return "Intelligence\n" + self._format_rows(rows)

    async def _command_divergences(self, _command: Command) -> str:
        rows = await self._query_state("intelligence", {})
        divergences: list[Any] = []
        for row in rows:
            analysis = self._json_from_row(row, "analysis_json")
            if isinstance(analysis.get("divergences"), list):
                divergences.extend(analysis["divergences"])
        if not divergences:
            return "Divergences\n(none)"
        return "Divergences\n" + json.dumps(divergences, indent=2, sort_keys=True)

    async def _command_edits(self, _command: Command) -> str:
        rows = await self._query_state("review_gate_edits", {})
        return "Review Edits\n" + self._format_rows(rows)

    async def _command_commands(self, _command: Command) -> str:
        return "\n".join([
            "Commands",
            "/commands — show this list",
            "/preview — generate a response draft",
            "/status — faction, round, coaching count",
            "/state — current game state (JSON)",
            "/ledger — cost budget info",
            "/intel — latest intelligence report",
            "/divergences — analyst disagreements",
            "/edits — review gate edit log",
            "/approve — approve pending draft",
            "/edit: <text> — approve with modified text",
            "/block — reject pending draft",
            "",
            "Coaching tags:",
            "PRIORITY: — set compass for next round",
            "CONSTRAINT: — hard boundary",
            "INTEL: — factual correction → state update",
            "TONE: — behavioral adjustment",
            "WATCH: — attention direction",
            "(untagged) — free coaching",
        ])

    async def _command_block(self, _command: Command) -> str:
        return "Block received. Pending review drafts should be blocked in the review gate."

    async def _query_state(
        self, entity_type: str, filters: dict[str, Any]
    ) -> list[dict[str, Any]]:
        try:
            return await self.state_manager.query(entity_type, filters)
        except Exception:
            return []

    async def _send_operator(self, content: str) -> None:
        await self.transport.send(OutboundMessage(content=content, channel="coaching"))

    async def _time_round_loop(self) -> None:
        interval = float(self.round_detection["interval_seconds"])
        while self._running:
            await asyncio.sleep(interval)
            await self.handle_round_boundary()

    async def _check_round_boundary(self, event: Any) -> bool:
        if self.round_detection["mode"] != "signal":
            return False
        pattern = self.round_detection["pattern"]
        if re.search(pattern, event.content):
            await self.handle_round_boundary()
            return True
        return False

    async def handle_round_boundary(self) -> None:
        state = await self.state_manager.get_full_state()
        recent_events = await self._recent_events()

        # Post-round state reconciliation: dedup, fulfillment, inconsistencies.
        await self._reconcile_state(state, recent_events)

        # Re-read state after reconciliation for analyst input.
        state = await self.state_manager.get_full_state()

        if not await self._budget_available("analyst:primary"):
            return
        if not await self._budget_available("analyst:secondary"):
            return
        primary_result, secondary_result = await asyncio.gather(
            self.primary_analyst.analyze(state, recent_events=recent_events),
            self.secondary_analyst.analyze(state, recent_events=recent_events),
        )
        if not getattr(primary_result, "success", False):
            await self._send_operator("Primary analyst failed; round analysis skipped.")
            return

        divergences: list[Divergence] = []
        if getattr(secondary_result, "success", False):
            divergences = list(self.divergence(primary_result, secondary_result))
        else:
            await self._send_operator(
                "Secondary analyst failed; proceeding with primary analysis only."
            )

        await self._store_intelligence(primary_result, secondary_result, divergences)
        self.current_round += 1
        await self._set_game_state("round_number", str(self.current_round))
        self._reset_round_budget()

    async def run_response_pipeline(
        self, trigger_event: InboundEvent | None = None
    ) -> bool:
        persona_prompt = await self.persona.get_base_prompt()
        round_context = await self.persona.build_round_context(
            self.current_round,
            None,
            await self._coaching_context(),
        )
        context = await self.context_assembler.assemble(
            persona_prompt=persona_prompt,
            round_context=round_context,
            intelligence=await self._latest_intelligence(),
            divergences=await self._latest_divergences(),
            recent_events=await self._recent_events(),
            free_coaching=await self._free_coaching_entries(),
            review_gate_enabled=self.feature_flags["review_gate"]["enabled"],
        )

        if not await self._budget_available("generation"):
            return False
        draft = await self.generator.generate(context)
        if not draft.success:
            await asyncio.sleep(0)
            if not await self._budget_available("generation:retry"):
                return False
            draft = await self.generator.generate(context)
        if not draft.success:
            await self._send_operator(f"Generation failed: {draft.error}")
            return False

        adversarial_result = None
        if self.feature_flags["adversarial"]["enabled"]:
            if not await self._budget_available("adversarial"):
                return False
            adversarial_result = await self.adversarial.read(draft.response_text or "")
            if not getattr(adversarial_result, "success", False):
                await self._send_operator("Adversarial read failed; continuing.")
        await self._store_adversarial_read(adversarial_result)

        decision = await self.review_gate.submit(
            draft,
            adversarial_result,
            self.current_round,
        )
        if getattr(decision, "action", None) == "blocked":
            await self._send_operator("Draft blocked.")
            return False
        final_text = getattr(decision, "final_text", None)
        if not isinstance(final_text, str) or not final_text.strip():
            await self._send_operator("Review gate returned no sendable text.")
            return False

        message = OutboundMessage(content=final_text.strip(), channel="public")
        for attempt in range(3):
            try:
                await self.transport.send(message)
                await self._mark_coaching_consumed()
                return True
            except Exception:
                if attempt == 2:
                    await self._send_operator("Transport send failed after 3 attempts.")
                    return False
                await asyncio.sleep(0)
        return False

    def _is_direct_address(self, event: Any) -> bool:
        return (
            event.channel == "public"
            and self.faction_id.lower() in event.content.lower()
        )

    def _build_cost_accountant(self, factory: Any | None) -> Any | None:
        if factory is not None:
            return factory(self.cost_config)
        try:
            from toolkit.cost_accountant import CostAccountant
        except ImportError:
            return None
        from adapters import DiplomatCostGate

        accountant = CostAccountant(
            ledger_path=self._path(
                self.cost_config.get("ledger_path", "data/cost_ledger.jsonl")
            ),
        )
        return DiplomatCostGate(
            accountant,
            per_round_budget_usd=self.cost_config["per_round_budget_usd"],
        )

    def _reset_round_budget(self) -> None:
        if self.cost_accountant is None:
            return
        for method_name in ("reset_round_budget", "start_round", "reset"):
            method = getattr(self.cost_accountant, method_name, None)
            if method is not None:
                result = method(self.cost_config["per_round_budget_usd"])
                if isawaitable(result):
                    raise PipelineConfigError(
                        f"Cost accountant {method_name} must be synchronous"
                    )
                return

    async def _budget_available(self, operation: str) -> bool:
        if self.cost_accountant is None:
            return True
        checker = getattr(self.cost_accountant, "available_budget", None)
        if checker is None:
            return True
        remaining = await _maybe_await(checker())
        if remaining is None or remaining > 0:
            return True
        await self._send_operator(
            f"Cost budget exceeded before {operation}; skipping LLM call."
        )
        return False

    async def _coaching_context(self) -> CoachingContext:
        rows = await self._query_state("coaching", {"consumed": False})
        buckets = {
            "PRIORITY": [],
            "CONSTRAINT": [],
            "WATCH": [],
            "TONE": [],
        }
        for row in rows:
            tag = str(row.get("tag", "")).upper()
            if tag in buckets:
                buckets[tag].append(str(row.get("content", "")))
        return CoachingContext(
            priorities=buckets["PRIORITY"],
            constraints=buckets["CONSTRAINT"],
            watch_items=buckets["WATCH"],
            tone_notes=buckets["TONE"],
        )

    async def _latest_intelligence(self) -> dict[str, Any]:
        rows = await self._query_state("intelligence", {})
        if not rows:
            return {}
        return self._json_from_row(rows[-1], "analysis_json")

    async def _latest_divergences(self) -> list[Divergence]:
        latest = await self._latest_intelligence()
        raw = latest.get("divergences")
        if not isinstance(raw, list):
            return []
        divergences: list[Divergence] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            try:
                divergences.append(
                    Divergence(
                        field=str(item.get("field", "")),
                        primary_value=str(item.get("primary_value", "")),
                        secondary_value=str(item.get("secondary_value", "")),
                        note=str(item.get("note", "")),
                    )
                )
            except TypeError:
                continue
        return divergences

    async def _recent_events(self) -> list[Any]:
        query = getattr(self.event_store, "query", None)
        if query is None:
            return []
        return await query(EventFilter(limit=30))

    async def _free_coaching_entries(self) -> list[CoachingEntry]:
        rows = await self._query_state("coaching", {"consumed": False})
        entries: list[CoachingEntry] = []
        now = datetime.now(timezone.utc)
        for row in rows:
            entries.append(
                CoachingEntry(
                    coaching_type=str(row.get("tag", "FREE")),
                    content=str(row.get("content", "")),
                    timestamp=now,
                )
            )
        return entries

    async def _store_intelligence(
        self,
        primary_result: Any,
        secondary_result: Any,
        divergences: list[Divergence],
    ) -> None:
        payload = {
            "primary": self._public_data(primary_result),
            "secondary": self._public_data(secondary_result),
            "divergences": [self._public_data(item) for item in divergences],
        }
        await self.state_manager.store_intelligence(
            self.current_round,
            "orchestrator",
            payload,
        )

    async def _set_game_state(self, key: str, value: str) -> None:
        await self.state_manager.set_game_state(key, value)

    async def _store_adversarial_read(self, adversarial_result: Any) -> None:
        if adversarial_result is None:
            return
        payload = self._public_data(adversarial_result)
        await self.state_manager.store_adversarial_read(self.current_round, payload)

    async def _mark_coaching_consumed(self) -> None:
        await self.state_manager.mark_coaching_consumed()

    async def _reconcile_state(
        self, state: dict[str, Any], recent_events: list[Any]
    ) -> None:
        """Run post-round state reconciliation if a reconciler is available."""
        reconciler = getattr(self, "reconciler", None)
        if reconciler is None:
            return
        if not await self._budget_available("reconciliation"):
            return
        try:
            result = await reconciler.reconcile(
                state, recent_events, self.current_round
            )
        except Exception as exc:
            print(f"Reconciliation failed: {exc}")
            return
        if not result.success:
            print(f"Reconciliation failed: {result.error}")
            return

        # Apply merge: remove duplicate promise IDs from state.
        for merge in result.merged_promises:
            for remove_id in merge.get("remove_ids", []):
                try:
                    await self.state_manager.delete_entity("promises", remove_id)
                except Exception:
                    pass

        # Apply status updates.
        for update in result.updated_statuses:
            try:
                await self.state_manager.update_promise_status(
                    update["promise_id"],
                    update["new_status"],
                    update.get("resolution", ""),
                )
            except Exception:
                pass

        # Add new inconsistencies.
        for incon in result.new_inconsistencies:
            incon_with_id = dict(incon)
            if "inconsistency_id" not in incon_with_id:
                incon_with_id["inconsistency_id"] = (
                    f"recon-{incon.get('faction_id', 'unknown')}-r{self.current_round}"
                )
            try:
                from modules.types import StatePatch
                await self.state_manager.apply_patch(
                    StatePatch({"inconsistencies": [incon_with_id]}),
                    PatchSource(
                        trigger_type="reconciliation",
                        trigger_ref=f"round-{self.current_round}",
                    ),
                )
            except Exception:
                pass

        # Add missed proposals as new promises.
        for proposal in result.missed_proposals:
            try:
                from modules.types import StatePatch
                await self.state_manager.apply_patch(
                    StatePatch({"promises": [proposal]}),
                    PatchSource(
                        trigger_type="reconciliation",
                        trigger_ref=f"round-{self.current_round}",
                    ),
                )
            except Exception:
                pass

        if result.merge_log:
            log_text = "\n".join(f"  - {entry}" for entry in result.merge_log)
            print(f"Reconciliation (round {self.current_round}):\n{log_text}")

    @staticmethod
    def _public_data(value: Any) -> Any:
        if is_dataclass(value):
            return Orchestrator._public_data(asdict(value))
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, dict):
            return {key: Orchestrator._public_data(item) for key, item in value.items()}
        if isinstance(value, list):
            return [Orchestrator._public_data(item) for item in value]
        return value

    @staticmethod
    def _format_rows(rows: list[dict[str, Any]]) -> str:
        if not rows:
            return "(none)"
        return json.dumps(rows, indent=2, sort_keys=True)

    @staticmethod
    def _json_from_row(row: dict[str, Any], key: str) -> dict[str, Any]:
        value = row.get(key)
        if isinstance(value, dict):
            return value
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
            except json.JSONDecodeError:
                return {}
            return parsed if isinstance(parsed, dict) else {}
        return {}

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
            for key in ("provider", "api_key_env"):
                if not self._has_text(provider_config.get(key)):
                    raise PipelineConfigError(
                        f"Pipeline config requires llm_providers.{provider_id}.{key}"
                    )
            models = provider_config.get("models")
            if isinstance(models, dict):
                models_dict = dict(models)
            elif self._has_text(provider_config.get("model")):
                single_model = str(provider_config["model"])
                models_dict = {
                    "quality": single_model,
                    "default": single_model,
                    "commodity": single_model,
                }
            else:
                raise PipelineConfigError(
                    f"Pipeline config requires llm_providers.{provider_id}.models "
                    f"(dict of tier->model) or .model (single model string)"
                )
            configs[str(provider_id)] = {
                "provider": provider_config["provider"],
                "models": models_dict,
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


async def _maybe_await(value: Any) -> Any:
    if isawaitable(value):
        return await value
    return value


__all__ = ["Orchestrator", "PipelineConfigError", "PipelinePaths"]
