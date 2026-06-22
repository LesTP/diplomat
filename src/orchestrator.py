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

from logging_config import get_logger
from toolkit.coaching import CoachingEvent, Command
from modules.context_assembler import CoachingEntry, DecisionContext
from modules.edit_classifier import build_edit_classifier
from modules.generation import GenerationResult
from modules.persona import CoachingContext
from modules.transport import OutboundMessage
from modules.types import Divergence, EventFilter, InboundEvent, PatchSource
from pipeline import Pipeline
from flows.event_driven import (
    EventDrivenFlow,
    faction_address_detector,
    signal_round_detector,
)
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

REQUIRED_MODULES = (
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
)
logger = get_logger(__name__)


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
    extraction_examples: Path
    state_patch_schema: Path
    intelligence_schema: Path
    adversarial_schema: Path


@dataclass(frozen=True)
class OrchestrationOptions:
    auto_response_enabled: bool = True
    total_rounds: int | None = None
    bare_mode: bool = False

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> "OrchestrationOptions":
        total_rounds: int | None = None
        game_config = config.get("game")
        if isinstance(game_config, dict):
            total_rounds_value = game_config.get("total_rounds")
            if isinstance(total_rounds_value, int) and total_rounds_value > 0:
                total_rounds = total_rounds_value
        return cls(total_rounds=total_rounds)

    @classmethod
    def from_config_path(
        cls, config_path: str | Path
    ) -> "OrchestrationOptions":
        try:
            config = yaml.safe_load(Path(config_path).read_text(encoding="utf-8"))
        except OSError as exc:
            raise PipelineConfigError(
                f"Unable to read pipeline config: {config_path}"
            ) from exc
        if not isinstance(config, dict):
            return cls()
        return cls.from_config(config)


