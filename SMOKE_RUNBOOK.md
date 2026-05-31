# SMOKE_RUNBOOK — Live Telegram re-smoke on Pi

Manual operator procedure for validating Diplomat on the Raspberry Pi
after Phase 18 + Phase 19 changes. Last live smoke was Phase 16 (Module 12,
2026-05-27). This runbook covers everything that changed since.

**Read once before starting.** ~30-45 minutes if everything works first
try; longer if any check fails.

> Companion to `diplomat-testing-doc.md` §5b (the original Phase 16 smoke
> checklist) and `RUN_PROTOCOL.md` (pre-flight for self-play). This runbook
> is the *delta* check — assumes §5b's baseline still passes.

---

## 1. Pre-flight (do not skip)

### 1.1 Sync code on Pi

```bash
ssh claude@<pi>
cd /home/claude/workspace/diplomat
git fetch && git status -sb
# Confirm we're on main and up-to-date with origin
git pull --ff-only

cd /home/claude/workspace/toolkit
git fetch && git status -sb
git pull --ff-only
```

Latest commits expected (as of 2026-05-30):
- diplomat HEAD: `acae7af [diplomat] docs: close tooling-debt #3...`
- toolkit HEAD: `bce696b cost_accountant: normalize dated model IDs...`

### 1.2 Reinstall toolkit editable

Toolkit shipped two changes since the last smoke (`complete_with_retry`,
`normalize_model_name`). The editable install needs to see them.

```bash
cd /home/claude/workspace/diplomat
.venv/bin/python -m pip install -e ../toolkit
.venv/bin/python -c "from toolkit.llm_client import complete_with_retry; print('retry OK')"
.venv/bin/python -c "from toolkit.cost_accountant import normalize_model_name; print('normalize OK')"
```

Both lines should print without ImportError.

### 1.3 Verify `.env`

```bash
grep -E '^(TELEGRAM_BOT_TOKEN|DIPLOMAT_PUBLIC_CHANNEL_ID|DIPLOMAT_COACHING_CHANNEL_ID|DIPLOMAT_OPERATOR_USER_IDS|OPENAI_API_KEY|ANTHROPIC_API_KEY)=' .env | cut -d= -f1
```

All 6 keys should print. Don't echo values.

### 1.4 Flip review_gate to TelegramReviewGate

Currently `config/pipeline.yaml` defaults to `AutoApproveReviewGate` (safe).
For this smoke we want the real review gate:

```bash
# Confirm current state
grep -A1 'review_gate:' config/pipeline.yaml | head -4
# Should show: class: AutoApproveReviewGate

# Flip it
sed -i 's/class: AutoApproveReviewGate/class: TelegramReviewGate/' config/pipeline.yaml
grep 'class: TelegramReviewGate' config/pipeline.yaml
# Should show one match
```

**Do not commit this change unless you decide to flip the production default.**
Either revert after the smoke (`git checkout config/pipeline.yaml`) or commit
intentionally with a clear message.

### 1.5 Run the full test suite locally on the Pi

```bash
PYTHONPATH=src .venv/bin/python -m pytest tests/ -q
```

Expected: 273 passed + up to 3 pre-existing Windows/network-share timing
flakes. On the Pi (Linux, local disk) the flakes may not reproduce — should
be cleanly 273 passed. If anything else fails, stop and investigate before
the live smoke.

### 1.6 Inspect existing cost ledger (one-time forensic)

```bash
ls -la $TMPDIR/diplomat_selfplay/cost_ledger.jsonl 2>/dev/null || \
    ls -la /tmp/diplomat_selfplay/cost_ledger.jsonl 2>/dev/null
```

If present and large, this is the historical ledger. After the smoke we'll
inspect the *new* entries to confirm the dated-pricing fix took effect.
Note current line count for the diff:

```bash
wc -l /tmp/diplomat_selfplay/cost_ledger.jsonl
```

---

## 2. Start the bot

### 2.1 Foreground mode (recommended for first smoke run)

```bash
cd /home/claude/workspace/diplomat
PYTHONPATH=src .venv/bin/python src/main.py
```

**Expected first-line output:**
```
DIPLOMAT ONLINE - Round 1 - <faction_id> - session budget $10.00
```

If you get import errors or `TELEGRAM_BOT_TOKEN is required`, stop and fix.

### 2.2 (Alternative) systemd mode

```bash
sudo systemctl daemon-reload
sudo systemctl restart diplomat.service
sudo systemctl status diplomat.service
journalctl -u diplomat.service -f
```

