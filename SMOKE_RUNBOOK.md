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

**Architecture reminder.** The Pi mounts the network share, and an **incus
container `claude-code`** re-mounts that share at
`/home/claude/workspace/`. The diplomat venv lives **inside the container**
at `/home/claude/workspace/diplomat/.venv` (not on the share). Code edits
made on the P: share are visible inside the container immediately (same
files via the mount), but the venv + Python must be reached via
`incus exec`. Almost every command below is prefixed accordingly.

### 1.1 No code sync needed

Code on the P: share *is* code in the container (same files via mount).
If the bot was already running in foreground or systemd, restart it to
pick up Python import changes — but you don't need to `git pull`.

### 1.2 Verify the container is alive and reachable

```bash
incus list claude-code
# Should show RUNNING.

incus exec claude-code -- ls /home/claude/workspace/diplomat/src/main.py
incus exec claude-code -- ls /home/claude/workspace/toolkit/src/toolkit
# Both should succeed (workspace mounted).
```

### 1.3 Verify the venv + toolkit + Phase 19 surface

This is the single most important pre-flight check.

```bash
incus exec claude-code -- bash -c "cd /home/claude/workspace/diplomat && \
  .venv/bin/python --version && \
  .venv/bin/python -c 'import toolkit; print(toolkit.__file__)' && \
  .venv/bin/python -c 'from toolkit.llm_client import complete_with_retry; print(\"retry OK\")' && \
  .venv/bin/python -c 'from toolkit.cost_accountant import normalize_model_name; print(\"normalize OK\")' && \
  .venv/bin/python -c 'from modules.reconciliation import StateReconciler; print(\"reconciler OK\")'"
```

Expected output (5 lines, no errors):
```
Python 3.X.Y
/home/claude/workspace/toolkit/src/toolkit/__init__.py
retry OK
normalize OK
reconciler OK
```

If line 2 shows a `site-packages/` path instead of `/home/claude/workspace/`,
the toolkit install is non-editable. Re-install editable:

```bash
incus exec claude-code -- bash -c "cd /home/claude/workspace/diplomat && \
  .venv/bin/python -m pip install -e ../toolkit"
```

If lines 3-5 fail with ImportError, the toolkit version in the container
is pre-Phase-19. Same fix.

If `modules.reconciliation` import fails (line 5), check `PYTHONPATH=src`
is being passed when needed — it's not in this raw probe.

### 1.4 Verify `.env`

```bash
incus exec claude-code -- bash -c "cd /home/claude/workspace/diplomat && \
  grep -E '^(TELEGRAM_BOT_TOKEN|DIPLOMAT_PUBLIC_CHANNEL_ID|DIPLOMAT_COACHING_CHANNEL_ID|DIPLOMAT_OPERATOR_USER_IDS|OPENAI_API_KEY|ANTHROPIC_API_KEY)=' .env | cut -d= -f1"
```

All 6 keys should print (`TELEGRAM_BOT_TOKEN`, `DIPLOMAT_PUBLIC_CHANNEL_ID`,
`DIPLOMAT_COACHING_CHANNEL_ID`, `DIPLOMAT_OPERATOR_USER_IDS`,
`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`). Don't echo values.

### 1.5 Choose pipeline config

Two configs are available:

| Config | When | What it gives you |
|---|---|---|
| `config/pipeline_smoke.yaml` | **This smoke** — matches what the bot was running before | Both providers OpenAI (no Anthropic key needed), all tiers `gpt-5.4-mini`, `TelegramReviewGate` already set, tight budgets ($0.50/round, $2.00/session), adversarial disabled |
| `config/pipeline.yaml` | Production (real game with full quality) | OpenAI + Anthropic, varied tiers, defaults to `AutoApproveReviewGate` (safe), larger budgets, adversarial enabled |

For this re-smoke, **stay on `pipeline_smoke.yaml`** — it's what was running
before, has TelegramReviewGate already, and is cheap. No edits to it needed.
The default for `tools/service.sh` is already `pipeline_smoke.yaml`.

If you want to test the production config later (with Anthropic secondary
and adversarial), set `DIPLOMAT_PIPELINE_CONFIG=config/pipeline.yaml` when
running the service.

### 1.6 (Optional) Enable endgame markers

