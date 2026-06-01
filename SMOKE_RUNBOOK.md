# SMOKE_RUNBOOK — Telegram coaching/review smoke

> **Scope.** Validates the Telegram bot's **coaching + review** role.
> Production game traffic is **not** expected to flow through Telegram —
> it comes via `ClankmatesTransport` (or future equivalents). Anything
> that needs non-operator faction senders belongs in Layer 3 integration
> tests, Layer 4 self-play, or a future Clankmates smoke — **not here.**

> **Last run: 2026-05-31, CLOSED for coaching scope.** Pre-flight + bot
> startup via tmux + all coaching-side verifications passed. Real fixes
> shipped: `toolkit/llm_client/providers.py` (gpt-5.x / o-series
> `max_completion_tokens`), `tests/integration/test_failure_handling.py`
> (Phase 18 signature drift). Full close-out in `DEVLOG.md` Phase 19
> "Smoke close-out (coaching scope)" entry. Game-traffic verification
> items moved to a new "Layer 3 integration tests for Phase 18 paths"
> NEXT_STEPS item.

Companion to `diplomat-testing-doc.md` §5b (Phase 16 baseline smoke
checklist) and `CLI_REFERENCE.md` `tools/service.sh` section (bot
lifecycle on the Pi).

---

## 1. Pre-flight

```bash
# Container alive + workspace mounted
incus list claude-code
incus exec claude-code -- ls /home/claude/workspace/diplomat/src/main.py
incus exec claude-code -- ls /home/claude/workspace/toolkit/src/toolkit

# Toolkit editable + Phase 19 surface
incus exec claude-code -- bash -c "cd /home/claude/workspace/diplomat && \
  .venv/bin/python -c 'import toolkit; print(toolkit.__file__)' && \
  .venv/bin/python -c 'from toolkit.llm_client import complete_with_retry; print(\"retry OK\")' && \
  .venv/bin/python -c 'from toolkit.cost_accountant import normalize_model_name; print(\"normalize OK\")' && \
  .venv/bin/python -c 'from modules.reconciliation import StateReconciler; print(\"reconciler OK\")'"

# .env keys present
incus exec claude-code -- bash -c "grep -E '^(TELEGRAM_BOT_TOKEN|DIPLOMAT_PUBLIC_CHANNEL_ID|DIPLOMAT_COACHING_CHANNEL_ID|DIPLOMAT_OPERATOR_USER_IDS|OPENAI_API_KEY)=' /home/claude/workspace/diplomat/.env | cut -d= -f1"

# Test suite (expected: 284 passed, ~17s on container)
incus exec claude-code -- bash -c "cd /home/claude/workspace/diplomat && \
  PYTHONPATH=src .venv/bin/python -m pytest tests/ -q"

# Cost ledger baseline (note line count for post-smoke diff)
incus exec claude-code -- bash -c "wc -l /home/claude/workspace/diplomat/data/cost_ledger.jsonl 2>/dev/null || echo 'ledger does not exist yet'"
```

If toolkit imports come from `/home/claude/workspace/toolkit/` — editable
install is correct. Otherwise `incus exec claude-code -- bash -c "cd
/home/claude/workspace/diplomat && .venv/bin/python -m pip install -e
../toolkit"`.

---

## 2. Start the bot

Production lifecycle on the Pi uses `tools/service.sh`, which starts the bot
inside the long-lived `bot` tmux session (the same one supervising codexbot).
The script is safe to call through `incus exec`.

```bash
incus exec claude-code -- bash /home/claude/workspace/diplomat/tools/service.sh start

# Verify
incus exec claude-code -- bash /home/claude/workspace/diplomat/tools/service.sh status
incus exec claude-code -- bash -c "tail -10 /home/claude/workspace/diplomat/logs/diplomat.log"
```

Expect: `diplomat` window in list, `DIPLOMAT ONLINE - Round 1 - england
- session budget $2.00` in log.

Production config (Anthropic + adversarial enabled): swap
`DIPLOMAT_PIPELINE_CONFIG=config/pipeline.yaml` into the start environment.
Cost ~$0.05–0.15/round vs ~$0.005–0.01.

---

## 3. Coaching-side verification

Items that need non-operator faction traffic have been **removed** from
this runbook and reassigned. See the "Removed (out of Telegram scope)"
block below.

Before sending commands, verify structured logs are present:

```bash
incus exec claude-code -- bash -c "tail -80 /home/claude/workspace/diplomat/logs/diplomat.log"
```

Look for `startup.online` after launch. During `/preview` and any injected
game-traffic test, expect records such as `event.received`, `event.tagged`,
`event.routed`, `extraction.scheduled`, `extraction.start`,
`extraction.complete`, `pipeline.trigger`, `pipeline.complete`, and
`event.sent`. If more detail is needed, restart with
`DIPLOMAT_LOG_LEVEL=DEBUG`.

