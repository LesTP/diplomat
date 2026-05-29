"""Detailed analysis of dry-run results — why are GEN counts so high?"""
import json
import re
from collections import Counter
from pathlib import Path

p = Path("tests/self_play/results/dryrun_v1.json")
data = json.loads(p.read_text(encoding="utf-8"))
calls = data.get("llm_call_log") or []

from tests.self_play.fake_llm_client import classify_call, extract_round_hint, extract_faction_id

# For each call, infer (faction, round, type, trigger context)
buckets: dict = {}
for c in calls:
    msgs = c.get("messages") or []
    sys_msg = next((m for m in msgs if m.get("role") == "system"), {})
    user_msg = next((m for m in msgs if m.get("role") == "user"), {})
    sys_p = sys_msg.get("content", "")
    user_p = user_msg.get("content", "")
    ct = classify_call(sys_p)
    rnd = extract_round_hint(user_p).get("round") if ct == "GEN" else None
    fac = extract_faction_id(sys_p) if ct == "GEN" else None

    key = (ct, fac, rnd)
    buckets[key] = buckets.get(key, 0) + 1

print("GEN calls per (faction, round):")
for k, v in sorted(buckets.items()):
    if k[0] == "GEN":
        print(f"  faction={k[1]}, round={k[2]}: {v} calls")

print(f"\nTotal GEN: {sum(v for k,v in buckets.items() if k[0]=='GEN')}")
print(f"Expected: 3 factions x 4 rounds = 12")

# Look at one GEN call's user prompt to see what triggered it
print("\nSample 5 GEN call user prompts (first 300 chars each):")
gen_count = 0
for c in calls:
    msgs = c.get("messages") or []
    sys_msg = next((m for m in msgs if m.get("role") == "system"), {})
    user_msg = next((m for m in msgs if m.get("role") == "user"), {})
    if classify_call(sys_msg.get("content", "")) == "GEN":
        gen_count += 1
        if gen_count <= 5:
            fac = extract_faction_id(sys_msg.get("content", ""))
            user_p = user_msg.get("content", "")
            # Find round
            m = re.search(r"Round:\s*(\d+)(?:\s*of\s*(\d+))?", user_p)
            rnd = m.group(0) if m else "?"
            # Look at what messages were in recent events
            recent = re.findall(r"\[Round \d+ \|.*?\]", user_p)[:5]
            print(f"\n  --- GEN #{gen_count}: fac={fac} {rnd} ---")
            print(f"  recent events markers in prompt: {len(recent)}")
            for r in recent:
                print(f"    {r}")
