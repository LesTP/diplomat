"""Dry-run LLM client for cost-free self-play infrastructure validation.

Drop-in replacement for ``ToolkitLLMAdapter``. Classifies each call by the
system prompt's signature and returns a canned, schema-valid JSON response so
that the entire self-play pipeline (generation -> adversarial -> review gate ->
transport -> extraction -> analyst -> reconciliation -> scoring) can run end
to end with zero LLM cost.

Usage: pass an instance to ``GameEnvironment(llm_client=...)`` or to
``run_simulation.py`` via the ``--dry-run`` flag.

What this catches: plumbing bugs (round counter increments, message delivery,
extraction call counts, schema mismatches between modules).
What this does NOT catch: anything that depends on the *content* of LLM
output being plausible (real strategic behavior, prompt-quality, persona
adherence).
"""

from __future__ import annotations

import json
import re
from typing import Any


# ---------------------------------------------------------------------------
# Call classification
# ---------------------------------------------------------------------------

_GEN_RE = re.compile(r"^You are ([a-zA-Z][\w-]*?) in ", re.MULTILINE)


def classify_call(system_prompt: str) -> str:
    """Return one of: GEN, ADV, EXTRACT, ANALYST, RECON, COMPILE, SCORE, JUDGE, UNKNOWN."""
    s = system_prompt or ""
    head = s[:300].lower()

    if "you are diplomat's adversarial reader" in head:
        return "ADV"
    if "you are diplomat's state extraction engine" in head:
        return "EXTRACT"
    if "you are diplomat's neutral strategic intelligence analyst" in head:
        return "ANALYST"
    if "you are a negotiation state reconciler" in head:
        return "RECON"
    if "you are a negotiation scenario analyst" in head:
        return "COMPILE"
    if "you are a negotiation game scorer" in head:
        return "SCORE"
    if "judge" in head and ("pass" in head or "fail" in head):
        return "JUDGE"
    if _GEN_RE.search(s):
        return "GEN"
    return "UNKNOWN"


def extract_faction_id(system_prompt: str) -> str | None:
    """Pull the faction id from a generation persona's 'You are X in ...' line."""
    m = _GEN_RE.search(system_prompt or "")
    return m.group(1).lower() if m else None


def extract_round_hint(user_prompt: str) -> dict[str, Any]:
    """Pull round metadata out of the user prompt's CURRENT ROUND CONTEXT section."""
    out: dict[str, Any] = {}
    m_round = re.search(r"Round:\s*(\d+)(?:\s*of\s*(\d+))?", user_prompt or "")
    if m_round:
        out["round"] = int(m_round.group(1))
        if m_round.group(2):
            out["total_rounds"] = int(m_round.group(2))
    m_rem = re.search(r"Rounds remaining:\s*(\S+)", user_prompt or "")
    if m_rem:
        rem = m_rem.group(1)
        out["rounds_remaining"] = int(rem) if rem.isdigit() else rem
    out["has_final_marker"] = "### FINAL ROUND" in (user_prompt or "")
    out["has_penultimate_marker"] = "### PENULTIMATE ROUND" in (user_prompt or "")
    return out


# ---------------------------------------------------------------------------
# Canned response builders (each returns a JSON string)
# ---------------------------------------------------------------------------


def _gen_response(faction: str | None, round_hint: dict[str, Any]) -> str:
    rnd = round_hint.get("round", "?")
    total = round_hint.get("total_rounds", "?")
    fac_tag = faction.upper() if faction else "?"
    marker = ""
    if round_hint.get("has_final_marker"):
        marker = " [saw FINAL ROUND]"
    elif round_hint.get("has_penultimate_marker"):
        marker = " [saw PENULTIMATE ROUND]"
    return json.dumps(
        {
            "response": (
                f"[dryrun {fac_tag} R{rnd}/{total}{marker}] "
                f"My proposal: form coalition ABC, split 40/40/41."
            ),
            "reasoning": f"dryrun stub for {fac_tag} round {rnd}",
        }
    )


def _adv_response() -> str:
    return json.dumps(
        {
            "reveals": ["dryrun: faction reveals coalition preference"],
            "commits_to": [],
            "exploitable": [],
            "counter_moves": [],
            "summary": "dryrun: no real adversarial analysis",
        }
    )


def _extract_response() -> str:
    # Empty patch is a valid extraction result (means "found nothing").
    # Lets us count extraction calls without needing to model schema for
    # promises/coalitions/etc.
    return json.dumps({})


