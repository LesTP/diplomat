# Diplomat — Tuning Guide

Living document for deployment configuration, provider assignments, prompt design notes, and game-specific tuning decisions. Updated during game prep and between rounds.

---

## 1. Provider Assignments

Configuration file: `config/pipeline.yaml` (production) or `config/pipeline_smoke.yaml` (testing). Per-faction Generator overrides for self-play via `--per-faction-providers` CLI flag on `run_simulation.py`.

### Current Assignment

| Module | Provider | Tier | Model | Rationale |
|---|---|---|---|---|
| **Generator** | primary (OpenAI) | quality | gpt-5.5 | Public-facing output; needs strong diplomatic language |
| **Primary Analyst** | primary (OpenAI) | quality | gpt-5.5 | Strategic reasoning; good structured JSON output |
| **Secondary Analyst** | secondary (Anthropic) | quality | claude-sonnet-4-6 | Different provider for divergence value |
| **Adversarial** | secondary (Anthropic) | quality | claude-sonnet-4-6 | Different provider from generator to catch blind spots |
| **Extractor** | — | — | RuleBasedExtractor | Regex-based, no LLM cost. Switch to OpenAIStructuredExtractor for better quality |

### Recommended Assignment (game deployment)

| Module | Provider | Model | Why |
|---|---|---|---|
| **Generator** | Anthropic | claude-sonnet-4-6 | Best persona adherence, nuanced diplomatic tone, strong constraint following |
| **Primary Analyst** | OpenAI | gpt-5.5 | Strong reasoning, reliable structured output |
| **Secondary Analyst** | Anthropic | claude-sonnet-4-6 | Different perspective for divergence detection |
| **Adversarial** | OpenAI | gpt-5.4-mini | Deliberately different provider from generator; cheap model sufficient for pattern matching |
| **Extractor** | OpenAI | gpt-5.4-mini | Structured extraction is straightforward; cheap model is sufficient |

### Scenario BATNA tuning (`--batna-fraction`)

Available on both `tools.scenario_compiler` and `tests.self_play.run_simulation`. Sets the target BATNA value as a fraction of each faction's maximum possible score across all issues.

**Semantics — which direction does what?**

| Fraction | Effect | When to use |
|---|---|---|
| **High (0.6–0.8)** | BATNA is close to the best possible deal. Agents must find a Pareto-optimal trade to beat BATNA — *mediocre deals fail*. Skill becomes visible: bad negotiators settle too soon and lose; good ones find the joint optimum and win. | Testing strategic skill, comparing model/strategy quality, generating non-trivial games |
| **Medium (0.4–0.6)** | Balanced. Pareto deals win, but moderately good deals also beat BATNA. Default. | General self-play, scenario validation |
| **Low (0.2–0.4)** | "Any deal beats no deal." Agents converge fast on whatever's on the table. Skill is invisible because everyone clears BATNA. | Testing "settling pressure" or coordination scenarios where the question is *whether* agents can agree, not *how well* |

**Common mistake.** Lower BATNA feels like "more pressure to negotiate" — and it is, in the narrow sense of "you must agree to *something*." But for measuring negotiation *quality*, higher BATNA creates more pressure because it rules out lazy settlements. Run 8 pre-patch had 0.19–0.34 BATNAs and we couldn't tell strategic skill apart because every agent easily beat BATNA. Hand-patching to 0.40–0.61 made the deadlock and the missed Pareto optimum visible.

**Default `0.50`.** Calibrated from Run 8 hand-patch experience.

**The `validate_batna_pressure()` helper** (called automatically by both CLIs after compilation) prints a warning per faction whose BATNA lands more than 10 percentage points below the target. It never blocks — operator can ignore if low BATNA is intentional.

**Workflows:**
- **Own scenarios, want defaults:** just run with `--scenario <path>`
- **Own scenarios, want specific pressure:** add `--batna-fraction 0.65` (or whatever)
- **External scenario with explicit BATNAs in the narrative:** prompt instructs the LLM to honor those; `--batna-fraction` becomes a soft target the LLM weighs against narrative
- **Hand-tuned reproducible runs:** compile once, edit `scenario_analysis.json`, then `--analysis-json` to replay (skips compile entirely; `--batna-fraction` is ignored on this path)

