"""Multi-agent self-play game environment.

Spins up N Orchestrator instances with TestTransport, routes messages
between agents, manages round lifecycle, and collects results.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import time
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from modules.types import InboundEvent
from flows.round_stepped import RoundSteppedFlow
from orchestrator import OrchestrationOptions, Orchestrator
from tests.helpers.test_transport import TestTransport
from tests.self_play.scenario import ROUND_UPDATES as DEFAULT_ROUND_UPDATES
from tests.self_play.scenario import SEED_MESSAGE as DEFAULT_SEED_MESSAGE


# ------------------------------------------------------------------
# LLM call logging
# ------------------------------------------------------------------


@dataclass
class LLMCallRecord:
    """One logged LLM API call."""

    timestamp: str
    faction_id: str
    call_index: int
    messages: list[dict[str, str]]
    config_provider: str
    tier: str | None
    max_tokens: int | None
    response: str
    duration_seconds: float
    error: str | None = None


class LoggingLLMClient:
    """Wraps an LLM client and records every call with full detail."""

    def __init__(self, inner: Any) -> None:
        self._inner = inner
        self.call_log: list[LLMCallRecord] = []
        self._call_index = 0
        self._current_faction: str = "unknown"

    def set_faction(self, faction_id: str) -> None:
        self._current_faction = faction_id

    async def complete(self, **kwargs: Any) -> str:
        messages = kwargs.get("messages", [])
        config = kwargs.get("config", {})
        tier = kwargs.get("tier")
        max_tokens = kwargs.get("max_tokens")
        faction_at_start = kwargs.get("attribution") or self._current_faction

        start = time.monotonic()
        error = None
        response = ""
        try:
            result = self._inner.complete(**kwargs)
            if asyncio.iscoroutine(result):
                result = await result
            response = result
            return response
        except Exception as exc:
            error = str(exc)
            raise
        finally:
            duration = time.monotonic() - start
            self._call_index += 1
            self.call_log.append(
                LLMCallRecord(
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    faction_id=faction_at_start,
                    call_index=self._call_index,
                    messages=_safe_messages(messages),
                    config_provider=config.get("provider", "?"),
                    tier=str(tier) if tier else None,
                    max_tokens=max_tokens,
                    response=response if isinstance(response, str) else str(response),
                    duration_seconds=round(duration, 3),
                    error=error,
                )
            )

    def to_dicts(self) -> list[dict[str, Any]]:
        """Serialize all call records for JSON output."""
        records = []
        for r in self.call_log:
            records.append(
                {
                    "timestamp": r.timestamp,
                    "faction_id": r.faction_id,
                    "call_index": r.call_index,
                    "messages": r.messages,
                    "config_provider": r.config_provider,
                    "tier": r.tier,
                    "max_tokens": r.max_tokens,
                    "response": r.response,
                    "duration_seconds": r.duration_seconds,
                    "error": r.error,
                }
            )
        return records


def _safe_messages(messages: Any) -> list[dict[str, str]]:
    """Normalize messages to a JSON-safe list of dicts."""
    if not isinstance(messages, list):
        return [{"raw": str(messages)}]
    result = []
    for m in messages:
        if isinstance(m, dict):
            result.append({k: str(v) for k, v in m.items()})
        else:
            result.append({"role": getattr(m, "role", "?"), "content": getattr(m, "content", str(m))})
    return result


# ---------------------------------------------------------------------------
# Provider routing helpers
# ---------------------------------------------------------------------------

_PROVIDER_API_KEY_ENV: dict[str, str] = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "google": "GOOGLE_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
}

# Default primary provider config for self-play subsystem calls (reconciler, scorer).
# Uses the same env vars as _generate_faction_config so operator overrides apply.
_SELF_PLAY_PRIMARY: dict[str, Any] = {
    "provider": "openai",
    "models": {"commodity": "gpt-4.1-mini"},
    "api_key_env": "OPENAI_API_KEY",
}


def _api_key_env_for(provider: str) -> str:
    """Return the env var name that holds the API key for a given provider."""
    return _PROVIDER_API_KEY_ENV.get(provider, "OPENAI_API_KEY")


@dataclass
class AgentHandle:
    """Runtime state for a single agent in the simulation."""

    faction_id: str
    orchestrator: Orchestrator
    transport: TestTransport
    task: asyncio.Task[None]


class GameEnvironment:
    """Coordinate a multi-agent self-play simulation."""

    def __init__(
        self,
        faction_personas: dict[str, Path],
        *,
        llm_client: Any,
        cost_accountant: Any,
        base_path: Path,
        tmp_dir: Path,
        extra_module_overrides: dict[str, Any] | None = None,
        seed_message: str | None = None,
        round_updates: dict[int, str] | None = None,
        scenario_analysis: dict[str, Any] | None = None,
        per_faction_providers: dict[str, dict[str, str]] | None = None,
        bare_mode: bool = False,
    ) -> None:
        self.faction_personas = faction_personas
        self.llm_client = llm_client
        self.cost_accountant = cost_accountant
        self.base_path = base_path
        self.tmp_dir = tmp_dir
        self.extra_module_overrides = extra_module_overrides or {}
        self.seed_message = seed_message or DEFAULT_SEED_MESSAGE
        self.round_updates = round_updates if round_updates is not None else DEFAULT_ROUND_UPDATES
        self.scenario_analysis = scenario_analysis
        self.per_faction_providers = per_faction_providers or {}
        self.bare_mode = bare_mode
        self.agents: dict[str, AgentHandle] = {}
        self.round_flow: RoundSteppedFlow | None = None
        self.channel_log: list[dict[str, Any]] = []
        # Wrap in a logging client if it isn't one already.
        if isinstance(llm_client, LoggingLLMClient):
            self.logging_client: LoggingLLMClient | None = llm_client
        else:
            self.logging_client = None

    # ------------------------------------------------------------------
    # Config generation
    # ------------------------------------------------------------------

    def _generate_faction_config(
        self, faction_id: str, persona_path: Path, db_path: Path
    ) -> Path:
        """Write a per-faction pipeline YAML into *tmp_dir*."""
        config: dict[str, Any] = yaml.safe_load(
            (self.base_path / "config" / "pipeline_test.yaml").read_text(
                encoding="utf-8"
            )
        )

        config["faction_id"] = faction_id
        config["database"]["path"] = str(db_path)
        config["message_debounce_seconds"] = 0.01

        # Use real LLM providers from environment.
        import os

        config["llm_providers"] = {
            "primary": {
                "provider": os.getenv("DIPLOMAT_PRIMARY_PROVIDER", "openai"),
                "models": {
                    "quality": os.getenv(
                        "DIPLOMAT_PRIMARY_QUALITY_MODEL", "gpt-4.1-mini"
                    ),
                    "default": os.getenv(
                        "DIPLOMAT_PRIMARY_DEFAULT_MODEL", "gpt-4.1-mini"
                    ),
                    "commodity": os.getenv(
                        "DIPLOMAT_PRIMARY_COMMODITY_MODEL", "gpt-4.1-mini"
                    ),
                },
                "api_key_env": "OPENAI_API_KEY",
            },
            "secondary": {
                "provider": os.getenv("DIPLOMAT_SECONDARY_PROVIDER", "openai"),
                "models": {
                    "quality": os.getenv(
                        "DIPLOMAT_SECONDARY_QUALITY_MODEL", "gpt-4.1-mini"
                    ),
                    "default": os.getenv(
                        "DIPLOMAT_SECONDARY_DEFAULT_MODEL", "gpt-4.1-mini"
                    ),
                    "commodity": os.getenv(
                        "DIPLOMAT_SECONDARY_COMMODITY_MODEL", "gpt-4.1-mini"
                    ),
                },
                "api_key_env": "OPENAI_API_KEY",
            },
        }

        # Real LLM-backed modules — identical capabilities for all factions.
        config["modules"]["primary_analyst"] = {
            "class": "LLMAnalyst",
            "provider": "primary",
            "tier": "commodity",
        }
        config["modules"]["secondary_analyst"] = {
            "class": "LLMAnalyst",
            "provider": "secondary",
            "tier": "commodity",
        }
        # Generator: defaults to primary, but can be overridden per faction
        # via per_faction_providers. Used to vary the Generator's provider
        # while holding all other modules constant (Run 8 design).
        generator_provider_slot = "primary"
        override = self.per_faction_providers.get(faction_id)
        if override:
            provider_name = override["provider"]
            model_name = override["model"]
            generator_provider_slot = "generator_override"
            config["llm_providers"]["generator_override"] = {
                "provider": provider_name,
                "models": {
                    "quality": model_name,
                    "default": model_name,
                    "commodity": model_name,
                },
                "api_key_env": _api_key_env_for(provider_name),
            }
        config["modules"]["generator"] = {
            "class": "LLMGenerator",
            "provider": generator_provider_slot,
            "tier": "commodity",
            "max_tokens": 512,
        }
        config["modules"]["adversarial"] = {
            "class": "LLMAdversarialReader",
            "provider": "secondary",
            "tier": "commodity",
        }
        config["modules"]["review_gate"] = {"class": "AutoApproveReviewGate"}
        config["modules"]["extractor"] = {
            "class": "OpenAIStructuredExtractor",
            "provider": "primary",
        }

        # Persona path.
        config["paths"]["faction_prompt"] = str(persona_path)

        config_path = self.tmp_dir / f"pipeline_{faction_id}.yaml"
        config_path.write_text(
            yaml.safe_dump(config, sort_keys=False), encoding="utf-8"
        )
        return config_path

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def setup(self) -> None:
        """Create and start all agent Orchestrators."""
        bare_overrides: dict[str, Any] = {}
        if self.bare_mode:
            from tests.self_play.bare_mode import bare_module_overrides
            bare_overrides = bare_module_overrides()

        for faction_id, persona_path in self.faction_personas.items():
            db_path = self.tmp_dir / f"{faction_id}.db"
            config_path = self._generate_faction_config(
                faction_id, persona_path, db_path
            )

            transport = TestTransport()
            overrides = {"transport": transport}
            overrides.update(bare_overrides)
            overrides.update(self.extra_module_overrides)
            orchestrator = Orchestrator(
                config_path,
                options=OrchestrationOptions(
                    auto_response_enabled=False,
                    bare_mode=self.bare_mode,
                ),
                llm_client=self.llm_client,
                cost_accountant=self.cost_accountant,
                module_overrides=overrides,
                base_path=self.base_path,
            )

            # Attach a reconciler for post-round state cleanup. Attribution
            # metadata tags RECON calls in the LLM call log when logging is
            # enabled.
            recon_llm_client: Any = self.logging_client or self.llm_client
            if self.bare_mode:
                from tests.self_play.bare_mode import _BareReconciler
                orchestrator.reconciler = _BareReconciler()
            else:
                from modules.reconciliation import build_reconciler
                orchestrator.reconciler = build_reconciler(
                    recon_llm_client,
                    {"primary": _SELF_PLAY_PRIMARY},
                    tier="commodity",
                    attribution=f"recon:{faction_id}",
                )
            task = asyncio.create_task(orchestrator.start())
            await asyncio.sleep(0)  # let the event loop start

            self.agents[faction_id] = AgentHandle(
                faction_id=faction_id,
                orchestrator=orchestrator,
                transport=transport,
                task=task,
            )
        self.round_flow = RoundSteppedFlow(
            pipelines=[handle.orchestrator.pipeline for handle in self.agents.values()],
            moderator=self,
            total_rounds=0,
        )

    async def teardown(self) -> None:
        """Shut down all agents gracefully."""
        for handle in self.agents.values():
            await handle.orchestrator.shutdown()
            handle.task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await handle.task
        self.round_flow = None

    # ------------------------------------------------------------------
    # Message routing
    # ------------------------------------------------------------------

    async def broadcast(
        self,
        sender_id: str,
        content: str,
        *,
        channel: str = "public",
    ) -> None:
        """Inject an event into all agents except the sender."""
        now = datetime.now(timezone.utc)
        self.channel_log.append(
            {
                "sender": sender_id,
                "channel": channel,
                "content": content,
                "timestamp": now.isoformat(),
            }
        )
        for faction_id, handle in self.agents.items():
            if faction_id != sender_id:
                await handle.transport.inject(
                    InboundEvent(
                        timestamp=now,
                        sender_faction=sender_id,
                        channel=channel,
                        content=content,
                    )
                )

    def record_channel_message(
        self,
        sender_id: str,
        content: str,
        *,
        channel: str = "public",
    ) -> None:
        self.channel_log.append(
            {
                "sender": sender_id,
                "channel": channel,
                "content": content,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )

    async def broadcast_to_all(
        self,
        sender_id: str,
        content: str,
        *,
        channel: str = "public",
    ) -> None:
        """Inject an event into ALL agents (including sender)."""
        now = datetime.now(timezone.utc)
        self.channel_log.append(
            {
                "sender": sender_id,
                "channel": channel,
                "content": content,
                "timestamp": now.isoformat(),
            }
        )
        for handle in self.agents.values():
            await handle.transport.inject(
                InboundEvent(
                    timestamp=now,
                    sender_faction=sender_id,
                    channel=channel,
                    content=content,
                )
            )

    # ------------------------------------------------------------------
    # Round management
    # ------------------------------------------------------------------

    async def run_round(self, round_number: int) -> dict[str, str]:
        """Execute one round: moderator update → each agent responds → round end."""
        if self.round_flow is None:
            self.round_flow = RoundSteppedFlow(
                pipelines=[
                    handle.orchestrator.pipeline for handle in self.agents.values()
                ],
                moderator=self,
                total_rounds=0,
            )
        return await self.round_flow.run_round(round_number)

    async def run_game(self, total_rounds: int = 4) -> dict[str, Any]:
        """Run a full multi-round game and return results."""
        print(f"\n{'#'*60}")
        print(f"  SELF-PLAY SIMULATION — {len(self.agents)} factions, {total_rounds} rounds")
        print(f"{'#'*60}")

        # Tell each faction's orchestrator the game length before the seed
        # broadcast so persona endgame reminders can render from the first
        # generation. Auto-response was disabled when each orchestrator was
        # constructed; self-play drives exactly one explicit response per agent
        # per round via run_round().
        for handle in self.agents.values():
            handle.orchestrator.options = replace(
                handle.orchestrator.options,
                total_rounds=total_rounds,
            )
        if self.round_flow is not None:
            self.round_flow.total_rounds = total_rounds

        # Seed message.
        print(f"\n[MODERATOR] {self.seed_message[:200]}...")
        await self.broadcast_to_all("moderator", self.seed_message)
        await asyncio.sleep(0.1)

        # Run rounds.
        all_responses: dict[int, dict[str, str]] = {}
        for round_num in range(1, total_rounds + 1):
            responses = await self.run_round(round_num)
            all_responses[round_num] = responses

        # Collect and return results.
        results = await self.collect_results()
        results["round_responses"] = {
            str(k): v for k, v in all_responses.items()
        }
        results["rounds_completed"] = total_rounds
        results["bare_mode"] = self.bare_mode

        # Post-game scoring.
        if self.scenario_analysis:
            scores = await self.score_game(all_responses.get(total_rounds, {}))
            results["scores"] = scores
            results["scenario_analysis"] = self.scenario_analysis

        # Re-snapshot the LLM call log AFTER scoring so the SCORE call (and
        # any post-collect_results calls) appear in the output. Without this,
        # collect_results' snapshot only sees calls made during the rounds.
        if self.logging_client:
            results["llm_call_log"] = self.logging_client.to_dicts()

        # Print summary.
        print(f"\n{'='*60}")
        print("  GAME COMPLETE")
        print(f"{'='*60}")
        print(f"  Rounds: {total_rounds}")
        print(f"  Messages exchanged: {len(self.channel_log)}")
        for fid, data in results["agents"].items():
            promises = len(data.get("promises", []))
            coalitions = len(data.get("coalitions", []))
            print(f"  [{fid}] promises={promises}, coalitions={coalitions}")

        if "scores" in results:
            print(f"\n  {'-'*56}")
            print("  FINAL SCORES")
            print(f"  {'-'*56}")
            scores = results["scores"]
            deal = scores.get("deal_reached", False)
            print(f"  Deal reached: {'YES' if deal else 'NO (BATNA applies)'}")
            for fid, score_data in scores.get("faction_scores", {}).items():
                pts = score_data.get("points", 0)
                batna = score_data.get("batna", 0)
                vs_batna = pts - batna
                marker = "WIN" if vs_batna > 0 else "LOSE" if vs_batna < 0 else "DRAW"
                print(f"  [{fid}] {pts} pts (BATNA={batna}, vs BATNA: {vs_batna:+d}) {marker}")
            winner = max(
                scores.get("faction_scores", {}).items(),
                key=lambda x: x[1].get("points", 0),
                default=("?", {}),
            )
            print(f"\n  WINNER: {winner[0].upper()} with {winner[1].get('points', 0)} points")

        return results

    # ------------------------------------------------------------------
    # Post-game scoring
    # ------------------------------------------------------------------

    async def score_game(
        self, final_responses: dict[str, str]
    ) -> dict[str, Any]:
        """Score the game outcome based on final-round proposals and scoring tables."""
        if not self.scenario_analysis:
            return {"error": "No scenario analysis available for scoring"}

        from toolkit.structured_llm import structured_call

        scoring_schema = {
            "type": "object",
            "additionalProperties": False,
            "required": ["deal_reached", "faction_scores", "reasoning"],
            "properties": {
                "deal_reached": {"type": "boolean"},
                "agreed_outcomes": {
                    "type": "object",
                    "additionalProperties": {"type": "string"},
                    "description": "Issue name -> agreed outcome, if deal reached",
                },
                "faction_scores": {
                    "type": "object",
                    "additionalProperties": {
                        "type": "object",
                        "properties": {
                            "points": {"type": "number"},
                            "batna": {"type": "number"},
                        },
                        "required": ["points", "batna"],
                    },
                },
                "reasoning": {"type": "string"},
            },
        }

        factions_text = "\n\n".join(
            f"[{fid}] {text}" for fid, text in final_responses.items()
        )

        # Attribution metadata tags SCORE calls in the LLM call log when
        # logging is enabled.
        score_llm_client: Any = self.logging_client or self.llm_client
        from modules.reconciliation import subsystem_llm_config
        llm_config = subsystem_llm_config(_SELF_PLAY_PRIMARY)

        result = await structured_call(
            score_llm_client,
            llm_config,
            "commodity",
            schema=scoring_schema,
            system_prompt=(
                "You are a negotiation game scorer. Given the final round's "
                "proposals from all factions and the scoring tables, determine:\n"
                "1. Whether a deal was reached (did all factions converge on "
                "compatible terms?)\n"
                "2. If yes, what the agreed outcomes are per issue.\n"
                "3. Each faction's point score based on the agreed outcomes "
                "and their private scoring table.\n"
                "4. If no deal, each faction gets their BATNA score.\n"
                "Be strict about what counts as agreement — positions must be "
                "explicitly compatible, not just close.\n"
                "\n"
                "JSON formatting (critical): every numeric value must be a "
                "single computed literal (e.g. `16`), never an arithmetic "
                "expression (e.g. `3 + 10 + 3` is INVALID JSON and will be "
                "rejected). Compute the sum yourself and emit the final "
                "number. Use the `reasoning` field to show your work, not the "
                "numeric value fields."
            ),
            user_prompt=(
                f"Scoring tables:\n{json.dumps(self.scenario_analysis['scoring'], indent=2)}\n\n"
                f"BATNAs:\n{json.dumps(self.scenario_analysis['batna'], indent=2)}\n\n"
                f"Issues:\n{json.dumps(self.scenario_analysis['issues'], indent=2)}\n\n"
                f"Final round proposals:\n{factions_text}"
            ),
            max_retries=3,
            attribution="scorer",
            purpose="scoring",
        )

        if not result.success:
            return {"error": f"Scoring failed: {result.error}"}

        score_data = dict(result.data)
        score_data.update(_pareto_efficiency_metrics(self.scenario_analysis, score_data))
        score_data.update(_compute_baselines(self.scenario_analysis, score_data))
        return score_data

    # ------------------------------------------------------------------
    # Results collection
    # ------------------------------------------------------------------

    async def collect_results(self) -> dict[str, Any]:
        """Query each agent's state and assemble the results dict."""
        agent_results: dict[str, Any] = {}
        for faction_id, handle in self.agents.items():
            sm = handle.orchestrator.state_manager
            try:
                full_state = await sm.get_full_state()
            except Exception:
                full_state = {}

            promises = await _safe_query(sm, "promises", {})
            coalitions = await _safe_query(sm, "coalitions", {})
            inconsistencies = await _safe_query(sm, "inconsistencies", {})
            intelligence = await _safe_query(sm, "intelligence", {})
            state_change_log = await _safe_query(sm, "state_change_log", {})
            coaching = await _safe_query(sm, "coaching", {})
            adversarial_reads = await _safe_query(sm, "adversarial_reads", {})

            agent_results[faction_id] = {
                "full_state": full_state,
                "promises": promises,
                "coalitions": coalitions,
                "inconsistencies": inconsistencies,
                "intelligence": intelligence,
                "state_change_log": state_change_log,
                "coaching": coaching,
                "adversarial_reads": adversarial_reads,
                "round": handle.orchestrator.current_round,
            }

        result = {
            "agents": agent_results,
            "transcript": self.channel_log,
        }

        # Attach LLM call log if available.
        if self.logging_client:
            result["llm_call_log"] = self.logging_client.to_dicts()

        return result