For an even more realistic smoke that exercises §3.9, uncomment the
`game:` section in `config/pipeline_smoke.yaml` (or `config/pipeline.yaml`
if you're using that). The block isn't currently in `pipeline_smoke.yaml`
— add it after `cost:` if you want endgame markers:

```yaml
game:
  total_rounds: 4    # any small number; lets you cycle through PENULTIMATE/FINAL
```

Skip if you'd rather keep the smoke minimal and verify endgame markers
later. Either way is fine — production default leaves it off.

### 1.7 Run the test suite inside the container

```bash
incus exec claude-code -- bash -c "cd /home/claude/workspace/diplomat && \
  PYTHONPATH=src .venv/bin/python -m pytest tests/ -q"
```

Expected: 280 passed. On the container's local disk (vs the P: network
share where tests run on Windows), the pre-existing Windows/network-share
timing flakes should NOT reproduce. If anything other than "280 passed"
appears, stop and investigate before the live smoke.

### 1.8 Snapshot the current cost ledger

Production ledger lives in `data/cost_ledger.jsonl` per `pipeline.yaml`
`cost.ledger_path` (not the self-play temp path). Use the production
inspector:

```bash
incus exec claude-code -- bash -c "cd /home/claude/workspace/diplomat && \
  python tools/inspect_ledger.py"
```

If "NO LEDGER FOUND" or "(empty ledger)" — that's fine, file gets created
on first call. Note the line count for the diff:

```bash
incus exec claude-code -- bash -c "cd /home/claude/workspace/diplomat && \
  wc -l data/cost_ledger.jsonl 2>/dev/null || echo 'ledger does not exist yet'"
```

---

## 2. Start the bot

### 2.1 Start via `tools/service.sh` (matches prior deployment)

The bot was previously run via `tools/service.sh start` — a nohup-based
mini-service manager. Use the same mechanism for the smoke so you're
testing the actual deployment path.

```bash
# Start the bot (uses pipeline_smoke.yaml by default)
incus exec claude-code -- bash /home/claude/workspace/diplomat/tools/service.sh start

# Confirm it's running
incus exec claude-code -- bash /home/claude/workspace/diplomat/tools/service.sh status

# Tail the log to watch live activity
incus exec claude-code -- bash /home/claude/workspace/diplomat/tools/service.sh logs 100
```

**Expected first lines in `logs/diplomat.log`:**
```
DIPLOMAT ONLINE - Round 1 - <faction_id> - session budget $2.00
```

(Note: `$2.00` not `$10.00` because `pipeline_smoke.yaml` has a tight
session budget. Production `pipeline.yaml` would show `$10.00`.)

For continuous log watching:

```bash
incus exec claude-code -- bash -c "tail -f /home/claude/workspace/diplomat/logs/diplomat.log"
```

(Open this in a second terminal so you can keep the first one for issuing
service commands.)

### 2.2 Stop and restart

```bash
incus exec claude-code -- bash /home/claude/workspace/diplomat/tools/service.sh stop
incus exec claude-code -- bash /home/claude/workspace/diplomat/tools/service.sh restart
```

`stop` is graceful (SIGTERM, 5-sec wait, then SIGKILL if still alive).
`restart` is just `stop` + `start`.

### 2.3 If you want production config (with Anthropic + adversarial)

```bash
incus exec claude-code -- bash -c "cd /home/claude/workspace/diplomat && \
  DIPLOMAT_PIPELINE_CONFIG=config/pipeline.yaml bash tools/service.sh start"
```

Requires `ANTHROPIC_API_KEY` in `.env`. Cost will be higher per round
(~$0.05–0.15 vs ~$0.005–0.01 for smoke).

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
- Dated model IDs (e.g. `gpt-4.1-mini-2025-04-14`, `claude-haiku-4-5-20251001`) should resolve correctly via `normalize_model_name`
- gpt-5.x and Gemini 2.5 prices should be accurate

- [ ] After the round-end analyst calls fire (§3.3), inspect the production cost ledger:
  ```bash
  incus exec claude-code -- bash -c "cd /home/claude/workspace/diplomat && \
    python tools/inspect_ledger.py"
  ```
  (Defaults to production `data/cost_ledger.jsonl`. Pass `--selfplay` for the temp self-play ledger.)
