# Diplomat — Live Run Protocol

The canonical sequence for executing a live multi-agent self-play
simulation. Follow this every time you intend to make real LLM calls.

## Why this exists

Run 8 burned ~$2-3 of LLM calls and exhausted Google's daily Gemini
quota (20 requests/day on this project) before the actual experiment
ran. Two silent-failure bugs (missing `.env` load, missing Markdown
fence stripping) caused structured_call's retry loop to spin until
exhaustion on every Anthropic and Google call. Both bugs would have
been caught for ~$0.003 by a 15-second pre-flight probe.

This protocol formalizes the cheap-validation steps that prevent
expensive surprises.

## The standard sequence

Order matters. Each step is cheap and catches a specific class of
failure. Don't skip without an explicit reason.

```
1. Define inputs           (no cost)
2. Validate scenario       (no cost)        verify_scenario_optimum.py
3. Validate integrations   (~$0.003)        probe_providers.py
4. Validate plumbing       (no cost)        run_simulation --dry-run
                                            verify_dryrun.py
5. Run live                (~$0.50-$2)      run_simulation.py
6. Validate output         (no cost)        verify_dryrun.py
7. Document + commit       (no cost)        TUNING_LOG.md, DEVLOG.md
```

### 1. Define inputs

Before any commands, write down on a notepad or task description:

- **Scenario**: which `scenarios/*.md` file?
- **Analysis JSON**: live-compile, or load a pre-edited one via `--analysis-json`?
- **Factions**: which faction ids?
- **Provider assignments**: which provider for each faction?
- **Round count**: usually 4 (matches existing TUNING_LOG runs and the PENULTIMATE/FINAL marker design)
- **Expected cost**: rough estimate per provider × calls per round × rounds. Anchor: a clean Run 8 was ~$1 across 3 providers and 4 rounds.
- **Hypothesis**: one sentence. What experimental variable are you isolating? What outcome would confirm or refute the hypothesis?

If you can't articulate the hypothesis, you're not ready to run.

### 2. Validate scenario — `verify_scenario_optimum.py`

For any new scenario or after editing BATNAs/scoring:

```bash
python tests/self_play/verify_scenario_optimum.py \
    --analysis scenarios/<name>_compiled/scenario_analysis.json
```

Confirm:
- Priorities are differentiated across factions
- Deals beating ALL BATNAs is in `(N/27)` range that creates real pressure — not 27/27 (too soft) and not 0/27 (impossible)
- Pareto frontier exists and includes the "everyone-gets-priority" deal
- Logrolling deals exist at the 60% and 75%-of-max thresholds

If the verifier reports "REVIEW NEEDED" with reasons, fix the scenario
before proceeding. Hand-edit BATNAs in the analysis JSON if the compiler
under-pressured the scenario; regenerate personas via `_load_precompiled_analysis`
(invoked automatically by `run_simulation --analysis-json`).

Skip rule: skip only if the scenario is unchanged since the last run
that already passed this check.

### 3. Validate integrations — `probe_providers.py`

For any live run, especially multi-provider:

```bash
$providers = '{"alpha":{"provider":"openai","model":"gpt-4.1-mini"},
               "beta":{"provider":"anthropic","model":"claude-haiku-4-5"},
               "gamma":{"provider":"google","model":"gemini-2.5-flash"}}'
python -m tests.self_play.probe_providers --providers $providers
```

