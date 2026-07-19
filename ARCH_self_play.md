# ARCH — Self-Play / Campaign Tooling

> **Contract for the self-play + benchmark-campaign tooling** — the harness,
> dispatchers, and post-game aggregation that produce the paper's experimental
> cells. Unlike the pipeline-module ARCH files, this covers the *offline
> research tooling* around `GameEnvironment`, not a runtime pipeline module.
> Companion docs: `ARCH_flow.md` (the `Flow` contract + Phase 52 harness),
> `ARCH_scenario_authoring.md` (scenario compiler/builder + Path B scoring),
> `papers/PAPER_PLAN.md` §5 (experiment ledger), `papers/WORK_SEQUENCING.md` §9
> (execution order).

## Scope — where the tooling lives (code map)

- **Per-game runner:** `tests/self_play/run_simulation.py` — CLI (`--per-faction-providers`,
  `--bare-prompt`, `--temperature`, `--dry-run`, `--rounds`) → builds a
  `GameEnvironment` and runs exactly one game per process; writes a result JSON.
- **Harness:** `tests/self_play/game_environment.py` — `GameEnvironment`
  (`RoundSteppedFlow` self-play), `_generate_faction_config` (emits the per-faction
  pipeline config from env + overrides), `collect_results`, `score_game`
  (BATNA-relative / Pareto / Nash / surplus + Path B coalition scoring).
- **Dispatchers (bash, run on pirozhok):** `tools/ablation_multi.sh` (generalized;
  supersedes `tools/ablation.sh` + `tools/ablation_jsm1.sh`) — `run` / `runmix` /
  `runrotate` subcommands; `TEMPERATURE` env → `--temperature`.
- **Seat rotation:** `tests/self_play/position_rotation.py` (`cyclic_rotations`,
  `all_permutations`).
- **Aggregation:** `tests/self_play/rank_aggregator.py` — cross-game `mean_rank` /
  `win_rate` pooling over result JSONs (reads `scores.faction_ranks` +
  `faction_models`; excludes no-deal games by default).
- **Cost / provenance:** per-run `metadata` block (Phase 49); per-agent `event_log`
  (Phase 50).
- **Offline fakes (hermetic tests):** `tests/helpers/factories.py`
  (`FakeLLMClient`, `FakeCostAccountant`), `tests/self_play/fake_llm_client.py`
  (`DryRunLLMClient`).

## Runtime temperature seam (reference)

`llm_providers.<slot>.temperature` (pipeline YAML) → `_OrchestratorCore._build_llm_configs`
(default 0.7) → per-module `llm_config` dict → `src/adapters.py` `ToolkitLLMAdapter.complete`
→ `LLMConfig.temperature` → toolkit `llm_client`. The self-play path **bypasses**
`pipeline.yaml`'s providers: `_generate_faction_config` rebuilds `llm_providers` from
env and (today) applies `self.temperature` to **only the generator slot**. Reasoning
models (gpt-5.x / o-series) reject `temperature != 1`; the toolkit omits the param for
them, so those cells always run at 1 regardless of the flag.

---

## Phase 51 — Paper hygiene (uniform temperature · external index · N-pooling + CIs) (planned · Build 🔨)

> Phase intent for the i2c PLAN action. Regime: **Build** (AI-evaluable) — every
> deliverable below is pure-code/data, **hermetic (no LLM calls, zero cost)**, and
> gated by offline unit tests. Architecture is pre-decided (D-66) so PLAN goes
> straight to steps. Bundles the three `PAPER_PLAN.md` §5.0 / `WORK_SEQUENCING.md`
> §9 "Phase C" hygiene items that gate the construct-validity analysis and the
> unified campaign.

**Why it leads the paper thread.** These three items unblock the §5.7
construct-validity correlation (needs the external index), remove the gpt-5.5
temperature confound from every future cell, and give the aggregator the bootstrap
CIs the experiment ledger requires — all before the (expensive, supervised) unified
campaign spends anything. Cheapest, lowest-risk, fully loopable.

### Item 1 — Uniform temperature across all provider slots

**Problem.** `game_environment._generate_faction_config` applies the `--temperature`
override to the generator's provider slot only; the support modules (analyst =
`secondary`, adversarial = `secondary`, extractor = `primary`, plus reconciler and
scorer via `subsystem_llm_config`) always run at the 0.7 default. A "temp = X cell"
is therefore not uniform, and the gpt-5.5 = 1 confound (`PAPER_PLAN` §5.0) is
undocumented in code beyond a comment.

**Pre-decided fix (D-66).** Apply the resolved `temperature` to **every provider
slot present** in the emitted per-faction config, not just the generator slot. Keep
the reasoning-model exception (gpt-5.x / o-series stay at 1 — the toolkit omits the
param) but make it **explicit**: expose the set of exempt slots/models on the result
so a cell's true temperature profile is recorded rather than implied. Bring
`ablation.sh` + `ablation_jsm1.sh` to `TEMPERATURE`-env parity with
`ablation_multi.sh` (additive shell edit; not test-gated — `ablation_multi` supersedes
both).

