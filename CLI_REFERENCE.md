# Diplomat — CLI Reference

Single-page index of every command-line entry point in the project. Each entry
shows flags, defaults, when to use it, and (where useful) a working example.
Cross-references point at fuller discussion in `TUNING.md`, `DEVPLAN.md`,
`RUN_PROTOCOL.md`, or `DEVLOG.md`.

**Conventions:**
- Required flags marked `*`
- Defaults shown in `[brackets]`
- All commands assume `PYTHONPATH=src` and run from project root
- Live-LLM commands assume `.env` contains the appropriate provider keys

---

## Quick index by purpose

| I want to... | Use |
|---|---|
| Run the production Telegram bot | [`tools/service.sh`](#toolsservicesh--bot-lifecycle-manager) (wraps [`src/main.py`](#srcmainpy--diplomat-bot-production-entry-point)) |
| Run a multi-agent self-play game | [`tests.self_play.run_simulation`](#testsself_playrun_simulation--multi-agent-self-play-runner) |
| Validate plumbing without spending money | `--dry-run` flag on `run_simulation` |
| Compile a narrative scenario into personas | [`tools.scenario_compiler`](#toolsscenario_compiler--narrative--scored-personas) |
| Check providers are reachable before a live run | [`tests.self_play.probe_providers`](#testsself_playprobe_providers--live-provider-auth--parse-check) |
| Assert dry-run output meets invariants | [`tests.self_play.verify_dryrun`](#testsself_playverify_dryrun--assert-dry-run-output-invariants) |
| Check a scenario has a non-trivial optimum before running | [`tests.self_play.verify_scenario_optimum`](#testsself_playverify_scenario_optimum--enumerate-scenario-outcomes) |
| Get a post-game report | [`tests.self_play.analysis`](#testsself_playanalysis--post-game-report) |
| Run prompt-quality regression scenarios | [`tests.prompt_regression.runner`](#testsprompt_regressionrunner--scenario-based-prompt-eval) |
| Inspect the cost ledger | [`tools/inspect_ledger.py`](#toolsinspect_ledgerpy) |
| Dig into a dry-run result | [`tools/inspect_dryrun.py`](#toolsinspect_dryrunpy) |
| Process iteration logs | [`tools/digest_logs.py`](#toolsdigest_logspy) |

---

## Production

### `src/main.py` — Diplomat bot (production entry point)

Direct invocation. Most operators should use `tools/service.sh` instead
(see below) — it wraps this with nohup + PID tracking + log redirection.

```bash
PYTHONPATH=src python src/main.py
```

No CLI flags. Configuration via environment variables (read from `.env` or shell):

| Env var | Required? | Purpose |
|---|---|---|
| `DIPLOMAT_PIPELINE_CONFIG` | optional | Path to `pipeline.yaml`; defaults to `config/pipeline.yaml` |
| `TELEGRAM_BOT_TOKEN` | yes (live) | Telegram bot token from @BotFather |
| `DIPLOMAT_PUBLIC_CHANNEL_ID` | yes (live) | Public game channel numeric ID |
| `DIPLOMAT_COACHING_CHANNEL_ID` | yes (live) | Operator coaching chat numeric ID |
| `DIPLOMAT_OPERATOR_USER_IDS` | yes (live) | Comma-separated operator Telegram user IDs |
| `OPENAI_API_KEY` | depends | Required when any module routes to `openai` |
| `ANTHROPIC_API_KEY` | depends | Required when any module routes to `anthropic` |
| `GOOGLE_API_KEY` | depends | Required when any module routes to `google` |
| `OPENROUTER_API_KEY` | depends | Required when any module routes to `openrouter` |

Lifecycle (when not using `tools/service.sh`) managed by `config/diplomat.service`
on the Pi (systemd). See `diplomat-testing-doc.md` §5b for two-channel Telegram
setup walkthrough.

### `tools/service.sh` — bot lifecycle manager

The established mechanism for running the bot in the Pi container. Wraps
`src/main.py` with nohup, a PID file (`.diplomat.pid`), and log redirection
(`logs/diplomat.log`). Designed to be callable from inside or outside the
container (wrap with `incus exec claude-code -- bash <path>` from outside).

```bash
bash tools/service.sh start              # background, default config
bash tools/service.sh status             # show PID + running state
bash tools/service.sh logs [N]           # tail N lines (default 50)
bash tools/service.sh stop               # SIGTERM → 5s wait → SIGKILL
bash tools/service.sh restart            # stop + start

# With non-default config:
DIPLOMAT_PIPELINE_CONFIG=config/pipeline.yaml bash tools/service.sh start
```

| Env var | Default | Notes |
|---|---|---|
| `DIPLOMAT_PIPELINE_CONFIG` | `config/pipeline_smoke.yaml` | Override to use production config or any other |

See `SMOKE_RUNBOOK.md` §2 for the canonical wrapped-in-incus invocation
sequence.

---

## Self-play

### `tests.self_play.run_simulation` — multi-agent self-play runner

```bash
# Free dry-run (validates plumbing, no API cost)
python -m tests.self_play.run_simulation --dry-run \
    --rounds 4 --scenario tests/self_play/scenarios/water_rights.md \
    --analysis-json tests/self_play/scenarios/water_rights_compiled/scenario_analysis.json \
    --factions alpha,beta,gamma \
    --output tests/self_play/results/smoke.json

# Live single-provider game
python -m tests.self_play.run_simulation \
    --rounds 4 --scenario tests/self_play/scenarios/water_rights.md \
    --output tests/self_play/results/run9.json

# Live multi-provider game (per-faction Generator)
python -m tests.self_play.run_simulation \
    --rounds 4 --scenario tests/self_play/scenarios/water_rights.md \
    --analysis-json tests/self_play/scenarios/water_rights_compiled/scenario_analysis.json \
    --per-faction-providers '{"alpha":{"provider":"openai","model":"gpt-4.1-mini"},"beta":{"provider":"anthropic","model":"claude-haiku-4-5"},"gamma":{"provider":"google","model":"gemini-2.5-flash-lite"}}' \
    --output tests/self_play/results/run9_multi.json
```

| Flag | Default | Notes |
|---|---|---|
| `--rounds` | `4` | Number of game rounds |
| `--factions` | `alpha,beta,gamma` | Comma-separated faction IDs. Auto-renamed when `--scenario` provides its own faction names. |
| `--output` * | — | Results JSON path |
| `--scenario` | — | Path to scenario `.md` for LLM compilation into per-faction personas |
| `--scenario-title` | `"a multi-party negotiation"` | Title injected into persona headers |
| `--analysis-json` | — | Skip live compilation; load pre-existing `scenario_analysis.json`. Requires `--scenario` for the seed message. Preserves hand-tuned BATNAs across runs. |
| `--batna-fraction` | `0.50` | Target BATNA as fraction of each faction's max possible score during compilation. See `TUNING.md` §1 BATNA tuning. Ignored with `--analysis-json` (analysis is already final). |
| `--per-faction-providers` | — | JSON map `{faction:{provider,model}}` — overrides only the Generator slot per faction. Other modules stay on shared primary/secondary. |
| `--dry-run` | `false` | Zero-cost path: `DryRunLLMClient` returns canned responses. Use before any live multi-provider run. See `RUN_PROTOCOL.md`. |

**Workflow recommendations:**
- Always dry-run first to catch plumbing bugs (~$0 instead of ~$1)
- For multi-provider runs, probe each provider live with `probe_providers` (~$0.003) before the real run
- Pair every live run with `verify_dryrun` for the same `--rounds`/`--num-factions` to assert invariants

### `tests.self_play.probe_providers` — live provider auth + parse check

```bash
python -m tests.self_play.probe_providers \
    --providers '{"openai":{"provider":"openai","model":"gpt-4.1-mini"},"anthropic":{"provider":"anthropic","model":"claude-haiku-4-5"},"google":{"provider":"google","model":"gemini-2.5-flash-lite"}}' \
    --max-tokens 500
```

| Flag | Default | Notes |
|---|---|---|
| `--providers` * | — | JSON map of label → `{provider, model}`. Same shape as `--per-faction-providers`. |
| `--max-tokens` | `50` | ⚠️ Gemini 2.5 **flash and pro** burn tokens on internal thinking; default 50 returns only ` ``` `. Use ≥500 for those. `gemini-2.5-flash-lite` has no thinking mode and is unaffected. See `TUNING.md` §1 thinking-token gotcha. |

Exit 0 if every probe passes; nonzero on any failure. ~$0.001 per probe call.
Run before every live multi-provider simulation per `RUN_PROTOCOL.md`.

### `tests.self_play.verify_dryrun` — assert dry-run output invariants

```bash
python -m tests.self_play.verify_dryrun \
    --results tests/self_play/results/smoke.json \
    --rounds 4 --num-factions 3 --adversarial \
    --expect-providers '{"alpha":"openai","beta":"anthropic","gamma":"google"}'
```

| Flag | Default | Notes |
|---|---|---|
| `--results` * | — | Results JSON from `run_simulation --dry-run` |
| `--rounds` | `4` | Expected round count |
| `--num-factions` | `3` | Expected faction count |
| `--adversarial` | `true` | Assert ADV calls fired (F × R count). Pass even when set; flag is a boolean store-true. |
| `--expect-providers` | — | JSON map `{faction:provider}` asserting per-faction Generator routing. Catches provider-routing regressions cheaply. |

Invariants checked include: per-round GEN counts, EXTRACT count, ADV count, endgame marker placement, **SCORE call presence** (added 2026-05-30 after LoggingLLMClient unwrap fix), per-faction provider routing.

### `tests.self_play.verify_scenario_optimum` — enumerate scenario outcomes

```bash
python -m tests.self_play.verify_scenario_optimum \
    --analysis tests/self_play/scenarios/water_rights_compiled/scenario_analysis.json \
    --top-n 10
```

| Flag | Default | Notes |
|---|---|---|
| `--analysis` * | — | Path to `scenario_analysis.json` |
| `--top-n` | `10` | Number of top deals (by sum-of-scores) to print |

Reports per-faction max possible deal, BATNA, "good deal" threshold; all
possible deals (cartesian product); Pareto frontier size; how many deals beat
all BATNAs; logrolling quality. Use **before** spending money on a live run
to confirm a non-trivial optimum exists.

### `tests.self_play.analysis` — post-game report

```bash
python -m tests.self_play.analysis --results tests/self_play/results/run9.json
```

| Flag | Default | Notes |
|---|---|---|
| `--results` * | — | Results JSON from `run_simulation` (live or dry-run) |

Prints per-agent summary, communication patterns, round-by-round responses,
and a promise cross-reference table.

---

## Tools

### `tools.scenario_compiler` — narrative → scored personas

```bash
# Default 0.50 BATNA fraction (moderate pressure)
python -m tools.scenario_compiler \
    --scenario tests/self_play/scenarios/water_rights.md \
    --output-dir tests/self_play/scenarios/water_rights_compiled \
    --title "Clearwater River Basin"

# High-pressure variant for skill-testing runs
python -m tools.scenario_compiler \
    --scenario tests/self_play/scenarios/water_rights.md \
    --batna-fraction 0.65
```

| Flag | Default | Notes |
|---|---|---|
| `--scenario` * | — | Path to scenario text/markdown file |
| `--faction` | (all) | Generate persona for one faction only |
| `--output-dir` | (scenario dir) | Where to write `scenario_analysis.json` and persona `.txt` files |
| `--title` | `"a multi-party negotiation"` | Persona header title |
| `--batna-fraction` | `0.50` | Target BATNA as fraction of each faction's max possible score. Same flag as on `run_simulation.py`. See `TUNING.md` §1 BATNA tuning for full semantics (higher = more pressure to find Pareto deals; lower = easier to settle for any deal). |

After compilation, prints any per-faction BATNA pressure warnings from
`validate_batna_pressure()`. Warnings only — never blocks compilation.

---

## Prompt regression

### `tests.prompt_regression.runner` — scenario-based prompt eval

```bash
# Free: extraction scenarios only (uses RuleBasedExtractor)
python -m tests.prompt_regression.runner \
    --scenarios tests/prompt_regression/scenarios \
    --module extraction

# Paid: all scenarios including generation (live LLM judge calls)
python -m tests.prompt_regression.runner \
    --scenarios tests/prompt_regression/scenarios
```

| Flag | Default | Notes |
|---|---|---|
| `--scenarios` * | — | Directory of scenario JSON files |
| `--module` | (all) | Filter by module: `extraction`, `generation`, `analyst`, `adversarial` |

Free for extraction scenarios. Generation scenarios require an injected
live LLM client and cost ~USD 0.05 per run with commodity-tier models.
See `diplomat-testing-doc.md` §4.

---

## Inspection tools (mostly fixed-input scripts)

### `tools/inspect_dryrun.py`

```bash
python tools/inspect_dryrun.py
```

Reads `tests/self_play/results/dryrun_v1.json` (hardcoded path) and prints GEN
call counts by faction × round. Edit the script's `Path(...)` line to point at
a different results file. (Not yet flag-driven.)

### `tools/inspect_ledger.py`

```bash
python tools/inspect_ledger.py                  # production ledger (data/cost_ledger.jsonl)
python tools/inspect_ledger.py --selfplay       # self-play temp ledger
python tools/inspect_ledger.py --path some/path # explicit path
python tools/inspect_ledger.py --show 50        # more timeline rows
```

| Flag | Default | Notes |
|---|---|---|
| `--selfplay` | off | Use `$TMPDIR/diplomat_selfplay/cost_ledger.jsonl` instead of production |
| `--path PATH` | — | Explicit path (overrides both above) |
| `--show N` | `30` | Leading-rows count in the cumulative-spend timeline (trailing rows = max(10, N/3)) |

Prints total entries, total spend, by-operation breakdown, by-model
breakdown, cumulative timeline, and any failures. Use after a live run
to sanity-check costs against the LLM provider dashboard.

### `tools/inspect_run7.py`

Run-7-specific inspector with a hardcoded results path. Kept for historical
reference; safe to skip unless you're re-analyzing Run 7.

### `tools/digest_logs.py`

```bash
python tools/digest_logs.py logs/loop/iteration_008.txt iteration_009.txt
python tools/digest_logs.py --range 8 12             # iterations 8-12
python tools/digest_logs.py --range 8 12 logs/loop   # with explicit log dir
```

Compresses long iteration `.txt` logs (~300-500 lines) into concise summaries
(~10-30 lines): errors, test failures, file creations, commits, decisions.

### `tools/parse_jsonl.py` / `tools/parse_codex_jsonl.py`

```bash
python tools/parse_jsonl.py < input.jsonl > output.txt
python tools/parse_jsonl.py --meta meta.json < input.jsonl > output.txt
```

| Flag | Default | Notes |
|---|---|---|
| `--meta` | — | Path to write metadata extracted from the JSONL stream |

`parse_codex_jsonl.py` is the Codex-specific variant.

### `tools/service.sh`, `tools/state_machine.sh`

Shell helpers; read their first lines for usage notes.

---

## Toolkit (separate repo)

Toolkit lives at `../toolkit` and exports functions Diplomat calls. No direct
CLI; behavior controlled by Diplomat-side flags and `pipeline.yaml`. See
`../toolkit/API.md` for function signatures.

Relevant toolkit functions used by Diplomat CLIs above:

- `toolkit.llm_client.complete` / `complete_with_retry` — provider-agnostic LLM call (`complete_with_retry` adds 429/5xx/empty backoff; default `max_attempts=3`, `base_delay=1.0`, `retry_on_empty=True`)
- `toolkit.structured_llm.structured_call` — JSON-schema-enforced LLM call with retry on validation failure
- `toolkit.cost_accountant.CostAccountant.complete` — wraps `complete_with_retry` with budget check + ledger write

---

## Common workflows

**Tune-then-run loop:**
```bash
# 1. Compile scenario at target pressure (warnings print if LLM under-sets BATNAs)
python -m tools.scenario_compiler --scenario X.md --batna-fraction 0.55

# 2. Confirm the resulting analysis has a non-trivial optimum
python -m tests.self_play.verify_scenario_optimum --analysis X_compiled/scenario_analysis.json

# 3. Dry-run end-to-end (free)
python -m tests.self_play.run_simulation --dry-run --rounds 4 \
    --scenario X.md --analysis-json X_compiled/scenario_analysis.json \
    --output results/dryrun.json

# 4. Verify dry-run invariants
python -m tests.self_play.verify_dryrun --results results/dryrun.json --rounds 4 --num-factions 3

# 5. Probe providers (~$0.003)
python -m tests.self_play.probe_providers --providers '{"a":{"provider":"openai","model":"gpt-4.1-mini"}}'

# 6. Live run
python -m tests.self_play.run_simulation --rounds 4 \
    --scenario X.md --analysis-json X_compiled/scenario_analysis.json \
    --output results/live.json

# 7. Inspect
python -m tests.self_play.analysis --results results/live.json
python tools/inspect_ledger.py
```

See `RUN_PROTOCOL.md` for the canonical version of this protocol with skip
rules and abort conditions. See `SMOKE_RUNBOOK.md` for the operator-side
procedure to validate the Diplomat bot on the Raspberry Pi after code changes.

---

## Change history

| Date | Change |
|---|---|
| 2026-05-30 | Initial draft — covers production entry, self-play, scenario_compiler, prompt regression. |
| 2026-05-30 | Expanded: added inspection-tools section, env-var table for `main.py`, workflow examples, by-purpose quick index, toolkit cross-reference, examples for every command. |
| 2026-05-30 | Documented `tools/service.sh` (the actual bot-lifecycle mechanism — nohup-based wrapper around `src/main.py`). Updated `tools/inspect_ledger.py` entry to match the new flag-driven version (`--selfplay`, `--path`, `--show`). Updated by-purpose quick index to route "run the bot" at `service.sh`. |