- [ ] **`/status`** — round number + budget remaining
- [ ] **`/state`** — structured state output (promises, coalitions, inconsistencies)
- [ ] **`/commands`** — full command list
- [ ] **`/ledger`** — spend matches on-disk `data/cost_ledger.jsonl` total
- [ ] **`/preview`** — triggers response pipeline; draft + (optional) adversarial appear in coaching channel; `/approve` / `/edit: ...` / `/block` work as expected
- [ ] **Two-channel routing** — operator commands respond on coaching only, never on public
- [ ] **Unknown command** — receives polite "unknown command" reply
- [ ] **Cost ledger entries** for `/preview` show realistic per-call cost (~$0.0005–$0.005 on gpt-5.4-mini, NOT $0.05+ which would mean the dated-pricing fix isn't active):
  ```bash
  incus exec claude-code -- bash -c "cd /home/claude/workspace/diplomat && \
    PYTHONPATH=src .venv/bin/python tools/inspect_ledger.py --show 30"
  ```

### Removed (out of Telegram scope, see new venues)

| Original item | Right venue |
|---|---|
| §3.1 game-message → extraction → state update | Layer 2 prompt regression (`tests/prompt_regression/scenarios/extraction/`) + Layer 3 transcript replay |
| §3.2 debounce burst (Phase 18.6) | Layer 3 integration — *new test needed*; see NEXT_STEPS "Layer 3 integration tests for Phase 18 paths" |
| §3.3 round-end → analyst | Already covered by 8 self-play runs (TUNING_LOG) |
| §3.8 reconciler dedup / fulfillment / inconsistency | Layer 3 integration — *new tests needed*; Run 7 self-play covered dedup live |
| §3.9 endgame markers (PENULTIMATE / FINAL) | Already covered by self-play Run 7 + Run 8 |

The Phase 18 production code (debounce rewrite, structured_call rewiring,
cost-accountant wiring, reconciler, total_rounds config) is exercised in
self-play. The remaining gap is **deterministic Layer 3 integration**
coverage for debounce burst + the three reconciler paths that haven't
fired in self-play — tracked in NEXT_STEPS.

---

## 4. Post-smoke

```bash
# Stop bot
incus exec claude-code -- sudo -u claude tmux kill-window -t bot:diplomat
incus exec claude-code -- sudo -u claude tmux list-windows -t bot   # confirm gone

# Diff cost ledger
incus exec claude-code -- bash -c "cd /home/claude/workspace/diplomat && \
  PYTHONPATH=src .venv/bin/python tools/inspect_ledger.py --show 30"
```

Capture results in a new `DEVLOG.md` entry (date, pass/fail per
checklist item, any new gotchas, cost ledger before/after).

Revert smoke setup edits if not keeping:
- `config/pipeline_smoke.yaml` `game.total_rounds: 4` (only matters if a
  future smoke explicitly tests endgame markers via `/preview` — Telegram
  smokes don't exercise rounds anymore)

---

## 5. Abort conditions

Stop the smoke and investigate (don't push through) if:

- Bot fails to start with config or import error → fix locally before continuing
- Cost ledger entries show $0.01+ per `/preview` call on gpt-5.4-mini → dated-pricing fix isn't active; reinstall toolkit editable
- Review gate doesn't respond to `/approve` → `TelegramReviewGate` may have stale state; restart bot via §2
- Toolkit `complete_with_retry` / `normalize_model_name` raise `ImportError` → toolkit in container is pre-Phase-19; reinstall editable
- Operator commands respond on the **public** channel (should be coaching-only) → channel-routing regression; check `transport._channel_for_chat`

---

## Change history

| Date | Change |
|---|---|
| 2026-05-30 | Initial draft. Covers Phase 18 + Phase 19 deltas since Phase 16 baseline. |
| 2026-05-30 | §1 + §2 + §5 rewritten for actual deployment architecture (incus container, workspace mount, venv inside container). |
| 2026-05-30 | §1.5 + §2 corrected to use `tools/service.sh` defaulting to `pipeline_smoke.yaml`. |
| 2026-05-31 | **Smoke run, partial.** §1 collapsed to status summary (pre-flight done, 284 tests pass). §2 rewritten: `tools/service.sh` does not work via `incus exec`; working pattern is `incus exec -- sudo -u claude tmux new-window -t bot -n diplomat ...`. Fixed `python` → `.venv/bin/python` throughout. Test count updated 280 → 284. |
| 2026-05-31 | Cleanup pass: removed §4 (Known gaps — FIXED 2026-05-30, live in §3.8/§3.9). Removed §5.5 (systemd install). Renumbered §5. |
| 2026-05-31 | **Smoke CLOSED for coaching scope.** Rewrote entire runbook: this is now a coaching/review smoke. Removed §3.1 / 3.2 / 3.3 / 3.8 / 3.9 (require non-operator faction traffic which is not a Telegram concern — Clankmates or equivalent is the game-traffic transport in production). Moved unverified extraction/debounce/reconciler/round-flow items to "Layer 3 integration tests for Phase 18 paths" in NEXT_STEPS. Final shape: pre-flight + tmux start + 8-item coaching checklist + post-smoke cleanup. ~155 lines (from 219, originally 377). |