def _analyst_response() -> str:
    return json.dumps(
        {
            "threat_level": 3,
            "key_leverage_points": ["dryrun: stub leverage point"],
            "coalition_stability": "unknown",
            "summary": "dryrun: stub intelligence report",
        }
    )


def _recon_response() -> str:
    return json.dumps(
        {
            "merged_promises": [],
            "status_updates": [],
            "new_inconsistencies": [],
            "missed_proposals": [],
            "merge_log": ["dryrun: no reconciliation actions taken"],
        }
    )


def _compile_response() -> str:
    """Mimic the scenario_compiler's SCENARIO_ANALYSIS_SCHEMA shape."""
    return json.dumps(
        {
            "factions": ["a", "b", "c"],
            "issues": [
                {
                    "name": "coalition_structure",
                    "outcomes": ["abc_only", "ab_only", "ac_only"],
                    "description": "dryrun: which coalition forms",
                }
            ],
            "scoring": {
                "a": {"coalition_structure": {"abc_only": 7, "ab_only": 9, "ac_only": 5}},
                "b": {"coalition_structure": {"abc_only": 7, "ab_only": 9, "ac_only": 3}},
                "c": {"coalition_structure": {"abc_only": 7, "ab_only": 3, "ac_only": 8}},
            },
            "batna": {"a": 6, "b": 5, "c": 4},
            "deception_tactics": {
                "a": "dryrun: stub tactic",
                "b": "dryrun: stub tactic",
                "c": "dryrun: stub tactic",
            },
            "logrolling": ["dryrun: stub trade"],
            "game_mode": "competitive",
        }
    )


def _score_response() -> str:
    return json.dumps(
        {
            "deal_reached": False,
            "faction_scores": {
                "a": {"points": 6, "batna": 6},
                "b": {"points": 5, "batna": 5},
                "c": {"points": 4, "batna": 4},
            },
            "reasoning": "dryrun: no real scoring; defaulted to BATNA",
        }
    )


def _judge_response() -> str:
    return "PASS|dryrun stub"


_RESPONSE_BUILDERS = {
    "ADV": lambda f, r: _adv_response(),
    "EXTRACT": lambda f, r: _extract_response(),
    "ANALYST": lambda f, r: _analyst_response(),
    "RECON": lambda f, r: _recon_response(),
    "COMPILE": lambda f, r: _compile_response(),
    "SCORE": lambda f, r: _score_response(),
    "JUDGE": lambda f, r: _judge_response(),
    "GEN": _gen_response,
}


# ---------------------------------------------------------------------------
# The fake client
# ---------------------------------------------------------------------------


class DryRunLLMClient:
    """Replacement for ``ToolkitLLMAdapter`` that returns canned responses.

    Matches the adapter's interface: ``async complete(*, messages, config, tier)``
    returning a string. Records every call to ``self.calls`` so the runner can
    later verify the pipeline behaved as expected.
    """

    def __init__(self, *, verbose: bool = False) -> None:
        self.calls: list[dict[str, Any]] = []
        self.verbose = verbose

    async def complete(self, **kwargs: Any) -> str:
        messages = kwargs.get("messages") or []
        system_msg = next((m for m in messages if m.get("role") == "system"), {})
        user_msg = next((m for m in messages if m.get("role") == "user"), {})
        sys_prompt = system_msg.get("content", "")
        user_prompt = user_msg.get("content", "")

        call_type = classify_call(sys_prompt)
        faction = extract_faction_id(sys_prompt) if call_type == "GEN" else None
        round_hint = extract_round_hint(user_prompt) if call_type == "GEN" else {}

        builder = _RESPONSE_BUILDERS.get(call_type)
        if builder is None:
            # Unknown call type — return generic empty JSON object.
            response = "{}"
            if self.verbose:
                print(f"  [dryrun] UNKNOWN call type, sys head: {sys_prompt[:120]!r}")
        else:
            response = builder(faction, round_hint)

        self.calls.append(
            {
                "call_index": len(self.calls),
                "call_type": call_type,
                "faction": faction,
                "round_hint": round_hint,
                "sys_head": sys_prompt[:120],
                "user_head": user_prompt[:120],
                "response": response,
            }
        )
        if self.verbose:
            fac = faction or "-"
            rnd = round_hint.get("round", "-")
            print(f"  [dryrun] {call_type:8s} fac={fac:4s} round={rnd}")
        return response


__all__ = [
    "DryRunLLMClient",
    "classify_call",
    "extract_faction_id",
    "extract_round_hint",
]