- [ ] **NEW entries** (those after §1.8's snapshot) should have realistic per-call costs (e.g. ~$0.0005-$0.005 per analyst call on gpt-5.4-mini, the primary commodity tier), NOT the conservative $15/$75 fallback (would show as $0.01-$0.10 per call for small token counts)
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

### 3.8 Reconciler (wired into production 2026-05-30)

Reconciler is now attached at startup by `src/main.py`. It fires at every
round boundary, before analysts run. Validates the post-round state cleanup
path end-to-end in production.

- [ ] Trigger 2–3 promises from the same faction via game messages in the public channel (e.g. multiple messages mentioning "Alpha commits $2M to Beta", paraphrased)
- [ ] Send `ROUND 1` (or matching `round_detection.pattern`) to trigger round boundary
- [ ] Wait ~10–20 sec for round-boundary processing (reconciler + analysts)
- [ ] `/state` from coaching channel should show **one** promise entry, not three duplicates
- [ ] Cost ledger should show a NEW entry corresponding to the RECON call — easiest to spot via `inspect_ledger.py`:
  ```bash
  incus exec claude-code -- bash -c "cd /home/claude/workspace/diplomat && \
    python tools/inspect_ledger.py | tail -20"
  ```
  Look for the "Cumulative spend timeline" — a new entry should have appeared since §1.8's snapshot, with timestamp near the round-boundary fire.
- [ ] Log output: no exceptions from `_reconcile_state`; if reconciler crashes, orchestrator alerts the operator

**If reconciler fires but doesn't dedup:** reconciler ran but LLM didn't
flag the duplicates as mergeable. Check the LLM's reconciler response in
the log. May indicate the model is too weak — primary commodity tier is
`gpt-5.4-mini`, which should handle this fine; if it doesn't, try bumping
to `default` or `quality` tier in `_attach_reconciler` in main.py.

### 3.9 Endgame markers (configurable as of 2026-05-30)

Persona's `PENULTIMATE` / `FINAL ROUND` blocks render when
`orchestrator.total_rounds` is set. Production now reads
`game.total_rounds` from `pipeline.yaml` when present.

**Optional setup before smoke** — uncomment in `config/pipeline.yaml`:
```yaml
game:
  total_rounds: 4    # short; easy to hit the endgame markers
```

- [ ] Start bot
- [ ] Send a normal game message + `/preview` from coaching channel
- [ ] In the draft sent to coaching, the system prompt context should mention "Round 1 of 4" (header), not just "Round 1"
- [ ] Advance round: send `ROUND 3` in public channel
- [ ] `/preview` again
- [ ] Draft system prompt should contain `### PENULTIMATE ROUND` block
- [ ] Advance to ROUND 4
- [ ] `/preview` should now show `### FINAL ROUND` block instead

If `game.total_rounds` is left commented out, markers don't fire (expected —
production default for unknown-length real games).

---

## 4. Known gaps (don't expect these to work; not blocking)

### 4.1 ~~Reconciler not wired in production~~ — FIXED 2026-05-30

`src/main.py` now attaches a `StateReconciler` to the orchestrator at
startup (commit-ID-pending — see latest `[diplomat] main: wire reconciler...`
commit). Uses the *primary* provider's commodity tier. Reconciliation fires
at the end of every round (before analyst calls) and:

- Merges duplicate promises that the extractor logged with different IDs
- Transitions promises pending → kept/broken when fulfilled or contradicted
- Flags inconsistencies from position shifts
- Catches proposals the per-message extractor missed

**Verification step (added to §3):** see §3.8 below.

### 4.2 ~~Endgame markers don't fire in production~~ — CONFIGURABLE 2026-05-30

`Orchestrator.__init__` now reads optional `game.total_rounds` from
`pipeline.yaml`. When set, `PENULTIMATE` / `FINAL ROUND` blocks in the
persona render correctly. When absent (current default), behavior is
unchanged from prior baseline.

**To enable for the smoke (optional):** uncomment the `game:` block in
`config/pipeline.yaml`:

```yaml
game:
  total_rounds: 6   # or whatever matches the planned game length
```

**Verification step:** see §3.9 below.

### 4.3 Adversarial reader rate

`config/pipeline.yaml` has `adversarial.enabled: true`. This means every
generation triggers an adversarial read — doubles per-response LLM cost.
For the smoke this is fine (cost is pennies). For the real game, consider
disabling if budget is tight; the review gate provides the human-eye check.

---

## 5. Post-smoke

### 5.1 Diff the cost ledger

```bash
# Compare new entries to baseline from §1.8
incus exec claude-code -- bash -c "cd /home/claude/workspace/diplomat && \
  python tools/inspect_ledger.py --show 50"
```