**Acceptance criteria (tests-first, hermetic):**
1. With `temperature=X`, `_generate_faction_config` emits `temperature: X` on **every**
   provider slot in the returned config (generator + all support slots), asserted on
   the in-memory/emitted config — no LLM call.
2. With `temperature=None`, **no** override is injected: the default (0.7) path is
   preserved unchanged (regression guard).
3. A reasoning-model slot (e.g. a gpt-5.x generator) is recorded as the **documented
   exception** — the result/metadata names which slots are temperature-exempt.
4. Existing self-play suite (`tests/test_self_play.py` et al.) still passes.

### Item 2 — External capability-index lookup (roster → LMArena Elo + MMLU)

**Purpose.** A static, offline lookup the §5.7 construct-validity analysis pairs with
per-model Diplomat scores (Diplomat-vs-Elo/MMLU correlation). New; paper-only.

**Pre-decided architecture (D-66).** New **Diplomat-side** module
`tests/self_play/external_index.py` (alongside `rank_aggregator.py`) — *not* the
shared `toolkit` tree (this is a paper reference table, not load-bearing runtime).
Mirror the established metadata pattern in
`toolkit/src/toolkit/cost_accountant/types.py` (`DEFAULT_PRICING`, frozen
`ModelPricing`) and `core.py` (`normalize_model_name`, strip date suffixes; exact →
normalized → fallback resolution):
- `ExternalIndex` frozen dataclass: `lmarena_elo: float`, `mmlu: float`,
  `source: str`, `as_of: str` (provenance is mandatory).
- `EXTERNAL_INDEX: dict[str, ExternalIndex]` covering the Paper-1 roster: gpt-4.1-nano,
  gpt-5.4-mini, gpt-5.5, claude-haiku-4-5, claude-sonnet-4-6, claude-opus,
  deepseek-v3, deepseek-r1.
- `lookup(model: str) -> ExternalIndex | None` with the same normalize→exact→fallback
  resolution as `estimate_cost`.

**Acceptance criteria (tests-first, hermetic):**
1. Every roster model resolves via `lookup()` (including through `normalize_model_name`
   date-suffix variants, e.g. `claude-sonnet-4-6-2026-…`).
2. Each entry carries both indices in sane ranges (Elo 800–1600; MMLU 0.0–1.0) and a
   non-empty `source` + `as_of`.
3. An unknown model returns `None` (or the documented fallback), not a crash.

> **Supervised follow-up (not a Build gate):** the *numeric values* are confirmed
> against their cited sources by the operator (a Refine 👁 check). Tests lock
> structure/presence/range, not value correctness — an autonomous loop must not be
> trusted to invent leaderboard numbers.

### Item 3 — Lock N-pooling + deterministic bootstrap CIs

**Problem.** `rank_aggregator.py` pools N games per cell (`mean_rank` / `win_rate`)
but reports **no confidence intervals**; `PAPER_PLAN` §5.0 requires "N≥10–20 +
bootstrap CIs." A bare "confirm the dispatcher" is not AI-evaluable, so this item is
scoped (D-66) to: **(a)** lock the N-pooling contract with tests, and **(b)** add a
deterministic bootstrap-CI helper.

**Pre-decided architecture (D-66).** Add a **deterministically seeded** bootstrap
helper (fixed default seed) — either in `rank_aggregator.py` or a sibling
`tests/self_play/aggregate_stats.py` — `bootstrap_ci(values, *, seed, iterations,
alpha) -> (point, ci_low, ci_high)`. Pure-Python/stdlib (`random`), no new deps.
Pooling-contract tests use synthetic result-JSON fixtures (no games run).

**Acceptance criteria (tests-first, hermetic):**
1. **N-pooling:** aggregation over K synthetic result files for one (model, scenario)
   cell pools exactly K games; no-deal exclusion behaves as documented.
2. **Determinism:** `bootstrap_ci` with a fixed seed returns byte-identical CIs across
   runs.
3. **Correctness sanity:** `ci_low <= point <= ci_high`; wider `alpha` → wider CI;
   degenerate inputs (n=1, all-equal values) handled without error.

### Out of scope (record, don't build here)
- The unified campaign itself (Run 👁, cost/judgment — `WORK_SEQUENCING` Phase D).
- Confirming the *correctness* of the external-index numbers (supervised).
- The mechanism classifier (§4.1) and capability probe battery (§4.2) — separate
  Phase-A builds; both need LLM keys + cost.
- Any seat-rotation redesign (`position_rotation` stands as-is).

**Regime.** Build 🔨 (autonomous-loopable). Three independent items → expect several
steps (temperature fix + test · external_index module + test · bootstrap/pooling +
test · shell parity · doc-update). Loops run on pirozhok via the i2c bot, not the
laptop (`rules/deployment.md`, FU-28).