### Google (Gemini) defaults for tuning and multi-provider runs

Set 2026-05-30. Google moved from free tier to **paid (Tier 1)** after the
operator enabled billing and bought $10 in credits. The Run 8 "20 requests/day"
constraint is gone; every call is now metered (per-token billing).

| Role | Model | Why |
|---|---|---|
| **Default for tuning / Run 9** | `gemini-2.5-flash-lite` | Fastest (~1.6s), cheapest ($0.10 in / $0.40 out per MTok), **no thinking-mode overhead**. Validates plumbing and behavioral patterns without the gotchas below. |
| Stronger generator option | `gemini-2.5-flash` | Better reasoning, but uses thinking mode — see gotcha. Requires `max_tokens >= 1000`. |
| Strongest option | `gemini-2.5-pro` | Newly accessible on paid tier. Strongest reasoning; also thinking mode. Requires `max_tokens >= 1500`. |
| Deprecated | `gemini-2.0-flash` | 404 — "no longer available to new users." Do not use. |

**Thinking-token gotcha (flash and pro only).** Gemini 2.5 flash and pro
consume output tokens for internal reasoning *before* producing visible
output. If `max_tokens` is too low, the model returns only the opening
Markdown fence ` ``` ` because the entire budget got eaten by thinking.
Empirical floor for trivial prompts is ~200 tokens; production negotiation
responses need 1000–2000. `gemini-2.5-flash-lite` does NOT have thinking
mode and is unaffected. This is the primary reason flash-lite is the
current tuning default.

CLI examples in `tests/self_play/probe_providers.py` and
`tests/self_play/run_simulation.py` use `gemini-2.5-flash-lite` to match
this default.

### Available Providers

Toolkit supports these providers via `llm_client`. Add to `pipeline.yaml` `llm_providers` section with an API key env var.

| Provider | Config name | Strengths | Weaknesses |
|---|---|---|---|
| OpenAI | `openai` | Reliable structured output, strong reasoning, good JSON | Less distinctive voice in creative writing |
| Anthropic | `anthropic` | Nuanced language, persona adherence, complex constraint following | Can over-hedge, sometimes refuses adversarial framings |
| Google | `google` | Large context window, good synthesis. Cheap on paid tier ($0.10/MTok for flash-lite). | Thinking-mode budget gotcha on 2.5-flash/pro (see Google defaults section above); some older models deprecated |
| OpenRouter | `openrouter` | Access to many models (Llama, Mistral, etc.) | Variable quality, routing latency |

### Tier System

Each provider defines three model tiers in `pipeline.yaml`:

```yaml
llm_providers:
  primary:
    provider: openai
    models:
      quality: gpt-5.5             # flagship — generation, analysis ($5/$30 per MTok)
      default: gpt-5.4             # balanced — most tasks ($2.50/$15 per MTok)
      commodity: gpt-5.4-mini      # cheapest — judging, extraction ($0.75/$4.50 per MTok)
    api_key_env: OPENAI_API_KEY
```

### Model Pricing Reference

**OpenAI:**

| Model | Input $/MTok | Output $/MTok | Context | Notes |
|---|---|---|---|---|
| gpt-5.5 | $5.00 | $30.00 | 1M | Flagship, best reasoning |
| gpt-5.4 | $2.50 | $15.00 | 1M | Good balance of quality and cost |
| gpt-5.4-mini | $0.75 | $4.50 | 400K | Best cost/quality ratio for routine tasks |

**Anthropic:**

| Model | Input $/MTok | Output $/MTok | Context | Notes |
|---|---|---|---|---|
| claude-opus-4-7 | $5.00 | $25.00 | 1M | Strongest, best for complex analysis |
| claude-sonnet-4-6 | $3.00 | $15.00 | 1M | Best balance — strong persona, good reasoning |
| claude-haiku-4-5 | $1.00 | $5.00 | 200K | Fast and cheap, sufficient for simple tasks |

Modules specify their tier: `tier: quality` for generation, `tier: commodity` for judge evaluations. The Orchestrator maps tier → model at call time.

---

## 2. Prompt Inventory

All prompts live in `config/`. Each is loaded at startup by the Orchestrator and injected into the corresponding module.

### faction_prompt.txt (36 lines)

**Purpose:** Defines the faction's identity, negotiation rules, and behavioral style. The system prompt for all generation calls.

**Sections:**
- Strategic identity — high-level positioning and priorities
- Negotiation rules — promise handling, uncertainty surfacing, questioning
- Behavioral style — tone and manner
- `## CURRENT ROUND CONTEXT` — dynamic section stripped and rebuilt each round by Persona module with live coaching data