---

## 3. Verification checklist

Each item maps to a specific change since Phase 16. Run them in order; later
items depend on earlier ones working.

### 3.1 Phase 16 baseline (regression check)

These were validated in the Phase 16 smoke; just confirm they still work.

- [ ] Bot starts without import errors
- [ ] Send a normal game message from a non-operator account in the public channel
- [ ] `/state` from coaching channel returns structured output
- [ ] `/status` returns round number + budget remaining
- [ ] Operator commands respond on coaching channel only (not public)
- [ ] Two-channel routing works: game-message goes to event store, operator command dispatches

### 3.2 Debounce rewrite (Phase 18.6 — D-20)

The original cancel-and-replace debounce silently dropped burst messages.
The new per-event task set processes every message.

- [ ] In quick succession (under 1 second), send three game messages from different non-operator senders in the public channel
- [ ] After ~2 seconds, send `/state` from coaching channel
- [ ] All three messages should appear in event store (`/state` shows promises or coalitions extracted from each, or at minimum all three event records exist)
- [ ] Cross-check log output: should see three extraction tasks scheduled, not one cancellation

**Pre-fix behavior:** only the last message would be extracted; the first two would be silently dropped.

### 3.3 `structured_call` rewiring (Phase 18.7)

All 4 LLM modules now use `toolkit.structured_llm.structured_call()` for
schema-enforced JSON with retry. Hardest to verify directly — surfaces as
"things still work when LLM returns malformed JSON."

- [ ] Send `ROUND 1` (or whatever matches `round_detection.pattern`) in the public channel
- [ ] Wait for analyst calls to complete (~5-10 sec)
- [ ] `/intel` should show a structured intelligence report
- [ ] No "JSON decode" or "schema validation" errors in the log

