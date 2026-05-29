"""Inspect each LLM call's round number and total_rounds context."""
import json
import re
from pathlib import Path

p = Path("tests/self_play/results/run7_endgame.json")
data = json.loads(p.read_text(encoding="utf-8"))
calls = data.get("llm_call_log") or []
print(f"Total calls: {len(calls)}\n")

for i, c in enumerate(calls):
    mts = c.get("messages") or []
    user = next((m["content"] for m in mts if m.get("role") == "user"), "")
    sys_ = next((m["content"] for m in mts if m.get("role") == "system"), "")

    # Detect module by system prompt signature
    if "adversarial reader" in sys_.lower(): module = "ADV"
    elif "negotiation scenario analyst" in sys_.lower(): module = "COMPILE"
    elif "intelligence analyst" in sys_.lower() or "analyze" in sys_.lower()[:200]: module = "ANALYST"
    elif "you are a" in sys_.lower()[:10] or "you are b" in sys_.lower()[:10] or "you are c" in sys_.lower()[:10]: module = "GEN"
    elif "state" in sys_.lower()[:80] or "extract" in sys_.lower()[:80]: module = "EXTRACT"
    elif "reconcil" in sys_.lower(): module = "RECON"
    else: module = "?"

    # Pull round and rounds remaining from user prompt
    m_round = re.search(r"Round:\s*(\d+)(?:\s*of\s*(\d+))?", user)
    m_rem = re.search(r"Rounds remaining:\s*(\S+)", user)
    rnd = m_round.group(0) if m_round else "?"
    rem = m_rem.group(0) if m_rem else "?"

    # Pull faction id from sys prompt "You are X"
    m_fac = re.search(r"You are (\w+)", sys_)
    fac = m_fac.group(1) if m_fac else "?"

    resp = c.get("response") or ""
    resp_str = resp if isinstance(resp, str) else str(resp)
    resp_preview = resp_str[:60].replace("\n", " ")
    print(f"{i:02d} {module:7s} fac={fac:4s} | {rnd:20s} | {rem:25s} | resp[0:60]={resp_preview!r}")