class _OrchestratorCore:
    def __init__(
        self,
        config_path: str | Path = "config/pipeline.yaml",
        *,
        options: OrchestrationOptions | None = None,
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
        self.options = options or OrchestrationOptions.from_config(self.config)
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
        self._edit_classifier = None
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
        if self.options.auto_response_enabled and self._is_direct_address(event):
            await self.run_response_pipeline(trigger_event=event)
        return event_id

    def advance_to_round(self, round_number: int) -> None:
        if not isinstance(round_number, int) or round_number < 1:
            raise ValueError("round_number must be a positive integer")
        self.current_round = round_number
        self._reset_round_budget()

    async def _route_operator_event(self, event: Any, event_id: str) -> None:
        if event.content.strip().lower() == "/edits-summary":
            await self._dispatch_command(Command(name="edits-summary", args={}))
            return
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
            logger.info(
                "extraction.skip trigger_type=%s trigger_ref=%s reason=budget",
                trigger_type,
                trigger_ref,
            )
            return
        logger.info(
            "extraction.start trigger_type=%s trigger_ref=%s content_length=%s",
            trigger_type,
            trigger_ref,
            len(content),
        )
        current_state = await self.state_manager.get_full_state()
        result = await self.extractor.extract(content, current_state, trigger_type)
        if not getattr(result, "success", False):
            logger.warning(
                "extraction.skip trigger_type=%s trigger_ref=%s reason=failed error=%s",
                trigger_type,
                trigger_ref,
                getattr(result, "error", "no patch"),
            )
            return
        if result.patch is None:
            logger.info(
                "extraction.skip trigger_type=%s trigger_ref=%s reason=no_patch",
                trigger_type,
                trigger_ref,
            )
            return
        await self.state_manager.apply_patch(
            result.patch,
            PatchSource(trigger_type=trigger_type, trigger_ref=trigger_ref),
        )
        logger.info(
            "extraction.complete trigger_type=%s trigger_ref=%s patch=%s",
            trigger_type,
            trigger_ref,
            _patch_summary(result.patch),
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
            "edits-summary": self._command_edits_summary,
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
        logger.info("pipeline.trigger trigger=preview_command")
        asyncio.create_task(self.run_response_pipeline())
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
        if not rows:
            return "Intelligence\n(none)"

        latest = self._latest_intelligence_row(rows)
        analysis = self._json_from_row(latest, "analysis_json")
        report = self._intelligence_report(analysis)
        leverage_points = self._intelligence_items(
            report,
            keys=("key_leverage_points",),
            limit=3,
        )
        risks = self._intelligence_risks(analysis, report, limit=3)
        threat_level = report.get("threat_level")
        threat_text = f"{threat_level}/5" if isinstance(threat_level, int) else "unknown"
        round_number = latest.get("round_number", "unknown")

        return "\n".join(
            [
                "Intelligence",
                f"Faction: {self.faction_id}",
                f"Round: {round_number}",
                f"Threat: {threat_text}",
                "Leverage points:",
                *self._bullet_lines(leverage_points),
                "Risks:",
                *self._bullet_lines(risks),
            ]
        )

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

    async def _command_edits_summary(self, _command: Command) -> str:
        edit_rows = await self._query_state("review_gate_edits", {})
        classifications = await self._get_edit_classifications()
        classified_ids = {
            row.get("review_gate_edit_id")
            for row in classifications
            if row.get("review_gate_edit_id") is not None
        }

        pending_rows = [
            row
            for row in edit_rows
            if row.get("decision") == "edited" and row.get("id") not in classified_ids
        ]
        if pending_rows:
            classifier = await self._get_edit_classifier()
            if classifier is None:
                logger.info("edit_summary.skip reason=classifier_unavailable")
            else:
                for row in pending_rows:
                    original_text = self._edit_original_text(row)
                    edited_text = self._edit_edited_text(row)
                    edit_notes = self._edit_notes(row)
                    classification = await classifier.classify(
                        original_text,
                        edited_text,
                        edit_notes,
                    )
                    await self.state_manager.store_edit_classification(
                        row["id"],
                        classification,
                    )
                classifications = await self._get_edit_classifications()

        return self._format_edit_summary(classifications)

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
            "/edits-summary — classify and summarize edit patterns",
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

    async def _get_edit_classifier(self) -> Any | None:
        classifier = getattr(self, "_edit_classifier", None)
        if classifier is not None:
            return classifier
        generator = getattr(self, "generator", None)
        llm_client = getattr(generator, "llm_client", None)
        if llm_client is None:
            return None
        classifier = build_edit_classifier(
            llm_client,
            self.config["llm_providers"],
            tier="commodity",
            attribution=self.faction_id,
        )
        self._edit_classifier = classifier
        return classifier

    async def _get_edit_classifications(self) -> list[dict[str, Any]]:
        getter = getattr(self.state_manager, "get_edit_classifications", None)
        if callable(getter):
            try:
                return await getter()
            except Exception:
                logger.exception("Failed to load edit classifications")
                return []
        return await self._query_state("edit_classifications", {})

    def _edit_original_text(self, row: dict[str, Any]) -> str:
        original_text = row.get("original_text")
        if isinstance(original_text, str) and original_text.strip():
            return original_text.strip()
        return "[original draft unavailable]"

    def _edit_edited_text(self, row: dict[str, Any]) -> str:
        edited_text = row.get("edited_text")
        if isinstance(edited_text, str) and edited_text.strip():
            return edited_text.strip()
        edit_text = row.get("edit_text")
        if isinstance(edit_text, str) and edit_text.strip():
            return edit_text.strip()
        return ""

    def _edit_notes(self, row: dict[str, Any]) -> str | None:
        revise_directives = row.get("revise_directives")
        if isinstance(revise_directives, list) and revise_directives:
            notes = ", ".join(
                str(item).strip() for item in revise_directives if str(item).strip()
            )
            if notes:
                return notes
        edit_text = row.get("edit_text")
        if isinstance(edit_text, str) and edit_text.strip():
            return edit_text.strip()
        return None

    def _truncate_text(self, text: str | None, limit: int = 80) -> str:
        if not text:
            return "[none]"
        value = text.strip()
        if len(value) <= limit:
            return value
        return value[: limit - 1].rstrip() + "…"

    def _format_edit_summary(self, rows: list[dict[str, Any]]) -> str:
        if not rows:
            return "Edit Summary\n(none)"

        grouped: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            category = str(row.get("category", "unknown"))
            grouped.setdefault(category, []).append(row)

        lines = [
            "Edit Summary",
            "| Category | Count | Most recent example |",
            "| --- | ---: | --- |",
        ]
        for category in sorted(grouped):
            category_rows = grouped[category]
            latest = max(
                category_rows,
                key=lambda row: (
                    str(row.get("classified_at", "")),
                    int(row.get("id", 0) or 0),
                ),
            )
            original_text = self._truncate_text(latest.get("original_text"))
            edited_text = self._truncate_text(latest.get("edited_text"))
            lines.append(
                "| {category} | {count} | original: {original} / edited: {edited} |".format(
                    category=category,
                    count=len(category_rows),
                    original=original_text,
                    edited=edited_text,
                )
            )
        return "\n".join(lines)

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
        previous_round = self.current_round
        logger.info("round.boundary round=%s stage=start", previous_round)
        state = await self.state_manager.get_full_state()
        recent_events = await self._recent_events()

        # Post-round state reconciliation: dedup, fulfillment, inconsistencies.
        logger.info(
            "round.boundary round=%s stage=reconciliation events=%s",
            previous_round,
            len(recent_events),
        )
        await self._reconcile_state(state, recent_events)

        # Re-read state after reconciliation for analyst input.
        state = await self.state_manager.get_full_state()

        if not await self._budget_available("analyst:primary"):
            logger.info(
                "round.boundary round=%s stage=analyst_skip reason=primary_budget",
                previous_round,
            )
            return
        if not await self._budget_available("analyst:secondary"):
            logger.info(
                "round.boundary round=%s stage=analyst_skip reason=secondary_budget",
                previous_round,
            )
            return
        logger.info("round.boundary round=%s stage=analyst_start", previous_round)
        primary_result, secondary_result = await asyncio.gather(
            self.primary_analyst.analyze(state, recent_events=recent_events),
            self.secondary_analyst.analyze(state, recent_events=recent_events),
        )
        if not getattr(primary_result, "success", False):
            logger.warning(
                "round.boundary round=%s stage=analyst_failed provider=primary",
                previous_round,
            )
            await self._send_operator("Primary analyst failed; round analysis skipped.")
            return

        divergences: list[Divergence] = []
        if getattr(secondary_result, "success", False):
            divergences = list(self.divergence(primary_result, secondary_result))
        else:
            logger.warning(
                "round.boundary round=%s stage=analyst_failed provider=secondary",
                previous_round,
            )
            await self._send_operator(
                "Secondary analyst failed; proceeding with primary analysis only."
            )

        await self._store_intelligence(primary_result, secondary_result, divergences)
        self.current_round += 1
        await self._set_game_state("round_number", str(self.current_round))
        self._reset_round_budget()
        logger.info(
            "round.boundary round=%s stage=complete next_round=%s divergences=%s",
            previous_round,
            self.current_round,
            len(divergences),
        )

    async def run_response_pipeline(
        self, trigger_event: InboundEvent | None = None
    ) -> bool:
        trigger = "direct_address" if trigger_event is not None else "manual"
        logger.info(
            "pipeline.trigger trigger=%s round=%s sender_faction=%s",
            trigger,
            self.current_round,
            getattr(trigger_event, "sender_faction", None),
        )
        context = await self._build_decision_context()

        if not await self._budget_available("generation"):
            logger.info(
                "pipeline.complete trigger=%s success=False reason=budget_generation",
                trigger,
            )
            return False
        draft = await self.generator.generate(
            context,
            purpose="generation",
            attribution=self.faction_id,
        )
        if not draft.success:
            await asyncio.sleep(0)
            if not await self._budget_available("generation:retry"):
                logger.info(
                    "pipeline.complete trigger=%s success=False reason=budget_generation_retry",
                    trigger,
                )
                return False
            draft = await self.generator.generate(
                context,
                purpose="generation",
                attribution=self.faction_id,
            )
        if not draft.success:
            logger.warning(
                "pipeline.complete trigger=%s success=False reason=generation_failed error=%s",
                trigger,
                draft.error,
            )
            await self._send_operator(f"Generation failed: {draft.error}")
            return False

        adversarial_result = None
        if self.feature_flags["adversarial"]["enabled"]:
            if not await self._budget_available("adversarial"):
                logger.info(
                    "pipeline.complete trigger=%s success=False reason=budget_adversarial",
                    trigger,
                )
                return False
            adversarial_result = await self.adversarial.read(draft.response_text or "")
            if not getattr(adversarial_result, "success", False):
                logger.warning(
                    "pipeline.stage trigger=%s stage=adversarial success=False",
                    trigger,
                )
                await self._send_operator("Adversarial read failed; continuing.")
        await self._store_adversarial_read(adversarial_result)

        decision = await self.review_gate.submit(
            draft,
            adversarial_result,
            self.current_round,
        )
        if getattr(decision, "action", None) == "blocked":
            logger.info(
                "pipeline.complete trigger=%s success=False reason=review_blocked",
                trigger,
            )
            await self._send_operator("Draft blocked.")
            return False
        final_text = getattr(decision, "final_text", None)
        if not isinstance(final_text, str) or not final_text.strip():
            logger.info(
                "pipeline.complete trigger=%s success=False reason=review_empty",
                trigger,
            )
            await self._send_operator("Review gate returned no sendable text.")
            return False

        message = OutboundMessage(content=final_text.strip(), channel="public")
        for attempt in range(3):
            try:
                await self.transport.send(message)
                await self._mark_coaching_consumed()
                logger.info(
                    "pipeline.complete trigger=%s success=True final_length=%s",
                    trigger,
                    len(final_text.strip()),
                )
                return True
            except Exception:
                if attempt == 2:
                    logger.warning(
                        "pipeline.complete trigger=%s success=False reason=transport_failed",
                        trigger,
                    )
                    await self._send_operator("Transport send failed after 3 attempts.")
                    return False
                await asyncio.sleep(0)
        return False

    async def _build_decision_context(self) -> DecisionContext:
        persona_prompt = await self.persona.get_base_prompt()
        round_context = await self.persona.build_round_context(
            self.current_round,
            None,
            await self._coaching_context(),
            total_rounds=self.options.total_rounds,
        )
        return await self.context_assembler.assemble(
            persona_prompt=persona_prompt,
            round_context=round_context,
            intelligence=await self._latest_intelligence(),
            divergences=await self._latest_divergences(),
            recent_events=await self._recent_events(),
            free_coaching=await self._free_coaching_entries(),
            review_gate_enabled=self.feature_flags["review_gate"]["enabled"],
            bare_mode=self.options.bare_mode,
        )

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
                except Exception as exc:
                    print(
                        "Reconciliation delete failed "
                        f"(promise_id={remove_id}): {exc}"
                    )

        # Apply status updates.
        for update in result.updated_statuses:
            try:
                await self.state_manager.update_promise_status(
                    update["promise_id"],
                    update["new_status"],
                    update.get("resolution", ""),
                )
            except Exception as exc:
                print(
                    "Reconciliation status update failed "
                    f"(promise_id={update.get('promise_id', 'unknown')}): {exc}"
                )

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
            except Exception as exc:
                print(
                    "Reconciliation inconsistency insert failed "
                    f"(inconsistency_id={incon_with_id.get('inconsistency_id', 'unknown')}): {exc}"
                )

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
            except Exception as exc:
                print(
                    "Reconciliation missed-proposal insert failed "
                    f"(promise_id={proposal.get('promise_id', 'unknown')}): {exc}"
                )

        if result.merge_log:
            log_text = "\n".join(f"  - {entry}" for entry in result.merge_log)
            print(f"Reconciliation (round {self.current_round}):\n{log_text}")

    @staticmethod
    def _public_data(value: Any) -> Any:
        if is_dataclass(value):
            return _OrchestratorCore._public_data(asdict(value))
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, dict):
            return {
                key: _OrchestratorCore._public_data(item)
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [_OrchestratorCore._public_data(item) for item in value]
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

    @staticmethod
    def _latest_intelligence_row(rows: list[dict[str, Any]]) -> dict[str, Any]:
        def sort_key(row: dict[str, Any]) -> tuple[int, datetime, int]:
            round_number = row.get("round_number")
            try:
                round_score = int(round_number)
            except (TypeError, ValueError):
                round_score = -1
            created_at = _OrchestratorCore._parse_timestamp(row.get("created_at"))
            provider = str(row.get("provider", "")).strip().lower()
            provider_score = 1 if provider == "primary" else 0
            return (round_score, created_at, provider_score)

        return max(rows, key=sort_key)

    @staticmethod
    def _parse_timestamp(value: Any) -> datetime:
        if isinstance(value, datetime):
            return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
        if not isinstance(value, str) or not value:
            return datetime.min.replace(tzinfo=timezone.utc)
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return datetime.min.replace(tzinfo=timezone.utc)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed

    @staticmethod
    def _intelligence_report(analysis: dict[str, Any]) -> dict[str, Any]:
        for branch_name in ("primary", "secondary"):
            branch = analysis.get(branch_name)
            if not isinstance(branch, dict):
                continue
            report = branch.get("report")
            if isinstance(report, dict):
                return report
        report = analysis.get("report")
        if isinstance(report, dict):
            return report
        return analysis

    @staticmethod
    def _intelligence_items(
        payload: dict[str, Any],
        *,
        keys: tuple[str, ...],
        limit: int,
    ) -> list[str]:
        items: list[str] = []
        for key in keys:
            value = payload.get(key)
            if isinstance(value, list):
                items.extend(
                    str(item).strip() for item in value if str(item).strip()
                )
            elif isinstance(value, str) and value.strip():
                items.append(value.strip())
        return _OrchestratorCore._unique_items(items)[:limit]

    @staticmethod
    def _intelligence_risks(
        analysis: dict[str, Any],
        report: dict[str, Any],
        *,
        limit: int,
    ) -> list[str]:
        items = _OrchestratorCore._intelligence_items(
            analysis,
            keys=("risks", "exploitable", "counter_moves"),
            limit=limit * 4,
        )
        if isinstance(analysis.get("divergences"), list):
            for divergence in analysis["divergences"]:
                if isinstance(divergence, dict):
                    note = divergence.get("note")
                    if isinstance(note, str) and note.strip():
                        items.append(note.strip())
                elif isinstance(divergence, str) and divergence.strip():
                    items.append(divergence.strip())
        if not items:
            summary = report.get("summary") or analysis.get("summary")
            if isinstance(summary, str) and summary.strip():
                items.append(summary.strip())
        return _OrchestratorCore._unique_items(items)[:limit]

    @staticmethod
    def _unique_items(items: list[str]) -> list[str]:
        unique: list[str] = []
        seen: set[str] = set()
        for item in items:
            if item in seen:
                continue
            seen.add(item)
            unique.append(item)
        return unique

    @staticmethod
    def _bullet_lines(items: list[str]) -> list[str]:
        if not items:
            return ["- (none)"]
        return [f"- {item}" for item in items]

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
        examples = paths.get("examples") if isinstance(paths.get("examples"), dict) else {}
        return PipelinePaths(
            coaching_routes=self._path(paths["coaching_routes"]),
            faction_prompt=self._path(paths["faction_prompt"]),
            state_updater_prompt=self._path(prompts["state_updater"]),
            analyst_prompt=self._path(prompts["analyst"]),
            generation_prompt=self._path(prompts["generation"]),
            adversarial_prompt=self._path(prompts["adversarial"]),
            extraction_examples=self._path(
                examples.get("extraction", "config/examples/extraction_examples.json")
            ),
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
            paths.extraction_examples,
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
                "temperature": provider_config.get("temperature", 0.7),
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
                built_modules=modules,
            )
        return modules

    def _build_module(
        self,
        name: str,
        config: dict[str, Any],
        *,
        llm_client: Any | None,
        telegram_client: Any | None,
        built_modules: dict[str, Any],
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
                self.paths.extraction_examples,
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
            if class_name == "OperatorReviewGate":
                transport = built_modules.get("transport")
                if transport is None:
                    raise PipelineConfigError(
                        "OperatorReviewGate requires the transport module"
                    )
                return cls(
                    transport,
                    max_message_chars=int(config.get("max_message_chars", 4000)),
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
        if not _OrchestratorCore._has_text(value):
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


def _patch_summary(patch: Any) -> str:
    data = getattr(patch, "data", None)
    if not isinstance(data, dict):
        return "unknown"
    parts = []
    for key, value in sorted(data.items()):
        if isinstance(value, list):
            parts.append(f"{key}:{len(value)}")
        else:
            parts.append(f"{key}:1")
    return ",".join(parts) if parts else "empty"


def Orchestrator(*args: Any, **kwargs: Any) -> EventDrivenFlow:
    core = _OrchestratorCore(*args, **kwargs)
    round_detector = None
    round_interval_seconds = None
    if core.round_detection["mode"] == "signal":
        round_detector = signal_round_detector(core.round_detection["pattern"])
    elif core.round_detection["mode"] == "time":
        round_interval_seconds = float(core.round_detection["interval_seconds"])

    address_detector = None
    if core.options.auto_response_enabled:
        address_detector = faction_address_detector(core.faction_id)

    return EventDrivenFlow(
        pipeline=Pipeline(core),
        transport=core.transport,
        round_detector=round_detector,
        address_detector=address_detector,
        message_debounce_seconds=core.message_debounce_seconds,
        round_interval_seconds=round_interval_seconds,
    )


__all__ = [
    "OrchestrationOptions",
    "Orchestrator",
    "PipelineConfigError",
    "PipelinePaths",
]