The probe makes 1 real call per provider with a trivial JSON request.
Catches:
- Missing API keys (`.env` not loaded, wrong env var name)
- Wrong model name (typos, deprecated models)
- Auth failures (expired keys, wrong project)
- Markdown fence wrapping or other parse issues
- Empty responses
- Daily quota already exhausted (you'll see 429 here, NOT mid-run)

Use the same JSON map you'll pass to `run_simulation.py --per-faction-providers`
so the probe validates the exact config you'll run.

Required exit code 0 before proceeding. If any probe fails, fix the
issue and re-probe.

Skip rule: skip only if you ran the exact same provider+model combination
successfully within the last few hours AND haven't changed any env vars
or toolkit code in between.

Cost guard: a probe is ~$0.001 per provider. If the probe alone reports
a 429 from Google, the daily quota is exhausted — abort the run, wait
for the next day.

### 4. Validate plumbing — dry-run + `verify_dryrun.py`

Before any live run:

```bash
python -m tests.self_play.run_simulation \
    --dry-run \
    --scenario scenarios/<name>.md \
    --analysis-json scenarios/<name>_compiled/scenario_analysis.json \
    --per-faction-providers $providers \
    --rounds 4 \
    --output tests/self_play/results/dryrun_<name>.json

$expect = '{"alpha":"openai","beta":"anthropic","gamma":"google"}'
python -m tests.self_play.verify_dryrun \
    --results tests/self_play/results/dryrun_<name>.json \
    --num-factions 3 --rounds 4 \
    --expect-providers $expect
```

Catches plumbing bugs the probe can't catch:
- Round counter not advancing
- Messages not reaching the transcript
- PENULTIMATE/FINAL markers missing or in wrong rounds
- Per-faction provider routing regressions (`--expect-providers`)
- Adversarial/extraction/analyst call counts wrong
- Reconciliation not firing on round boundaries
- Auto-trigger flag forgotten (cause of Run 7 Bug 3)

Dry-run is free. Always run it before any structural change. The expected
output is `PASS — all infrastructure invariants hold.`

Skip rule: skip only for trivial configuration changes (different round
count, different scenario file with same plumbing) AND you ran a full
dry-run within the last day.

### 5. Run live — `run_simulation.py`

Only after steps 2-4 pass cleanly:

```bash
python -m tests.self_play.run_simulation \
    --scenario scenarios/<name>.md \
    --analysis-json scenarios/<name>_compiled/scenario_analysis.json \
    --per-faction-providers $providers \
    --rounds 4 \
    --output tests/self_play/results/run<N>_<descriptor>.json \
    2>&1 | Tee-Object tests/self_play/results/run<N>_<descriptor>.log
```

Conventions:
- Output filename: `run<N>_<descriptor>.json` where N is the sequential
  run number from `TUNING_LOG.md`'s metrics table and `<descriptor>`
  is a short slug like `water_rights_3provider`.
- Pipe to `Tee-Object` (or `tee` on Linux) so the full console output
  is preserved alongside the structured JSON.
- Use `_v2.json` / `_v3.json` suffixes for re-attempts after bug fixes.
  Discard non-final attempts after the canonical run lands.

Cost ceiling: if budget gate trips mid-run, the orchestrator drops to
BATNA scoring for affected factions. The default `per_round_budget_usd=2.0`
(in `tests/self_play/run_simulation.py:_build_cost_accountant`) is
generous; raise it only if you know why.

### 6. Validate output — `verify_dryrun.py` on the live results

Even live runs should pass `verify_dryrun` (it doesn't care whether the
underlying calls were canned or real):

```bash
python -m tests.self_play.verify_dryrun \
    --results tests/self_play/results/run<N>_<descriptor>.json \
    --num-factions 3 --rounds 4 \
    --expect-providers $expect
```

Catches mid-run regressions:
- Generation calls failed mid-round (transcript message count < expected)
- Provider routing drifted (a faction's GEN calls show a different provider)
- Endgame markers missing
- Reconciliation didn't fire

If invariants fail, that's a finding for the TUNING_LOG entry. Don't
"fix" the run by re-running — document the failure mode.

### 7. Document + commit

Append to `TUNING_LOG.md`:
- Run number, scenario, providers, cost
- Observations (per-faction scores, deal/no-deal, qualitative behavior)
- Learning (what the data tells you about your hypothesis)
- Decisions taken (what changes for the next run)
- Open items raised and closed

Append to `DEVLOG.md`:
- Structured entry with Scope / What this is NOT / Verification / Files modified / Next

Commit the canonical results JSON. Since `tests/self_play/results/.gitignore`
excludes `*.json` by default, use `git add -f`:

```bash
git add -f tests/self_play/results/run<N>_<descriptor>.json
git add TUNING_LOG.md DEVLOG.md DEVPLAN.md  # if cold-start gotchas need updating
git commit -m "Run <N>: <one-line summary>"
```

## When to abort

Stop the run and investigate before retrying if:

- Probe (step 3) reports any failure → fix integration, re-probe
- Probe reports 429 from Google → daily quota gone, wait for next day
  (clock resets at midnight UTC on free tier)
- Dry-run (step 4) fails invariants → fix plumbing, re-dry-run
- Live run prints repeated retry errors of the same kind → kill it, fix,
  start fresh. Don't let it burn quota on retry loops.
- Live run completes but `verify_dryrun` reports >20% missing
  generations → likely a provider-specific failure mode. Inspect the
  call log before deciding whether to re-run or document and move on.

## Budget context

| Provider | Tier | Typical run cost | Daily ceiling |
|---|---|---|---|
| OpenAI gpt-4.1-mini | paid | ~$0.30/game | API limit (high) |
| Anthropic claude-haiku-4-5 | paid | ~$0.40/game | API limit (high) |
| Google gemini-2.5-flash | **free, this project** | $0 | **20 requests/day** |

A clean 4-round game uses ~4-6 GEN calls per faction. The Google quota
is the bottleneck. With clean runs, 1-3 games per day is comfortable.
Bug-tax (silent retry loops) can burn 14+ Gemini calls per failed
iteration — probe before every run.

If serious experimentation requires more than 2-3 games per day on
Gemini, either:
- Switch to a paid Gemini tier
- Add retry-with-backoff to toolkit's `llm_client` for 429s (currently
  the LLM call surfaces 429 to structured_call which retries
  immediately, wasting quota)
- Use a different provider for that faction

## Reference

- `tests/self_play/probe_providers.py` — live integration probe
- `tests/self_play/verify_scenario_optimum.py` — scenario sanity checker
- `tests/self_play/run_simulation.py` — main runner (supports `--dry-run`)
- `tests/self_play/verify_dryrun.py` — invariant checker (works on dry-run AND live results)
- `scenarios/` — scenario .md files + compiled analyses
- `tests/self_play/results/` — canonical run results (most `*.json` are gitignored; commit specific runs with `git add -f`)
- `TUNING_LOG.md` — history of all runs with hypotheses, observations, learnings
- `DEVLOG.md` — structured per-change audit trail
- `DEVPLAN.md` — current status + cold-start gotchas

## Change History

| Date | What Changed | Why |
|------|--------------|-----|
| 2026-05-30 | Initial protocol | Formalize the pre-flight sequence after Run 8 wasted ~14 Gemini calls on silent retries that a probe would have caught |
