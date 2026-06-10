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
| Run a self-play game with one Telegram-coached faction | [`tests.self_play.coached_game`](#testsself_playcoached_game--coached-self-play-runner) |
| Validate plumbing without spending money | `--dry-run` flag on `run_simulation` |
| Compile a narrative scenario into personas | [`tools.scenario_compiler`](#toolsscenario_compiler--narrative--scored-personas) |
| Generate a scenario from outcome-shape constraints | [`tools.scenario_builder`](#toolsscenario_builder--constraint-driven-scenario-generator) |
| Check providers are reachable before a live run | [`tests.self_play.probe_providers`](#testsself_playprobe_providers--live-provider-auth--parse-check) |
| Assert dry-run output meets invariants | [`tests.self_play.verify_dryrun`](#testsself_playverify_dryrun--assert-dry-run-output-invariants) |
| Check a scenario has a non-trivial optimum before running | [`tests.self_play.verify_scenario_optimum`](#testsself_playverify_scenario_optimum--enumerate-scenario-outcomes) |
| Get a post-game report | [`tests.self_play.analysis`](#testsself_playanalysis--post-game-report) |
| Run prompt-quality regression scenarios | [`tests.prompt_regression.runner`](#testsprompt_regressionrunner--scenario-based-prompt-eval) |
| Classify the review-gate edit log (post-game) | [`tools/classify_edit_log.py`](#toolsclassify_edit_logpy--bulk-edit-log-classifier) |
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
| `DIPLOMAT_LOG_LEVEL` | optional | Override `logging.level` from pipeline config (for example `DEBUG` during a smoke) |
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

**Status:** Canonical Pi lifecycle wrapper. The script uses a `diplomat`
window inside the long-lived tmux session `bot` by default, so it survives
`incus exec` cgroup teardown. Override the session with `BOT_TMUX_SESSION`
for tests or parallel deployments.

```bash
incus exec claude-code -- bash /home/claude/workspace/diplomat/tools/service.sh start
incus exec claude-code -- bash /home/claude/workspace/diplomat/tools/service.sh status
incus exec claude-code -- bash /home/claude/workspace/diplomat/tools/service.sh logs 50
incus exec claude-code -- bash /home/claude/workspace/diplomat/tools/service.sh stop
incus exec claude-code -- bash /home/claude/workspace/diplomat/tools/service.sh restart
```

Inside the container/project checkout, the same commands are:

```bash
bash tools/service.sh start              # tmux window, default smoke config
bash tools/service.sh status             # tmux window running state
bash tools/service.sh logs [N]           # tail N lines (default 50)
bash tools/service.sh stop               # kill tmux window
bash tools/service.sh restart            # stop + start
```

| Env var | Default | Notes |
|---|---|---|
| `DIPLOMAT_PIPELINE_CONFIG` | `config/pipeline_smoke.yaml` | Override to use production config or any other |
| `DIPLOMAT_LOG_LEVEL` | config `logging.level` | Temporary log-level override; use `DEBUG` for high-verbosity diagnostics |
| `BOT_TMUX_SESSION` | `bot` | tmux session that supervises the `diplomat` window |

The tmux session must already exist. If it is missing, create it with
`sudo -u claude tmux new-session -d -s bot`. The underlying tmux command runs
as user `claude` unless the script is already running as that user.

**With non-default config:** set
`DIPLOMAT_PIPELINE_CONFIG=config/pipeline.yaml` before `start`. Production
config requires `ANTHROPIC_API_KEY`.

See `SMOKE_RUNBOOK.md` §2 and `diplomat-testing-doc.md` §5b for the Pi
operational context.

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
# OpenRouter example — access 200+ models via one API key
# python -m tests.self_play.run_simulation ... \
#     --per-faction-providers '{"alpha":{"provider":"openrouter","model":"meta-llama/llama-3.3-70b-instruct"},"beta":{"provider":"openrouter","model":"deepseek/deepseek-v3"}}'
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
| `--batna-fraction` | `0.50` | Target BATNA as fraction of each faction's max possible score during compilation. Scalar fallback when `--batna-fractions` is not supplied. See `TUNING.md` §1 BATNA tuning. Ignored with `--analysis-json` (analysis is already final). |
| `--batna-fractions` | — | JSON map `{faction_id: fraction}` for **asymmetric** BATNAs (one faction under pressure, another comfortable). Overrides `--batna-fraction` only for listed factions; unlisted use the scalar fallback. Example: `'{"alpha":0.65,"beta":0.35,"gamma":0.50}'`. Same parsing pattern as `--per-faction-providers`. Ignored with `--analysis-json`. |
| `--game-mode` | — | Runtime override for the compiled scenario's `game_mode` classification. Choices: `cooperative` / `competitive` / `mixed`. Applies a temporary persona overlay without touching `scenario_analysis.json` — lets you re-run the same scenario in a different posture without recompiling. |
| `--per-faction-providers` | — | JSON map `{faction:{provider,model}}` — overrides only the Generator slot per faction. Other modules stay on shared primary/secondary. |
| `--dry-run` | `false` | Zero-cost path: `DryRunLLMClient` returns canned responses. Use before any live multi-provider run. See `RUN_PROTOCOL.md`. |
| `--bare-prompt` | `false` | Ablation mode: disables Extraction, Analyst, Divergence, Reconciliation, Adversarial, and Coaching. Context assembler produces persona + raw transcript only. Results JSON includes `bare_mode: true`. ~10-20× cheaper per game than full mode. See `tests/self_play/bare_mode.py`. |

**Workflow recommendations:**
- Always dry-run first to catch plumbing bugs (~$0 instead of ~$1)
- For multi-provider runs, probe each provider live with `probe_providers` (~$0.003) before the real run
- Pair every live run with `verify_dryrun` for the same `--rounds`/`--num-factions` to assert invariants

### `tests.self_play.coached_game` — coached self-play runner

```bash
# Dry-run wiring check: no Telegram access required
python -m tests.self_play.coached_game --dry-run \
    --coach-faction beta --rounds 4 \
    --scenario tests/self_play/scenarios/water_rights.md \
    --analysis-json tests/self_play/scenarios/water_rights_compiled/scenario_analysis.json \
    --factions alpha,beta,gamma \
    --output tests/self_play/results/coached_dryrun.json

# Live coached run: one faction uses OperatorReviewGate + TelegramBotTransport
python -m tests.self_play.coached_game \
    --coach-faction beta --rounds 4 \
    --scenario tests/self_play/scenarios/water_rights.md \
    --analysis-json tests/self_play/scenarios/water_rights_compiled/scenario_analysis.json \
    --factions alpha,beta,gamma \
    --output tests/self_play/results/coached_live.json
```

| Flag / env | Default | Notes |
|---|---|---|
| `--coach-faction` * | — | Faction id routed through the Telegram-coached pipeline. |
| `--rounds` | `4` | Same as `run_simulation`. |
| `--factions` | `alpha,beta,gamma` | Same as `run_simulation`. |
| `--scenario` | — | Same as `run_simulation`; required for `--analysis-json` because the seed message still comes from the scenario text. |
| `--analysis-json` | — | Same as `run_simulation`; preserves hand-edited scenario analysis. |
| `--output` | auto-timestamped | Same as `run_simulation`. |
| `--dry-run` | `false` | Uses `DryRunLLMClient` plus a local `DryRunOperatorReviewGate` stand-in. |
| `TELEGRAM_BOT_TOKEN` | yes (live) | Telegram bot token used by the coached faction transport/review gate. |
| `DIPLOMAT_PUBLIC_CHANNEL_ID` | yes (live) | Public game channel for the coached faction's outbound messages. |
| `DIPLOMAT_COACHING_CHANNEL_ID` | yes (live) | Operator coaching channel for `OperatorReviewGate`. |
| `DIPLOMAT_OPERATOR_USER_IDS` | yes (live) | Comma-separated operator Telegram user IDs; same tagging semantics as the production bot. |

Pass-through flags from `run_simulation` are supported as-is: `--scenario-title`,
`--batna-fraction`, `--batna-fractions`, `--game-mode`, and
`--per-faction-providers`. The coached faction's pipeline uses
`OperatorReviewGate`; other factions stay on `AutoApproveReviewGate`.

### `tests.self_play.probe_providers` — live provider auth + parse check

```bash
python -m tests.self_play.probe_providers \
    --providers '{"openai":{"provider":"openai","model":"gpt-4.1-mini"},"anthropic":{"provider":"anthropic","model":"claude-haiku-4-5"},"google":{"provider":"google","model":"gemini-2.5-flash-lite"}}' \
    --max-tokens 500
# OpenRouter probe — set OPENROUTER_API_KEY first
# python -m tests.self_play.probe_providers \
#     --providers '{"test":{"provider":"openrouter","model":"meta-llama/llama-3.3-70b-instruct"}}'
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

# Asymmetric BATNAs: alpha squeezed, beta comfortable
python -m tools.scenario_compiler \
    --scenario tests/self_play/scenarios/water_rights.md \
    --batna-fractions '{"alpha":0.65,"beta":0.35,"gamma":0.50}'

# Force-clamp LLM-produced BATNAs to the target fractions (no narrative drift)
python -m tools.scenario_compiler \
    --scenario tests/self_play/scenarios/water_rights.md \
    --batna-fraction 0.55 \
    --force-batna-fraction
```

| Flag | Default | Notes |
|---|---|---|
| `--scenario` * | — | Path to scenario text/markdown file |
| `--faction` | (all) | Generate persona for one faction only |
| `--output-dir` | (scenario dir) | Where to write `scenario_analysis.json` and persona `.txt` files |
| `--title` | `"a multi-party negotiation"` | Persona header title |
| `--batna-fraction` | `0.50` | Target BATNA as fraction of each faction's max possible score. Scalar fallback when `--batna-fractions` is not supplied. Same flag as on `run_simulation.py`. See `TUNING.md` §1 BATNA tuning for full semantics (higher = more pressure to find Pareto deals; lower = easier to settle for any deal). |
| `--batna-fractions` | — | JSON map `{faction_id: fraction}` for **asymmetric** BATNAs. Overrides `--batna-fraction` only for listed factions; unlisted use the scalar fallback. Example: `'{"alpha":0.65,"beta":0.35}'`. |
| `--force-batna-fraction` | `false` | After LLM analysis, **overwrite** each faction's BATNA with `target_fraction × max_possible_score`. Uses `--batna-fractions` per-faction targets when supplied; otherwise uses `--batna-fraction`. Default off, preserving narrative BATNAs. Use when narrative-explicit BATNAs would dilute the target pressure. |

After compilation, prints any per-faction BATNA pressure warnings from
`validate_batna_pressure()`. Warnings only — never blocks compilation.

---

### `tools.scenario_builder` — constraint-driven scenario generator

Reverse of `tools.scenario_compiler`. Operator writes a `ScenarioSpec` JSON
file declaring desired outcome-shape properties; the tool searches scoring-table
space via random-restart hill-climb and emits a `scenario_analysis.json` +
per-faction `.txt` persona directory compatible with `run_simulation.py`.

Pass `--debug-search` to emit one JSON restart record per search restart while
the builder runs. The log includes the restart index, starting and ending total
fitness distance, the exit reason, and the per-target distances at exit.

No LLM calls — pure combinatorial search. `logrolling` and `deception_tactics`
fields are emitted as stubs; fill them by hand or by running
`tools.scenario_compiler` over the generated tables.

```bash
# Build a scenario from a spec, verify the Pareto count matches the target
python -m tools.scenario_builder \
    --spec tests/self_play/specs/multi_pareto.json \
    --output-dir tests/self_play/scenarios/multi_pareto_v1 \
    --title "Multi-Pareto River Basin" \
    --verify

# Reproducible run with fixed seed
python -m tools.scenario_builder \
    --spec tests/self_play/specs/multi_pareto.json \
    --output-dir /tmp/scenario_test \
    --seed 42 \
    --max-iterations 2000 \
    --debug-search \
    --verify
```

| Flag | Default | Notes |
|---|---|---|
| `--spec` * | — | Path to `ScenarioSpec` JSON file (see spec schema below) |
| `--output-dir` * | — | Directory to write `scenario_analysis.json` and per-faction `.txt` persona files |
| `--title` | `"a reverse-engineered negotiation"` | Scenario title used in persona text headers |
| `--seed` | `None` (from spec's `seed` field) | Override the spec's random seed |
| `--max-iterations` | `1000` | Maximum hill-climb restarts before declaring failure |
| `--debug-search` | `false` | Emit structured JSON restart logs while searching |
| `--verify` | `false` | After emission, run `verify_scenario_optimum` on the result; exit non-zero if it reports FAIL |

**Spec schema** (`ScenarioSpec` JSON):

```json
{
  "factions": ["alpha", "beta", "gamma"],
  "issues": [
    {
      "name": "Water Allocation",
      "outcomes": ["low", "medium", "high"],
      "description": "Share of river flow"
    }
  ],
  "score_range": [1, 10],
  "pareto_count_target": 3,
  "pareto_distribution_spread": 1.5,
  "batna_clearing_count_target": 2,
  "batna_to_pareto_gap_pct": 0.15,
  "requires_logrolling": true,
  "priority_collision": "soft",
  "asymmetric_batna_fractions": {"alpha": 0.65, "beta": 0.45},
  "game_mode": "mixed",
  "seed": 42
}
```

| Field | Type | Default | Notes |
|---|---|---|---|
| `factions` * | list[str] | — | Faction IDs (≥ 2, unique) |
| `issues` * | list[IssueSpec] | — | Each issue has `name`, `outcomes` (list, ≥ 2, unique), optional `description` |
| `score_range` | [int, int] | `[1, 10]` | Min/max score value for every cell in the scoring table |
| `pareto_count_target` | int or [min, max] | `1` | Target number of Pareto-optimal deals; range tuple accepted |
| `pareto_distribution_spread` | float | `0.0` | Min stdev of per-faction max–min scores across Pareto deals (spread enforcement) |
| `batna_clearing_count_target` | int | `1` | Minimum number of deals that beat BATNA for every faction |
| `batna_to_pareto_gap_pct` | float (0–1) | `0.10` | Minimum gap between best BATNA and worst Pareto deal, as fraction of score range |
| `requires_logrolling` | bool | `false` | Emit a logrolling stub in `scenario_analysis.json` (structural flag; not enforced combinatorially) |
| `priority_collision` | `"none"` \| `"soft"` \| `"hard"` | `"none"` | Priority-collision property target (soft/hard = overlapping faction priorities) |
| `asymmetric_batna_fractions` | dict[str, float] | `{}` | Per-faction BATNA fraction overrides; unspecified factions use `0.50` |
| `game_mode` | `"cooperative"` \| `"competitive"` \| `"mixed"` | `"mixed"` | Recorded in emitted analysis; no effect on search |
| `seed` | int | `0` | Random seed for reproducibility; overridden by `--seed` flag |

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

### `tools/classify_edit_log.py` — bulk edit-log classifier

Classify all `review_gate_edits` rows with `action='edited'` into one of six
categories. Reads the existing DB, skips already-classified rows, writes results
to the `edit_classifications` table, and prints a markdown summary.

```bash
# Classify unclassified edits (production DB)
python tools/classify_edit_log.py --db data/game.db

# Classify a self-play game DB
python tools/classify_edit_log.py --db /tmp/diplomat_selfplay/game.db --game-id some-game-id

# Reclassify everything (including already-classified rows)
python tools/classify_edit_log.py --db data/game.db --force

# Override provider/model
python tools/classify_edit_log.py --db data/game.db \
    --provider google --model gemini-2.5-flash-lite
```

| Flag | Default | Notes |
|---|---|---|
| `--db` * | — | Path to the SQLite game DB |
| `--game-id` | (all games) | Filter to a specific game ID |
| `--force` | off | Reclassify rows that already have a classification |
| `--provider` | pipeline.yaml primary | LLM provider for the classifier |
| `--model` | pipeline.yaml primary model | LLM model for the classifier |

**Output format:** markdown table with `category | count | most_recent_example_id` columns,
one row per category that has at least one classified row.

**Cost:** ~$0.01 per edit at `gemini-2.5-flash-lite` defaults (~$0.05 for a full coached game).

**Alternative (mid-game):** use the `/edits-summary` operator command instead. It lazy-classifies
unclassified rows on demand and renders the same summary table without leaving the coaching chat.

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

### Ad-hoc SQL inspection queries

> Originally diplomat-system-spec.md §13 (Monitoring). Migrated here 2026-06-02. Paths assume the production layout `data/game.db`; adjust if running self-play (no shared SQLite) or the smoke deployment.

The Diplomat bot persists everything in one SQLite file. The State Manager
owns most tables (see `ARCH_state_manager.md` Schema section); the Event
Store owns `messages`. These are the queries the operator most often wants
between rounds:

```bash
# Game state snapshot (current_round, total_rounds, game_status)
sqlite3 data/game.db "SELECT * FROM game_state;"

# Promise ledger — all promises tracked, who made them, current status
sqlite3 data/game.db \
  "SELECT round_made, from_faction, to_faction, content, status
   FROM promises ORDER BY round_made;"

# INTEL coaching corrections actually applied
sqlite3 data/game.db \
  "SELECT timestamp, table_affected, change_summary
   FROM state_change_log
   WHERE trigger_type='intel_coaching';"

# Review-gate edit log for the current round (what the operator did to drafts)
sqlite3 data/game.db \
  "SELECT action, original_draft, edited_text
   FROM review_gate_edits
   WHERE round_number=(SELECT value FROM game_state WHERE key='current_round');"

# Adversarial reads for the current round (draft + the adversarial analysis)
sqlite3 data/game.db \
  "SELECT round_number, draft_response, analysis, posted
   FROM adversarial_reads
   WHERE round_number=(SELECT value FROM game_state WHERE key='current_round');"
```

For cost reports, prefer `tools/inspect_ledger.py` (see above). If you want
a Python one-liner instead of the CLI:

```bash
python3 -c "from toolkit.cost_accountant import CostAccountant; \
  from pathlib import Path; \
  a = CostAccountant(Path('data/cost_ledger.jsonl')); \
  r = a.report(); \
  print(f'Total: \${r.total_spend_usd:.2f}'); \
  [print(f'  {k}: \${v:.2f}') for k,v in r.by_operation.items()]"
```

For live Pi diagnostics use the structured logs from Phase 26 instead of
SQL — grep `logs/diplomat.log` for the documented event names
(`startup.online`, `event.received`, `event.routed`, `event.tagged`,
`event.sent`, `extraction.*`, `round.boundary`, `pipeline.*`). See
`SMOKE_RUNBOOK.md` §3 for the verification command.

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
| 2026-06-07 | Phase 33: added `tools/classify_edit_log.py` entry (bulk edit-log classifier); added "classify the review-gate edit log" row to quick index. |
| 2026-06-10 | Phase 35: added `tools.scenario_builder` section (constraint-driven scenario generator; `--spec`, `--output-dir`, `--title`, `--seed`, `--max-iterations`, `--verify`); added quick-index row. |
| 2026-06-10 | Phase 36 Step 36.1: added `--debug-search` to `tools.scenario_builder` and documented its JSON restart logs. |