Indirect check (if you don't see errors and the report is populated, structured_call is doing its job).

### 3.4 Cost-accountant wiring (Phase 18.8)

Every LLM call should now route through `CostAccountant.complete()` and
write a ledger entry. Combined with the Phase 19 fixes:
- Dated model IDs (e.g. `gpt-4.1-mini-2025-04-14`) should resolve correctly
- gpt-5.x and Gemini 2.5 prices should be accurate

- [ ] After the round-end analyst calls fire (§3.3), check the cost ledger:
  ```bash
  tail -5 /tmp/diplomat_selfplay/cost_ledger.jsonl
  ```
- [ ] **NEW entries** (those after step 1.6's snapshot) should have realistic per-call costs (e.g. ~$0.0005-$0.005 per analyst call on gpt-4.1-mini), NOT the conservative $15/$75 fallback (would show as $0.01-$0.10 per call for small token counts)
- [ ] `/ledger` from coaching channel should match the on-disk total
- [ ] After 4-5 LLM calls, `/ledger` should show non-trivial-but-reasonable spend (think pennies, not dollars)

**Pre-fix:** ledger entries used the $15/$75 fallback → ~40× overestimate.
After this smoke, the *new* entries will be accurate; the *old* ones in the
file remain inflated. Don't be alarmed by historical entries.

### 3.5 Retry-with-backoff (Phase 19, toolkit `complete_with_retry`)

Hard to trigger deliberately — would need to provoke a 429. Two options:

**Option A (passive):** Just run normally and watch logs for any "Retrying
after Nx" messages. If you happen to hit a transient 429 over the course of
the smoke, the bot should recover automatically instead of failing the call.

**Option B (active, optional):** Temporarily set a tiny per-round budget in
`pipeline.yaml` (`per_round_budget_usd: 0.001`) to force the cost gate to
trip, then verify the operator-alert path fires. Reset budget after.

- [ ] No silent failures from transient API issues (if encountered)
- [ ] If a 429 occurs, the retry-with-backoff path triggers and the call eventually succeeds (or fails cleanly after `max_attempts=3`)

### 3.6 Review gate flow (Phase 9 baseline + Phase 16 fixes)

Requires `TelegramReviewGate` (you flipped this in §1.4).

- [ ] Send a direct-address message in public: `Hey <faction_id>, what is your position on trade?`
- [ ] Bot sends a draft + adversarial analysis to coaching channel within ~10 sec
- [ ] Reply `/approve` — response posts to public channel
- [ ] Repeat: send another direct-address; this time `/edit: New text here.` — edited text posts to public
- [ ] Repeat: send another; this time `/block` — operator gets a "blocked" ack; nothing posts to public

### 3.7 Operator commands

- [ ] `/status` shows round + budget
- [ ] `/state` shows promises, coalitions, inconsistencies
- [ ] `/ledger` shows spend (matches `tail` of cost_ledger.jsonl)
- [ ] `/intel` shows latest intelligence report
- [ ] `/divergences` shows analyst disagreements (or "none")
- [ ] `/edits` shows review-gate edit history
- [ ] `/commands` lists all available commands
- [ ] `/preview` triggers the response pipeline without auto-posting
- [ ] Unknown command receives a polite "unknown command" reply

---

## 4. Known gaps (don't expect these to work; not blocking)

### 4.1 Reconciler not wired in production

`src/modules/reconciliation/StateReconciler` exists and is exercised by
self-play (`tests/self_play/game_environment.py` creates one and attaches it
to each orchestrator). **Production `src/main.py` does not.** The
orchestrator's `_reconcile_state()` checks `getattr(self, "reconciler",
None)` and returns silently when missing.

**Consequence for this smoke:** post-round reconciliation (dedup, fulfillment
detection, inconsistency flagging) will not fire. The promise ledger will
have duplicates that self-play would have merged.

**Fix path** (deferred — separate phase): add reconciler wiring to `main.py`
similar to game_environment's setup. ~30 min change. Worth doing before
the first real game but not blocking the smoke.

### 4.2 Endgame markers don't fire in production

`PENULTIMATE` / `FINAL ROUND` markers in `build_round_context` only render
when `orchestrator.total_rounds` is set. Self-play sets it explicitly.
Production doesn't know the round count, so `total_rounds = None` and the
markers never appear.

**Consequence for this smoke:** persona context will not include endgame
reminders. Agents won't get the "close the deal" pressure cue.

**Fix path** (deferred — game-design decision): either ask the moderator
how many rounds the real game has and add a `total_rounds` config option,
or accept that production stays endgame-blind. Tracked in NEXT_STEPS §2.

### 4.3 Adversarial reader rate

`config/pipeline.yaml` has `adversarial.enabled: true`. This means every
generation triggers an adversarial read — doubles per-response LLM cost.
For the smoke this is fine (cost is pennies). For the real game, consider
disabling if budget is tight; the review gate provides the human-eye check.

---

## 5. Post-smoke

### 5.1 Diff the cost ledger

```bash
# Compare new entries to baseline from §1.6
wc -l /tmp/diplomat_selfplay/cost_ledger.jsonl   # should be > baseline
tail -20 /tmp/diplomat_selfplay/cost_ledger.jsonl
```

Spot-check a few new entries:
- `model` field shows the dated ID (e.g. `gpt-4.1-mini-2025-04-14`)
- `cost_usd` is in the cents range, not dollars
- `cumulative_session_usd` is consistent across entries

### 5.2 Restore review_gate (or commit the flip)

If you flipped to `TelegramReviewGate` for the smoke and don't want it as
the new default:

```bash
git checkout config/pipeline.yaml
```

If you do want it as the new default for the real game:

```bash
git add config/pipeline.yaml
git commit -m "[diplomat] pipeline.yaml: switch to TelegramReviewGate for live game"
git push
```

### 5.3 Stop bot

```bash
# Foreground: Ctrl-C
# systemd: sudo systemctl stop diplomat.service
```

### 5.4 Capture results

Document outcomes in `DEVLOG.md` under a new "Phase 19 — Live Telegram
re-smoke" entry. Include:
- Date and Pi hostname
- Test suite count on Pi
- Any new gotchas (especially anything that differed from the runbook)
- Cost ledger before/after line counts
- Which checklist items passed, which failed, which were skipped

---

## 6. Abort conditions

Stop the smoke and investigate (don't push through) if:

- Bot fails to start with a config or import error → fix locally before continuing
- Cost ledger entries show $0.01+ per analyst call on gpt-4.1-mini → the dated-pricing fix didn't take effect; check toolkit install (§1.2)
- Multi-message burst (§3.2) drops messages → debounce regression; check `_extraction_tasks` set in orchestrator.py
- Review gate doesn't respond to `/approve` → TelegramReviewGate may have stale state; restart bot
- Unexpected 429s on any provider → check `.env` keys and per-provider quotas

---

## Change history

| Date | Change |
|---|---|
| 2026-05-30 | Initial draft. Covers Phase 18 + Phase 19 deltas since Phase 16 baseline. |
