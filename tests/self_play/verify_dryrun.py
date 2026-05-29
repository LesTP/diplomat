"""Verify infrastructure invariants on a dry-run self-play results JSON.

Run AFTER a dry-run to assert the self-play plumbing behaved correctly.
Returns nonzero exit code if any invariant fails.

Usage:
    python -m tests.self_play.verify_dryrun --results tests/self_play/results/dryrun_v1.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--results", required=True, type=str)
    p.add_argument("--num-factions", type=int, default=3)
    p.add_argument("--rounds", type=int, default=4)
    p.add_argument(
        "--adversarial",
        action="store_true",
        default=True,
        help="Whether adversarial reader was enabled (default: True)",
    )
    args = p.parse_args()

    data = json.loads(Path(args.results).read_text(encoding="utf-8"))
    calls = data.get("llm_call_log") or []
    transcript = data.get("transcript") or []
    agents = data.get("agents") or {}
    scores = data.get("scores") or {}

    failures: list[str] = []

    # Classify each call by its system prompt signature.
    from tests.self_play.fake_llm_client import classify_call, extract_round_hint, extract_faction_id

    by_type: Counter[str] = Counter()
    by_type_and_round: dict[tuple[str, int], int] = {}
    gen_calls: list[dict] = []
    for c in calls:
        msgs = c.get("messages") or []
        sys_msg = next((m for m in msgs if m.get("role") == "system"), {})
        user_msg = next((m for m in msgs if m.get("role") == "user"), {})
        sys_prompt = sys_msg.get("content", "")
        user_prompt = user_msg.get("content", "")
        call_type = classify_call(sys_prompt)
        by_type[call_type] += 1
        if call_type == "GEN":
            hint = extract_round_hint(user_prompt)
            faction = extract_faction_id(sys_prompt)
            gen_calls.append({"faction": faction, **hint})
            rnd = hint.get("round")
            if rnd is not None:
                by_type_and_round[("GEN", rnd)] = by_type_and_round.get(("GEN", rnd), 0) + 1

    print(f"\nCall counts by type: {dict(by_type)}")

    F = args.num_factions
    R = args.rounds

    # --- Invariant 1: total_rounds reached the persona ---
    bad_total = [g for g in gen_calls if g.get("total_rounds") != R]
    if bad_total:
        failures.append(
            f"Bug 1 — total_rounds NOT reaching persona in {len(bad_total)}/{len(gen_calls)} "
            f"generation calls. Expected total_rounds={R}. Sample: {bad_total[0]}"
        )

    # --- Invariant 2: current_round increments per round ---
    rounds_seen = sorted({g["round"] for g in gen_calls if "round" in g})
    expected_rounds = list(range(1, R + 1))
    if rounds_seen != expected_rounds:
        failures.append(
            f"Bug 2 — generation calls saw rounds {rounds_seen}, expected {expected_rounds}. "
            f"current_round is not advancing per round."
        )

    # --- Invariant 3: GEN calls per round == F (one per faction) ---
    for rnd in expected_rounds:
        count = by_type_and_round.get(("GEN", rnd), 0)
        if count != F:
            failures.append(
                f"Bug 2/3 — expected {F} GEN calls in round {rnd}, got {count}."
            )

    # --- Invariant 4: each agent message reaches transcript per round ---
    agent_msgs_per_round: Counter[int] = Counter()
    for m in transcript:
        sender = m.get("sender") or m.get("sender_faction")
        if sender and sender not in ("moderator", "system"):
            # We don't have round_number on transcript entries; infer from order
            # by counting messages between moderator round-update markers. Simpler:
            # just count total non-moderator messages.
            agent_msgs_per_round["_total"] += 1

    expected_total_agent_msgs = F * R
    actual_total_agent_msgs = agent_msgs_per_round["_total"]
    if actual_total_agent_msgs != expected_total_agent_msgs:
        failures.append(
            f"Bug 3 — expected {expected_total_agent_msgs} agent messages in transcript "
            f"({F} factions x {R} rounds), got {actual_total_agent_msgs}. "
            f"Generations are being made but not reaching the transcript."
        )

    # --- Invariant 5: penultimate / final round markers fire in the right rounds ---
    penultimate_rounds = {g["round"] for g in gen_calls if g.get("has_penultimate_marker")}
    final_rounds = {g["round"] for g in gen_calls if g.get("has_final_marker")}
    if R >= 2:
        if R - 1 not in penultimate_rounds:
            failures.append(
                f"Endgame — PENULTIMATE ROUND block missing in round {R-1}. "
                f"Saw it in: {sorted(penultimate_rounds) or '(nowhere)'}"
            )
        if R not in final_rounds:
            failures.append(
                f"Endgame — FINAL ROUND block missing in round {R}. "
                f"Saw it in: {sorted(final_rounds) or '(nowhere)'}"
            )
        # Negative: penultimate/final should NOT appear in early rounds
        early_rounds = set(range(1, R - 1))
        bad_penultimate = early_rounds & penultimate_rounds
        bad_final = early_rounds & final_rounds
        if bad_penultimate:
            failures.append(
                f"Endgame — PENULTIMATE marker leaked into early rounds {sorted(bad_penultimate)}"
            )
        if bad_final:
            failures.append(
                f"Endgame — FINAL marker leaked into early rounds {sorted(bad_final)}"
            )

    # --- Invariant 6: ADV calls per round == F (if enabled) ---
    if args.adversarial:
        expected_adv = F * R
        if by_type.get("ADV", 0) != expected_adv:
            failures.append(
                f"Adversarial — expected {expected_adv} ADV calls ({F} x {R}), "
                f"got {by_type.get('ADV', 0)}"
            )

    # --- Invariant 7: SCORE produced output (note: SCORE calls bypass
    # LoggingLLMClient because score_game uses the unwrapped inner client,
    # so we check the results-JSON `scores` field instead of the call log).
    if not scores or "faction_scores" not in scores:
        failures.append(
            "Scoring — scores.faction_scores missing; post-game scorer did not run."
        )

    # --- Invariant 9: each agent has run-loop state ---
    if set(agents.keys()) != set(c.get("faction") for c in gen_calls if c.get("faction")):
        agents_keys = sorted(agents.keys())
        gen_factions = sorted({c.get("faction") for c in gen_calls if c.get("faction")})
        failures.append(
            f"State — agents present in results ({agents_keys}) "
            f"mismatch generators called ({gen_factions})"
        )

    # --- Report ---
    print(f"\nVerified against: {args.results}")
    print(f"  {F} factions x {R} rounds")
    print(f"  Transcript agent messages: {actual_total_agent_msgs} (expected {expected_total_agent_msgs})")
    print(f"  Rounds seen by generations: {rounds_seen}")
    print(f"  Penultimate marker rounds: {sorted(penultimate_rounds)}")
    print(f"  Final marker rounds: {sorted(final_rounds)}")
    print(f"  SCORE calls: {by_type.get('SCORE', 0)}")
    print()

    if failures:
        print(f"FAIL — {len(failures)} infrastructure invariants violated:\n")
        for f in failures:
            print(f"  * {f}")
        return 1

    print("PASS — all infrastructure invariants hold.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