Spot-check:
- "Total entries" went up by ~6-20 (round-boundary + response-pipeline calls during the smoke)
- "Total spent" is in the cents range (e.g. $0.02–0.20), not dollars
- "By operation" shows `analysis`, `generation`, `reconciler` (or similar) — not just `?`
- "By model" shows the dated ID (`gpt-5.4-mini-YYYY-MM-DD`) resolved correctly (cost per entry is realistic — `$0.0005–0.005`-ish per call, NOT `$0.05+` per call which would indicate the fallback hit)
- "Failures" section either absent or contains transient errors only (rate limits, etc.)

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
incus exec claude-code -- bash /home/claude/workspace/diplomat/tools/service.sh stop
incus exec claude-code -- bash /home/claude/workspace/diplomat/tools/service.sh status
```

`stop` is graceful: SIGTERM, 5-sec wait, SIGKILL if still alive. Removes
the PID file.

### 5.4 Capture results

Document outcomes in `DEVLOG.md` under a new "Phase 19 — Live Telegram
re-smoke" entry. Include:
- Date and Pi hostname
- Test suite count on Pi
- Any new gotchas (especially anything that differed from the runbook)
- Cost ledger before/after line counts
- Which checklist items passed, which failed, which were skipped

### 5.5 (Optional) Install as systemd service

The `diplomat.service` unit file exists at `config/diplomat.service` but
the bot has been running via `tools/service.sh` (nohup) — that's the
established pattern. If you want a true systemd service that survives
container reboots automatically:

```bash
incus exec claude-code -- sudo install -m 0644 \
  /home/claude/workspace/diplomat/config/diplomat.service \
  /etc/systemd/system/diplomat.service
incus exec claude-code -- sudo systemctl daemon-reload
incus exec claude-code -- sudo systemctl enable --now diplomat.service
incus exec claude-code -- systemctl status diplomat.service
incus exec claude-code -- journalctl -u diplomat.service -f
```

Requires `sudo` and `systemd` working inside the container. If those
aren't available (e.g. unprivileged container without systemd), keep
running via `tools/service.sh` — it's the established working path. For
restart-on-reboot in that case, add a cron `@reboot` entry or a small
container-startup hook that calls `tools/service.sh start`.

---

## 6. Abort conditions

Stop the smoke and investigate (don't push through) if:

- Bot fails to start with a config or import error → fix locally before continuing
- Cost ledger entries show $0.01+ per analyst call on gpt-5.4-mini → the dated-pricing fix didn't take effect; check toolkit install (§1.3)
- Multi-message burst (§3.2) drops messages → debounce regression; check `_extraction_tasks` set in orchestrator.py
- Review gate doesn't respond to `/approve` → TelegramReviewGate may have stale state; restart bot
- Unexpected 429s on any provider → check `.env` keys and per-provider quotas
- `systemctl status diplomat.service` returns "Unit not found" or "No medium found" → systemd unit isn't installed in the container (it's intentionally not installed). Use foreground mode (§2.1) instead; install systemd post-smoke per §5.5 only if you want it.
- Toolkit import succeeds but `complete_with_retry` / `normalize_model_name` raise ImportError → toolkit version inside container is pre-Phase-19. Reinstall editable per §1.3.

---

## Change history

| Date | Change |
|---|---|
| 2026-05-30 | Initial draft. Covers Phase 18 + Phase 19 deltas since Phase 16 baseline. |
| 2026-05-30 | §1 + §2 + §5 rewritten for the actual deployment architecture: incus container `claude-code` with `/home/claude/workspace/` mount of the P: share; venv inside container. Removed `git pull` step (code-on-Pi = code-on-share, same files via mount). Cost-ledger path corrected from self-play temp dir to production `data/cost_ledger.jsonl`. Added §5.5 optional systemd install. Added two abort conditions covering the "no medium found / unit not found" symptom and pre-Phase-19 toolkit. |
| 2026-05-30 | §1.5 + §2 corrected to match actual deployment mechanism: `tools/service.sh` (nohup-based; the script the bot was actually running under previously), defaulting to `config/pipeline_smoke.yaml` (which already has TelegramReviewGate set). Dropped the "flip review_gate" step since the smoke config has it. `inspect_ledger.py` now used throughout instead of raw `tail`/`wc -l`. §5.5 systemd discussion clarified: nohup is the established path; systemd install is optional / depends on container privilege. |
