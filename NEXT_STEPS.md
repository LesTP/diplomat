# Diplomat — Next Steps

> **Live forward backlog only.** Closed work lives in `DEVLOG.md` /
> `DEVLOG_archive.md` (phases) and `TUNING_LOG.md` (runs). Findings / theses
> live in `RESEARCH_NOTES.md`. Decisions live in `DECISIONS.md`. Since the
> 2026-07-01 i2c migration the canonical phase state is `.state/` (via the `i2c`
> CLI) with intent in `ARCHITECTURE.md`; `DEVPLAN.md` is a frozen e2e archive.
> Keep this file short — route everything else home.
>
> **Workstream tags** (`ASSESSMENT.md` §5): `[A]` agent architecture & memory ·
> `[B]` prompt tuning · `[C]` game creation & scoring · `[X]` cross-cutting infra.
> **Loop-readiness:** 🔨 pure build · 🔀 mixed · 👁 supervised.
>
> **Direction (D-56, 2026-06-16).** Diplomat is an LLM **negotiation benchmark**.
> Tier 1 = `[C]` game creation & scoring (primary surface); Tier 2 = `[A]`/`[X]`
> infra that serves the benchmark; coaching-product work is deferred
> (infrastructure preserved, no new investment). Rationale: `DECISIONS.md` D-56.

## Forward backlog -> papers/WORK_SEQUENCING.md

> **Retired 2026-06-29.** The live forward backlog is reconciled into the
> paper-driven master plan **`papers/WORK_SEQUENCING.md`** (sections 1-9:
> discriminating scenarios, coalition scoring, the two publication builds,
> construct validity / roster / hygiene, harness-lift, scenario breadth,
> deferred research questions, Tier-2/icebox, and the consolidated execution
> sequence). The former *Current state*, *Now*, *Tier 1*, *Tier 2*, and
> *Deferred (icebox)* lists live there now.

**Project-only residual** (not on the paper critical path; parked in
WORK_SEQUENCING section 8): N4 pressure-on-jsm1; pricing audit; ASSESSMENT 3.4
persuasion / concession-curve signatures; surplus-distribution investigation;
narrative re-skin prompt-quality tuning. **Closed build phases 46-48** ->
`DEVLOG.md`.

## Where things live

- **Forward work sequence (master)** -> `papers/WORK_SEQUENCING.md`
- **Closed phases / runs** → `DEVLOG.md` · `DEVLOG_archive.md` · `TUNING_LOG.md`
  (+ `TUNING_LOG_archive.md`). No closed-items audit is kept here.
- **Findings / theses** → `RESEARCH_NOTES.md`: Note 1 (harness contribution =
  f(scenario shape, what the model already does well)), Note 2 (competitive vs
  cooperative scoring; Paths A/B/C), Note 3 (provider consistency as a deal
  variable).
- **Decisions** → `DECISIONS.md` (D-56 benchmark direction; D-58/D-59 scenario
  tooling; D-60 standalone leaf, D-61 coalition contract scope, D-62 narrative re-skin, D-63 viz layout).
- **Scoring framework** → `ASSESSMENT.md` (§3 lenses, §5 workstream tiers).
- **Scenario authoring** → `SCENARIO_GUIDE.md` + `ARCH_scenario_authoring.md`.