async def _safe_query(
    state_manager: Any, entity_type: str, filters: dict[str, Any]
) -> list[dict[str, Any]]:
    """Query a state_manager table, returning [] on any error."""
    try:
        return await state_manager.query(entity_type, filters)
    except Exception:
        return []


def _pareto_efficiency_metrics(
    scenario_analysis: dict[str, Any],
    score_data: dict[str, Any],
) -> dict[str, Any]:
    """Calculate aggregate Pareto and BATNA-normalized metrics."""
    from tests.self_play.verify_scenario_optimum import (
        enumerate_deals,
        find_pareto_frontier,
    )

    deals = enumerate_deals(scenario_analysis)
    frontier = find_pareto_frontier(scenario_analysis, deals)
    max_pareto_sum = max((sum(scores.values()) for _, scores in frontier), default=0.0)

    faction_scores = score_data.get("faction_scores", {})
    achieved_sum = 0.0
    sum_batnas = 0.0
    faction_deltas: dict[str, float] = {}
    for faction in scenario_analysis.get("factions", faction_scores.keys()):
        faction_data = faction_scores.get(faction, {})
        points = float(faction_data.get("points", 0.0))
        batna = float(scenario_analysis.get("batna", {}).get(faction, 0.0))
        achieved_sum += points
        sum_batnas += batna
        faction_deltas[faction] = points - batna

    efficiency = achieved_sum / max_pareto_sum if max_pareto_sum > 0 else 0.0
    deltas = list(faction_deltas.values())
    delta_above_batna_sum = sum(deltas)
    min_faction_delta = min(deltas, default=0.0)
    mean_delta = delta_above_batna_sum / len(deltas) if deltas else 0.0
    surplus_distribution_stdev = (
        (
            sum((delta - mean_delta) ** 2 for delta in deltas)
            / len(deltas)
        )
        ** 0.5
        if deltas
        else 0.0
    )
    surplus_denominator = max_pareto_sum - sum_batnas
    negotiated_surplus_share = (
        delta_above_batna_sum / surplus_denominator
        if surplus_denominator > 0
        else 0.0
    )
    return {
        "achieved_score_sum": achieved_sum,
        "max_pareto_sum": max_pareto_sum,
        "pareto_efficiency": efficiency,
        "sum_batnas": sum_batnas,
        "faction_deltas": faction_deltas,
        "delta_above_batna_sum": delta_above_batna_sum,
        "min_faction_delta": min_faction_delta,
        "surplus_distribution_stdev": surplus_distribution_stdev,
        "negotiated_surplus_share": negotiated_surplus_share,
    }


