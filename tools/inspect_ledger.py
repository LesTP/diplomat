"""Quick cost ledger inspection."""
import json
import tempfile
from pathlib import Path
from collections import defaultdict

ledger = Path(tempfile.gettempdir()) / "diplomat_selfplay" / "cost_ledger.jsonl"
print(f"Ledger: {ledger}")
if not ledger.exists():
    print("NO LEDGER FOUND")
    raise SystemExit

entries = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines() if line.strip()]
print(f"Total entries: {len(entries)}")
total = sum(e.get("cost_usd", 0) for e in entries)
print(f"Total spent: ${total:.4f}")

by_op = defaultdict(lambda: {"count": 0, "cost": 0.0})
for e in entries:
    op = e.get("operation_name", "?")
    by_op[op]["count"] += 1
    by_op[op]["cost"] += e.get("cost_usd", 0)

print("\nBy operation:")
for op, d in sorted(by_op.items(), key=lambda x: -x[1]["cost"]):
    print(f"  {op:30s} {d['count']:3d} calls  ${d['cost']:.4f}")

# Show timeline of cumulative spend (might cross the $2 per-round budget threshold)
print("\nCumulative spend timeline (first 30, last 10):")
running = 0.0
for i, e in enumerate(entries):
    running += e.get("cost_usd", 0)
    if i < 30 or i >= len(entries) - 10:
        print(f"  [{i:3d}] +${e.get('cost_usd', 0):.4f}  running=${running:.4f}  ts={e.get('timestamp', '?')[-8:]}")
    elif i == 30:
        print("  ...")

print(f"\nFinal running: ${running:.4f}")
print(f"Per-round budget configured: $2.00 (DiplomatCostGate)")
print(f"Session budget configured: $20.00 (CostBudget)")
