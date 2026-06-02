"""CLI runner for a coached multi-agent self-play simulation.

This reuses the standard self-play scenario/persona/LLM construction but
swaps one faction's transport and review gate so an operator can coach that
faction live via Telegram.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

from modules.review_gate import ReviewDecision, TelegramReviewGate
from modules.transport import TelegramBotTransport
from flows.round_stepped import RoundSteppedFlow
from orchestrator import OrchestrationOptions, Orchestrator
from tests.helpers.test_transport import TestTransport
from tests.self_play.game_environment import AgentHandle, GameEnvironment
from tests.self_play import run_simulation


_SELF_PLAY_PRIMARY: dict[str, Any] = {
    "provider": "openai",
    "models": {"commodity": "gpt-4.1-mini"},
    "api_key_env": "OPENAI_API_KEY",
}


class CoachedGameTransport(TestTransport):
    """Self-play transport that forwards outbound messages to Telegram.

    The self-play harness still injects moderator and peer messages locally
    through ``inject()``. Outbound sends are mirrored to Telegram so the
    coached faction's public output is visible to the operator.
    """

    def __init__(self, telegram_transport: TelegramBotTransport | None = None) -> None:
        super().__init__()
        self._telegram_transport = telegram_transport

    async def send(self, message) -> None:
        if self._telegram_transport is not None:
            await self._telegram_transport.send(message)
        await super().send(message)


class DryRunTelegramReviewGate:
    """Telegram-flavored stand-in used by ``--dry-run``."""

    def __init__(self) -> None:
        self.submissions: list[dict[str, Any]] = []

    async def submit(
        self,
        draft: Any,
        adversarial: Any,
        round_number: int,
    ) -> ReviewDecision:
        self.submissions.append(
            {
                "round_number": round_number,
                "draft_success": getattr(draft, "success", None),
                "draft_text": getattr(draft, "response_text", None),
                "adversarial": adversarial,
            }
        )

        if not getattr(draft, "success", False):
            return ReviewDecision(
                action="blocked",
                final_text=None,
                edit_notes=getattr(draft, "error", None) or "Draft generation failed",
            )

        response_text = (getattr(draft, "response_text", "") or "").strip()
        if not response_text:
            return ReviewDecision(
                action="blocked",
                final_text=None,
                edit_notes="Draft response was blank",
            )

        return ReviewDecision(
            action="approved",
            final_text=response_text,
            edit_notes=None,
        )


class CoachedGameEnvironment(GameEnvironment):
    """GameEnvironment variant that gives one faction live Telegram wiring."""

    def __init__(
        self,
        *,
        coach_faction: str,
        dry_run: bool,
        telegram_client: Any | None,
        public_channel_id: str | int | None,
        coaching_channel_id: str | int | None,
        operator_user_ids: set[str],
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.coach_faction = coach_faction
        self.dry_run = dry_run
        self.telegram_client = telegram_client
        self.public_channel_id = public_channel_id
        self.coaching_channel_id = coaching_channel_id
        self.operator_user_ids = operator_user_ids

    async def setup(self) -> None:
        for faction_id, persona_path in self.faction_personas.items():
            db_path = self.tmp_dir / f"{faction_id}.db"
            config_path = self._generate_faction_config(
                faction_id, persona_path, db_path
            )

            overrides = dict(self.extra_module_overrides)
            if faction_id == self.coach_faction:
                overrides["transport"] = self._build_coached_transport()
                overrides["review_gate"] = self._build_coached_review_gate()
            else:
                overrides.setdefault("transport", TestTransport())

            orchestrator = Orchestrator(
                config_path,
                options=OrchestrationOptions(auto_response_enabled=False),
                llm_client=self.llm_client,
                cost_accountant=self.cost_accountant,
                module_overrides=overrides,
                base_path=self.base_path,
            )

            recon_llm_client: Any = self.logging_client or self.llm_client
            from modules.reconciliation import build_reconciler

            orchestrator.reconciler = build_reconciler(
                recon_llm_client,
                {"primary": _SELF_PLAY_PRIMARY},
                tier="commodity",
                attribution=f"recon:{faction_id}",
            )
            task = asyncio.create_task(orchestrator.start())
            await asyncio.sleep(0)

            self.agents[faction_id] = AgentHandle(
                faction_id=faction_id,
                orchestrator=orchestrator,
                transport=overrides["transport"],
                task=task,
            )

        self.round_flow = RoundSteppedFlow(
            pipelines=[handle.orchestrator.pipeline for handle in self.agents.values()],
            moderator=self,
            total_rounds=0,
        )

    def _build_coached_transport(self) -> CoachedGameTransport:
        if self.dry_run:
            return CoachedGameTransport()
        return CoachedGameTransport(self._build_telegram_transport())

    def _build_coached_review_gate(self) -> Any:
        if self.dry_run:
            return DryRunTelegramReviewGate()
        return TelegramReviewGate(
            self._telegram_client(),
            coaching_channel_id=self._coaching_channel_id(),
        )

    def _build_telegram_transport(self) -> TelegramBotTransport:
        client = self._telegram_client()
        return TelegramBotTransport(
            client,
            public_channel_id=self._public_channel_id(),
            coaching_channel_id=self._coaching_channel_id(),
            operator_user_ids=self.operator_user_ids,
        )

    def _telegram_client(self) -> Any:
        if self.telegram_client is not None:
            return self.telegram_client
        bot_token = _require_env("TELEGRAM_BOT_TOKEN")
        try:
            from toolkit.telegram_client import TelegramClient
        except ImportError as exc:
            raise RuntimeError(
                "toolkit telegram client is unavailable; install toolkit editable first"
            ) from exc

        self.telegram_client = TelegramClient(bot_token)
        return self.telegram_client

    def _public_channel_id(self) -> str:
        if self.public_channel_id is not None:
            return str(self.public_channel_id).strip()
        return _require_env("DIPLOMAT_PUBLIC_CHANNEL_ID")

    def _coaching_channel_id(self) -> str:
        if self.coaching_channel_id is not None:
            return str(self.coaching_channel_id).strip()
        return _require_env("DIPLOMAT_COACHING_CHANNEL_ID")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a Diplomat coached self-play simulation."
    )
    parser.add_argument(
        "--coach-faction",
        required=True,
        help="Faction id to route through live Telegram coaching",
    )
    _add_run_simulation_args(parser)
    return parser


def _add_run_simulation_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--rounds",
        type=int,
        default=4,
        help="Number of rounds to play (default: 4)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output JSON file path (default: auto-timestamped)",
    )
    parser.add_argument(
        "--factions",
        type=str,
        default="alpha,beta,gamma",
        help="Comma-separated faction IDs (default: alpha,beta,gamma)",
    )
    parser.add_argument(
        "--scenario",
        type=str,
        default=None,
        help="Path to scenario description — auto-compiles personas via LLM",
    )
    parser.add_argument(
        "--scenario-title",
        type=str,
        default="a multi-party negotiation",
        help="Title for compiled persona headers",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Use DryRunLLMClient and a local Telegram review-gate stand-in",
    )
    parser.add_argument(
        "--per-faction-providers",
        type=str,
        default=None,
        help=(
            'JSON map of faction_id -> {"provider":"...","model":"..."} '
            'that overrides the Generator provider/model for that faction.'
        ),
    )
    parser.add_argument(
        "--analysis-json",
        type=str,
        default=None,
        help=(
            "Path to a pre-compiled scenario_analysis.json. When provided, "
            "skips the live LLM compile step and uses this analysis to "
            "generate personas and seed post-game scoring. Requires --scenario "
            "to also be provided (for the seed message text)."
        ),
    )
    parser.add_argument(
        "--batna-fraction",
        type=float,
        default=None,
        help=(
            "Target BATNA as fraction of each faction's max possible score "
            "during scenario compilation."
        ),
    )
    parser.add_argument(
        "--batna-fractions",
        type=str,
        default=None,
        help=(
            'JSON map of faction_id -> BATNA fraction for scenario compilation. '
            "Overrides --batna-fraction for listed factions."
        ),
    )
    parser.add_argument(
        "--game-mode",
        choices=("cooperative", "competitive", "mixed"),
        default=None,
        help="Runtime override for compiled scenario game_mode.",
    )


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if value is None or not value.strip():
        print(f"ERROR: missing required environment variable: {name}", file=sys.stderr)
        sys.exit(1)
    return value.strip()


def _parse_operator_user_ids(raw_value: str) -> set[str]:
    return {item.strip() for item in raw_value.split(",") if item.strip()}


async def _run(args: argparse.Namespace) -> None:
    faction_ids = [f.strip() for f in args.factions.split(",") if f.strip()]

    from tools.scenario_compiler import parse_batna_fractions_json

    try:
        batna_fractions = (
            parse_batna_fractions_json(args.batna_fractions)
            if args.batna_fractions
            else None
        )
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    per_faction_providers: dict[str, dict[str, str]] | None = None
    if args.per_faction_providers:
        try:
            per_faction_providers = json.loads(args.per_faction_providers)
        except json.JSONDecodeError as exc:
            print(
                f"ERROR: --per-faction-providers is not valid JSON: {exc}",
                file=sys.stderr,
            )
            sys.exit(1)
        if not isinstance(per_faction_providers, dict):
            print("ERROR: --per-faction-providers must be a JSON object", file=sys.stderr)
            sys.exit(1)
        for fid, cfg in per_faction_providers.items():
            if not isinstance(cfg, dict):
                print(
                    f"ERROR: per-faction-providers[{fid}] must be an object",
                    file=sys.stderr,
                )
                sys.exit(1)
            if "provider" not in cfg or "model" not in cfg:
                print(
                    f"ERROR: per-faction-providers[{fid}] missing 'provider' or 'model'",
                    file=sys.stderr,
                )
                sys.exit(1)
        unknown = set(per_faction_providers.keys()) - set(faction_ids)
        if unknown and not args.scenario:
            print(
                f"WARNING: per-faction-providers has factions not in --factions: {sorted(unknown)}",
                file=sys.stderr,
            )

    if args.dry_run:
        from tests.helpers.factories import FakeCostAccountant
        from tests.self_play.fake_llm_client import DryRunLLMClient
        from tests.self_play.game_environment import LoggingLLMClient

        print("=" * 60)
        print("  DRY RUN MODE — no real LLM calls, no cost")
        print("=" * 60)
        accountant = None
        llm_client = LoggingLLMClient(DryRunLLMClient())
        cost_accountant = FakeCostAccountant()
        live_telegram = None
        public_channel_id = None
        coaching_channel_id = None
        operator_user_ids: set[str] = set()
    else:
        accountant = run_simulation._build_raw_accountant()
        llm_client = run_simulation._build_llm_client(cost_accountant=accountant)
        cost_accountant = run_simulation._build_cost_accountant(accountant=accountant)
        live_telegram = None
        public_channel_id = _require_env("DIPLOMAT_PUBLIC_CHANNEL_ID")
        coaching_channel_id = _require_env("DIPLOMAT_COACHING_CHANNEL_ID")
        operator_user_ids = _parse_operator_user_ids(
            _require_env("DIPLOMAT_OPERATOR_USER_IDS")
        )

    with tempfile.TemporaryDirectory(
        prefix="diplomat_selfplay_", ignore_cleanup_errors=True
    ) as tmp:
        tmp_dir = Path(tmp)
        seed_message = None
        round_updates = None
        scenario_analysis = None

        if args.analysis_json:
            if not args.scenario:
                print(
                    "ERROR: --analysis-json requires --scenario (for the seed message text)",
                    file=sys.stderr,
                )
                sys.exit(1)
            personas, scenario_analysis = run_simulation._load_precompiled_analysis(
                args.analysis_json,
                faction_ids,
                tmp_dir,
                args.scenario_title,
                game_mode_override=args.game_mode,
            )
            seed_message = Path(args.scenario).read_text(encoding="utf-8")
            round_updates = {
                1: "Opening positions are on the table. Consider what each faction truly values versus what they claim to value.",
                2: "Midpoint: assess whether proposals reflect genuine priorities or strategic positioning. Look for trades that create mutual value.",
                3: "Pressure is building. The cost of no deal is rising. Consider whether to escalate, concede, or propose a new framework.",
                4: "Final round. All commitments are binding. This is your last chance to secure favorable terms.",
            }
        elif args.scenario:
            personas, scenario_analysis = await run_simulation._compile_scenario(
                args.scenario,
                faction_ids,
                tmp_dir,
                llm_client,
                args.scenario_title,
                batna_fraction=args.batna_fraction,
                batna_fractions=batna_fractions,
                game_mode_override=args.game_mode,
            )
            seed_message = Path(args.scenario).read_text(encoding="utf-8")
            round_updates = {
                1: "Opening positions are on the table. Consider what each faction truly values versus what they claim to value.",
                2: "Midpoint: assess whether proposals reflect genuine priorities or strategic positioning. Look for trades that create mutual value.",
                3: "Pressure is building. The cost of no deal is rising. Consider whether to escalate, concede, or propose a new framework.",
                4: "Final round. All commitments are binding. This is your last chance to secure favorable terms.",
            }
        else:
            personas = run_simulation._resolve_personas(faction_ids)

        if args.coach_faction not in personas:
            print(
                f"ERROR: coach faction '{args.coach_faction}' is not present in the active faction list",
                file=sys.stderr,
            )
            sys.exit(1)

        env = CoachedGameEnvironment(
            coach_faction=args.coach_faction,
            dry_run=args.dry_run,
            telegram_client=live_telegram,
            public_channel_id=public_channel_id,
            coaching_channel_id=coaching_channel_id,
            operator_user_ids=operator_user_ids,
            faction_personas=personas,
            llm_client=llm_client,
            cost_accountant=cost_accountant,
            base_path=Path(__file__).resolve().parent.parent.parent,
            tmp_dir=tmp_dir,
            seed_message=seed_message,
            round_updates=round_updates,
            scenario_analysis=scenario_analysis,
            per_faction_providers=per_faction_providers,
        )

        await env.setup()
        results = None
        try:
            results = await env.run_game(total_rounds=args.rounds)
        finally:
            if results is not None:
                run_simulation._write_results(results, args.output)
            await env.teardown()


def main() -> None:
    args = _build_parser().parse_args()
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()