def _compute_baselines(
    scenario_analysis: dict[str, Any],
    score_data: dict[str, Any],
) -> dict[str, Any]:
    """Calculate baseline comparisons against equal split, BATNA, and Nash bargaining."""
    from tests.self_play.verify_scenario_optimum import (
        beats_batna,
        enumerate_deals,
        faction_score,
        find_pareto_frontier,
    )

    factions = list(scenario_analysis.get("factions", []))
    deals = enumerate_deals(scenario_analysis)
    frontier = find_pareto_frontier(scenario_analysis, deals)
    max_pareto_sum = max((sum(scores.values()) for _, scores in frontier), default=0.0)
    equal_split_baseline = max_pareto_sum / len(factions) if factions else 0.0

    faction_scores = score_data.get("faction_scores", {})
    batnas = scenario_analysis.get("batna", {})
    achieved_sum = 0.0
    vs_equal_split: dict[str, float] = {}
    max_possible_per_faction: dict[str, float] = {}
    skill_premium_vs_batna: dict[str, float] = {}

    for faction in factions:
        faction_data = faction_scores.get(faction, {})
        points = float(faction_data.get("points", 0.0))
        batna = float(batnas.get(faction, 0.0))
        achieved_sum += points
        vs_equal_split[faction] = points - equal_split_baseline

        max_possible = max(
            (faction_score(scenario_analysis, faction, deal) for deal in deals),
            default=batna,
        )
        max_possible_per_faction[faction] = max_possible
        denominator = max_possible - batna
        skill_premium_vs_batna[faction] = (
            (points - batna) / denominator if denominator > 0 else 0.0
        )

    nash_deal_scores: dict[str, float] | None = None
    nash_deal_sum: float | None = None
    nash_product: float | None = None
    vs_nash_efficiency: float | None = None

    nash_candidates: list[tuple[dict[str, str], dict[str, float], float]] = []
    for deal in deals:
        scores = {faction: faction_score(scenario_analysis, faction, deal) for faction in factions}
        if beats_batna(scenario_analysis, scores):
            product = 1.0
            for faction in factions:
                product *= scores[faction] - float(batnas.get(faction, 0.0))
            nash_candidates.append((deal, scores, product))

    if nash_candidates:
        _, nash_deal_scores, nash_product = max(
            nash_candidates,
            key=lambda item: item[2],
        )
        nash_deal_sum = sum(nash_deal_scores.values())
        vs_nash_efficiency = achieved_sum / nash_deal_sum if nash_deal_sum > 0 else 0.0

    return {
        "equal_split_baseline": equal_split_baseline,
        "vs_equal_split": vs_equal_split,
        "max_possible_per_faction": max_possible_per_faction,
        "skill_premium_vs_batna": skill_premium_vs_batna,
        "nash_deal_scores": nash_deal_scores,
        "nash_deal_sum": nash_deal_sum,
        "nash_product": nash_product,
        "vs_nash_efficiency": vs_nash_efficiency,
    }