**Design notes:**
- Currently configured for England. Replace entirely for a different faction.
- The `CURRENT ROUND CONTEXT` marker is structural — Persona.get_base_prompt() returns everything above it; build_round_context() assembles the live version below it.
- Keep negotiation rules concrete and actionable. Vague instructions ("be strategic") produce vague outputs. Specific rules ("do not promise support unless the current context supports it") are enforceable.

**Known weaknesses:**
- No late-game strategy shift — currently static across all rounds
- No explicit handling of win conditions (blocked on game rules)
- Coaching tags override prompt rules at runtime, but recurring overrides should be baked into the prompt

**Tuning approach:** Run generation scenarios from `tests/prompt_regression/scenarios/generation/`. Check constraint adherence and persona consistency. Edit the prompt, re-run, compare pass rates.

### analyst.txt (14 lines)

**Purpose:** System prompt for the intelligence analyst. Instructs the LLM to evaluate game state and return structured JSON matching the intelligence schema.

**Key instructions:**
- Ground judgments in provided state snapshot
- threat_level as 1-5 integer
- Identify leverage points affecting negotiation outcomes
- Coalition stability as stable/fragile/volatile/unknown
- Conservative assessments when evidence is thin

**Design notes:**
- Same prompt used for both primary and secondary analysts (different providers produce different assessments)
- Output must conform to `config/schemas/intelligence.json`
- The prompt deliberately does not mention the faction's identity — the analyst is neutral

**Tuning approach:** Run analyst scenarios. Compare primary vs secondary outputs. If both consistently miss the same patterns, the prompt needs strengthening.

### generation.txt (12 lines)

**Purpose:** Additional instruction for the generation call, layered on top of the faction prompt (which is the system prompt). Tells the LLM to use the assembled context and produce either JSON (review gate mode) or plain text.

**Key instructions:**
- Use persona, round context, intelligence, divergences, transcript, and coaching
- Keep message strategically coherent
- Avoid unsupported commitments
- Preserve uncertainty when analysts disagree
- Review gate mode: return `{"response": "...", "reasoning": "..."}`

**Design notes:**
- This is the user prompt prefix; the full assembled context follows it
- The JSON output format is consumed by `LLMGenerator._parse_review_response()`
- Keep this prompt short — the assembled context already contains all the information

### adversarial.txt (14 lines)

**Purpose:** System prompt for the adversarial reader. Instructs the LLM to read a draft response as an opposing faction looking for exploitable weaknesses.

**Key instructions:**
- Identify what the draft reveals about our position
- Identify explicit and implicit commitments
- Find exploitable ambiguity, inconsistency, overcommitment, or timing risk
- Suggest counter-moves an opponent might make
- Use empty arrays when no issue is visible

**Design notes:**
- Output must conform to `config/schemas/adversarial.json`
- This is the most adversarial prompt in the system — some providers (especially Anthropic) may soften their analysis. Using a different provider from the generator helps.
- The adversarial analysis is shown to the operator in the review gate alongside the draft

### state_updater.txt (17 lines)

**Purpose:** System prompt for the extraction module when using LLM-based extraction (OpenAIStructuredExtractor). Converts game text into structured state patches.

**Key instructions:**
- Extract only facts supported by input text and current state
- Use stable, descriptive IDs for new entities
- Preserve existing IDs when updating known items
- Mark promises as pending unless clearly resolved
- Operator intel corrections are high-confidence and override prior state
- Return empty JSON object if no state-changing facts

