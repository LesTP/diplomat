from __future__ import annotations

from inspect import isawaitable
from types import SimpleNamespace
from typing import Any

from logging_config import get_logger
from modules.context_assembler import DecisionContext
from modules.generation import GenerationResult
from modules.types import InboundEvent


logger = get_logger(__name__)


class Pipeline:
    """Per-agent capability surface backed by the existing Orchestrator."""

    def __init__(self, orchestrator: Any) -> None:
        self.orchestrator = orchestrator

    async def start(self) -> None:
        await self.orchestrator.start()

    async def shutdown(self) -> None:
        await self.orchestrator.shutdown()

    async def store_event(self, event: InboundEvent) -> str:
        event_id = await self.orchestrator.event_store.append(
            event,
            self.orchestrator.current_round,
        )
        logger.debug(
            "event.stored event_id=%s round=%s sender_faction=%s channel=%s",
            event_id,
            self.orchestrator.current_round,
            event.sender_faction,
            event.channel,
        )
        return event_id

    async def extract_from(
        self, event: InboundEvent, event_id: str | None = None
    ) -> str:
        stored_event_id = event_id or await self.store_event(event)
        logger.debug(
            "extraction.delegated event_id=%s sender_faction=%s channel=%s",
            stored_event_id,
            event.sender_faction,
            event.channel,
        )
        await self.orchestrator._apply_extraction(
            event.content,
            "message",
            stored_event_id,
        )
        return stored_event_id

    async def dispatch_operator(
        self, content: str, event_id: str = "operator-dispatch"
    ) -> None:
        review_gate = getattr(self.orchestrator, "review_gate", None)
        if review_gate is not None and content.strip().startswith("/"):
            handle_command = getattr(review_gate, "handle_command", None)
            if handle_command is not None:
                consumed = await handle_command(content.strip())
                if consumed:
                    return
        event = SimpleNamespace(content=content)
        await self.orchestrator._route_operator_event(event, event_id)

    async def regenerate_with_directive(
        self, directive: str, previous_draft: str
    ) -> GenerationResult:
        context = await self.orchestrator._build_decision_context()
        revised_context = DecisionContext(
            system_prompt=context.system_prompt,
            user_prompt="\n\n".join(
                [
                    context.user_prompt,
                    f"[OPERATOR REVISION DIRECTIVE]: {directive.strip()}",
                    (
                        "[PREVIOUS DRAFT — REVISE PER DIRECTIVE]: "
                        f"{previous_draft.strip()}"
                    ),
                ]
            ),
            metadata=dict(context.metadata),
        )
        return await self.orchestrator.generator.generate(
            revised_context,
            purpose="generation_revision",
            attribution=self.orchestrator.faction_id,
        )

    def advance_to_round(self, round_number: int) -> None:
        self.orchestrator.advance_to_round(round_number)

    async def reconcile_and_analyze(self) -> None:
        await self.orchestrator.handle_round_boundary()

    async def run_response(self, trigger_event: InboundEvent | None = None) -> bool:
        return await self.orchestrator.run_response_pipeline(
            trigger_event=trigger_event
        )

    async def get_state(self) -> dict[str, Any]:
        return await self.orchestrator.state_manager.get_full_state()

    async def get_intelligence(self) -> dict[str, Any]:
        return await self.orchestrator._latest_intelligence()

    async def get_ledger(self) -> dict[str, Any]:
        checker = getattr(self.orchestrator.cost_accountant, "available_budget", None)
        available_budget = None
        if checker is not None:
            available_budget = checker()
            if isawaitable(available_budget):
                available_budget = await available_budget
        return {
            "current_round": self.orchestrator.current_round,
            "per_round_budget_usd": self.orchestrator.cost_config[
                "per_round_budget_usd"
            ],
            "session_budget_usd": self.orchestrator.cost_config[
                "session_budget_usd"
            ],
            "available_budget_usd": available_budget,
        }


__all__ = ["Pipeline"]
