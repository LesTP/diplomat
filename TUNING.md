# Diplomat — Tuning Guide

Living document for deployment configuration, provider assignments, prompt design notes, and game-specific tuning decisions. Updated during game prep and between rounds.

---

## 1. Provider Assignments

Configuration file: `config/pipeline.yaml` (production) or `config/pipeline_smoke.yaml` (testing).

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
| **Extractor** | OpenAI | gpt-5.4-nano | Structured extraction is straightforward; cheapest model is sufficient |

### Available Providers

Toolkit supports these providers via `llm_client`. Add to `pipeline.yaml` `llm_providers` section with an API key env var.

| Provider | Config name | Strengths | Weaknesses |
|---|---|---|---|
| OpenAI | `openai` | Reliable structured output, strong reasoning, good JSON | Less distinctive voice in creative writing |
| Anthropic | `anthropic` | Nuanced language, persona adherence, complex constraint following | Can over-hedge, sometimes refuses adversarial framings |
| Google | `google` | Large context window, good synthesis | Less predictable format, newer API |
| OpenRouter | `openrouter` | Access to many models (Llama, Mistral, etc.) | Variable quality, routing latency |

### Tier System

Each provider defines three model tiers in `pipeline.yaml`:

```yaml
llm_providers:
  primary:
    provider: openai
    models:
      quality: gpt-5.5             # flagship — generation, analysis
      default: gpt-5.4-mini        # balanced — most tasks
      commodity: gpt-5.4-nano      # cheapest — judging, extraction, bulk
    api_key_env: OPENAI_API_KEY
```

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
| Primary Analyst | gpt-4.1 | ~2K in, ~1K out | ~$0.02 |
| Secondary Analyst | claude-3-5-sonnet | ~2K in, ~1K out | ~$0.02 |
| Generation | gpt-4.1 | ~3K in, ~1K out | ~$0.03 |
| Adversarial | claude-3-5-sonnet | ~1K in, ~500 out | ~$0.01 |
| **Total per round** | | | **~$0.08** |

Extraction is free (RuleBasedExtractor). Direct-address responses add another generation call (~$0.03 each).

### Budget settings

In `pipeline.yaml`:
```yaml
cost:
  per_round_budget_usd: 1.00    # hard cap per round
  session_budget_usd: 10.00     # hard cap per session
```

At ~$0.08/round, the per-round budget of $1.00 allows ~12 generation calls per round before the gate trips. The session budget of $10.00 supports ~125 rounds — more than any reasonable game.

### Smoke test config

In `pipeline_smoke.yaml`: both providers set to OpenAI `gpt-4.1-mini`, budgets halved ($0.50/round, $2.00/session), adversarial disabled. Cost per round: ~$0.01.

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
(no changes yet)
```