**Design notes:**
- Currently unused in production — `RuleBasedExtractor` handles extraction via regex
- Would be activated by changing `modules.extractor.class` to `OpenAIStructuredExtractor` in pipeline.yaml
- Output must conform to `config/schemas/state_patch.json`
- The `commodity` tier model is sufficient for extraction

---

## 3. Cost Profile

### Per-round estimate (production config)

| Call | Model | Est. tokens | Est. cost |
|---|---|---|---|
| Primary Analyst | gpt-5.5 | ~2K in, ~1K out | ~$0.04 |
| Secondary Analyst | claude-sonnet-4-6 | ~2K in, ~1K out | ~$0.02 |
| Generation | gpt-5.5 | ~3K in, ~1K out | ~$0.05 |
| Adversarial | claude-sonnet-4-6 | ~1K in, ~500 out | ~$0.01 |
| **Total per round** | | | **~$0.12** |

Extraction is free (RuleBasedExtractor). Direct-address responses add another generation call (~$0.03 each).

### Budget settings

In `pipeline.yaml`:
```yaml
cost:
  per_round_budget_usd: 1.00    # hard cap per round
  session_budget_usd: 10.00     # hard cap per session
```

At ~$0.12/round, the per-round budget of $1.00 allows ~8 generation calls per round before the gate trips. The session budget of $10.00 supports ~80 rounds.

### Smoke test config

In `pipeline_smoke.yaml`: both providers set to OpenAI `gpt-5.4-mini`, budgets halved ($0.50/round, $2.00/session), adversarial disabled. Cost per round: ~$0.01.

---

## 4. Scenario Baseline

Track prompt regression pass rates here after each tuning session.

```
date        | prompt file          | scenarios | passed | notes
------------|----------------------|-----------|--------|------
(not yet run against live LLM)
```

Run with:
```bash
cd /home/claude/workspace/diplomat
PYTHONPATH=src .venv/bin/python -m tests.prompt_regression.runner \
  --scenarios tests/prompt_regression/scenarios/
```

---

## 5. Game-Specific Configuration

Populated when game rules are received from the moderator.

### Faction Identity
- **Faction name:** england (placeholder)
- **Faction persona file:** `config/faction_prompt.txt`

### Round Structure
- **Mode:** signal / time (TBD — `round_detection.mode` in pipeline.yaml)
- **Signal pattern:** TBD (currently `^ROUND\s+(?P<round>\d+)`)
- **Total rounds:** unknown

### Win Conditions
- TBD — will affect late-game prompt adjustments

### Response Limits
- TBD — if posts are capped per round, add a counter to Orchestrator

### Opponent Intelligence
Updated during the game from analyst reports and coaching input.

| Faction | Known behavior | Assessment | Notes |
|---|---|---|---|
| (populated during game) | | | |

---

## 6. Tuning Changelog

Log prompt and config changes during the game.

```
date        | what changed                          | why                           | result
------------|---------------------------------------|-------------------------------|-------
2026-05-30  | Google paid tier enabled, $10 credits | Run 8 hit 250 RPD on free tier| 5-call burst probe passed; all 3 Gemini 2.5 models accessible incl. pro
2026-05-30  | gemini-2.5-flash-lite set as default  | Avoid thinking-token gotcha   | Cheapest ($0.10/MTok), no thinking-mode overhead; revisit during dedicated provider/tier testing
2026-05-30  | toolkit complete_with_retry shipped   | Transient 429/5xx/empty handling at scale | Exponential backoff + retry-after honoring; wired through CostAccountant + Diplomat adapter; 15 new toolkit tests; live 3-provider probe green
2026-05-30  | LoggingLLMClient SCORE/RECON unwrap fixed | Calls were bypassing the logger; verify_dryrun couldn't assert on them | _TaggedLLMClient wrapper applies recon:<faction> / scorer tags; verify_dryrun invariant 7 now asserts SCORE >= 1; 5 new tests
2026-05-30  | scenario compiler BATNA hardcode removed | Run 8 needed hand-patched BATNAs because compiler forced "4-8 total" regardless of scenario size | Replaced with fraction-of-max formula (default 50%); new --batna-fraction CLI on tools.scenario_compiler AND tests.self_play.run_simulation; validate_batna_pressure() warns when LLM under-sets; 13 new tests
```
