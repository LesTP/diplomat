# Diplomat — Development Log

<!-- Reverse-chronological record of what happened during development.
     Each step or milestone gets a structured entry. This is the audit trail.
     Older phases are archived to DEVLOG_archive.md; the active log holds the current phase. -->

## 2026-06-25 — Phase 44: scenario brief + verify-against-brief + auto-doc

Phase 44 adds a per-scenario **design brief** and a machine-checkable
verify-against-brief gate — the structural check Runs 19/20 lacked. A brief
declares the discriminating properties a scenario is supposed to have; the check
measures the actual static structure and reports PASS/FAIL per feature, exiting
non-zero so it works as a pre-flight gate before a paid run. Operator-supervised;
scope was full Phase 44 (core + auto-doc + compiler `--viz`).

**What was built:**

- **`src/scenario_authoring/scenario_brief.py` (new):** `load_brief()` (validates
  `brief.json`; rejects unknown/malformed features), `check_brief()` (6 features:
  `constant_sum`, `priority_collision`, `no_focal_point`, `winner_spread`,
  `batna_clearing_count`, `no_exact_ties`), `FeatureCheck`/`BriefResult`,
  `build_brief_readme()` (auto-doc), and a `main()` CLI (`--analysis --brief
  [--doc] [--title] [--viz-rel-path]`). Reuses verifier + fitness math; depends
  only on `verify_scenario_optimum` + `scenario_fitness` + stdlib (standalone
  constraint held).

- **`verify_scenario_optimum.py`:** extracted the inline "everyone-gets-priority"
  focal-deal computation from `main()` into reusable `compute_focal_deal()` /
  `focal_deal_clears_batnas()` (last math duplication removed, Phase-43 pattern);
  added `--brief` flag (runs `check_brief`, rc 2 on any FAIL).

- **`scenario_compiler.py`:** added `--viz [PATH]` + `--viz-title` so the
  narrative creation path emits the deal explorer too (mirrors verify).

- **Public API:** exported `load_brief`, `check_brief`, `BriefResult`; pinned in
  `tests/test_scenario_authoring_api.py`.

- **Golden fixtures:** `brief.json` + `brief.md` in `succession_division_v1`
  (`succ`) and `_v2` (`succ2`). `succ` FAILs `no_focal_point` (the Run 19 focal
  deal scores 13/11/12 and clears all BATNAs) + `no_exact_ties`; `succ2` FAILs
  `batna_clearing_count` (only 4 clearing deals vs intended ≥6) + `winner_spread`
  + `no_exact_ties`. These prove the gate would have caught both runs.

- **Doc sync:** `SCENARIO_GUIDE.md` (new brief section + capabilities + quick-ref),
  `CLI_REFERENCE.md` (`scenario_brief` entry, `--brief` on verify, `--viz` on
  compiler, quick-index + change-history), `ARCH_scenario_authoring.md` (module
  map, public API, key signatures, feature table, implementation + standalone
  notes).

**Files changed:** `src/scenario_authoring/scenario_brief.py` (new),
`src/scenario_authoring/verify_scenario_optimum.py`,
`src/scenario_authoring/scenario_compiler.py`,
`src/scenario_authoring/__init__.py`,
`scenarios/succession_division_v1/{brief.json,brief.md}` (new),
`scenarios/succession_division_v2/{brief.json,brief.md}` (new),
`tests/test_scenario_brief.py` (new), `tests/test_scenario_authoring_api.py`,
`tests/test_verify_scenario_optimum.py`, `tests/test_scenario_compiler.py`,
`SCENARIO_GUIDE.md`, `CLI_REFERENCE.md`, `ARCH_scenario_authoring.md`.

**Tests:** 555 passed, 1 skipped (full suite). The two golden regression tests
assert `succ` FAILs `no_focal_point` and `succ2` FAILs `batna_clearing_count`.

**Process note:** measured the real `succ` structure before authoring its brief —
SCENARIO_GUIDE's claimed "balanced 2/2/2 winner spread, no exact ties" was
aspirational; the actual structure is 1/1/2 with exact ties present, which the
gate now surfaces. Briefs were authored against measured reality, not the prose
claim.

**Contract changes scan:** additive only — three new public exports; no existing
signatures changed. `scenario_brief` honors the standalone constraint.

## 2026-06-23 — Phase 43 close: deal-explorer viz integration complete

Phase 43 extracted the deal-explorer renderer from `tools/viz.py` into a first-class `src/scenario_authoring/scenario_viz.py` package module, wired it into the `verify_scenario_optimum` and `scenario_builder` CLIs, exported it on the public API, and synchronized all reference docs. 5 steps, all 🔨 pure build.

**What was built:**

- **Step 43.1 (new scenario_viz module):** `src/scenario_authoring/scenario_viz.py` now owns `build_deals`, `build_data`, `build_scenario_html`, `render_scenario_html`, and `build_scenario_viz`. The O(n²) Pareto scan was replaced with a call to `find_pareto_frontier` (imported from `verify_scenario_optimum`), eliminating the last math duplication. `tools/viz.py` was slimmed to a run-discovery wrapper that delegates all rendering to the package. Added `tests/test_scenario_viz.py` (4 tests: render markers, `runs=None`/`[]` handling, frontier parity, file write).

- **Step 43.2 (wrapper regression):** `tools/viz.py` already matched the wrapper contract (src/ path insert, package import, run-discovery helpers retained); no source changes needed. Both `viz_wrbeta.html` and `viz_jsm1.html` regenerated cleanly via `python3 tools/build_viz.py`.

- **Step 43.3 (CLI flags):** `verify_scenario_optimum` now accepts `--viz [PATH]` and `--viz-title`; `scenario_builder` now accepts `--viz` and `--viz-output`. Both default to `scenario_analysis.html` when the optional path override is omitted. Pure-additive; existing behavior unchanged when the flag is absent.

- **Step 43.4 (public API):** Re-exported `render_scenario_html` and `build_scenario_viz` in `src/scenario_authoring/__init__.py` under a new "Visualization" group in `__all__`. `tests/test_scenario_authoring_api.py` updated to pin the extended stable surface.

- **Step 43.5 (doc sync):** `SCENARIO_GUIDE.md` (Visualize subsection + quick-ref card row + file-layout note corrected), `CLI_REFERENCE.md` (`--viz`/`--viz-title`/`--viz-output` on verify + builder; `tools/viz.py` wrapper entry), `ARCH_scenario_authoring.md` (new `scenario_viz` module + public visualization symbols).

**Files changed:** `src/scenario_authoring/scenario_viz.py` (new), `src/scenario_authoring/__init__.py`, `src/scenario_authoring/verify_scenario_optimum.py`, `src/scenario_authoring/scenario_builder.py`, `tools/viz.py` (slimmed), `tests/test_scenario_viz.py` (new), `tests/test_scenario_authoring_api.py`, `SCENARIO_GUIDE.md`, `CLI_REFERENCE.md`, `ARCH_scenario_authoring.md`.

**Tests:** 535 passed, 1 skipped (full suite).

**DEVLOG learning review:** No new trial-and-error patterns. Step 43.2 found the wrapper contract already satisfied — a clean zero-change regression step. The O(n²) → frontier-membership swap was the only non-trivial algorithmic change and was straightforward given the existing `find_pareto_frontier` function.

**Contract changes scan:** No cross-module contract changes. `scenario_viz` depends only on `verify_scenario_optimum` (intra-package) and stdlib — the standalone coupling constraint was maintained. `tools/viz.py` now delegates rendering rather than owning it; its CLI flags and output filenames are unchanged.

## 2026-06-23 — Operator-supervised: Phase 43 planning + NEXT_STEPS overhaul + doc routing

- **Mode:** Discuss → Code (documentation only)
- **Outcome:** complete
- **Contract changes:** none (no code/API surfaces touched; documentation routing only)

Operator-supervised session alongside the autonomous Phase 43 run. Two threads:

**1. Phase 43 planning + roadmap.** Discussed integrating the deal-explorer viz
into the `scenario_authoring` subsystem; wrote Phase 43 into `DEVPLAN.md` as a
loop-ready Build phase (5 EXECUTE steps, `state: execute`), which the autonomous
loop then executed (see "Phase 43 close" above). Recorded the forward roadmap in
DEVPLAN Current Status: **Phase 44** (scenario design-brief + verify-against-brief
+ auto-doc), **Phase 45** (narrative-integration tool — numbers-first re-skin from
the negotiation-scenarios catalogue / free-text), **Phase 46** (make
`scenario_authoring` standalone — extract the shared round-context renderer to a
leaf module to sever the lone `modules.persona` coupling in `scenario_compiler.py`,
make `toolkit` an optional extra, add a unified `python -m scenario_authoring` CLI
+ package README). Phase 43 carried an explicit "no new inbound/outbound coupling"
constraint, which the loop honored.

**2. NEXT_STEPS.md overhaul.** The file had grown to ~1106 lines mixing five
content types (live backlog, closed audit, finding narrative, deferred items,
process meta). Rewrote it in place to a lean **105-line live forward backlog**:
header + Current state + Now (sequencing) + Tier 1 (open) + Tier 2 (open) +
Deferred (icebox) + Where-things-live pointers. Routing applied (verify-before-
delete, no information loss):

- Closed audit (Appendix A) + "Tier-1 status snapshot" table + Change History
  table → dropped; canonical detail already in `DEVLOG.md` / `DEVLOG_archive.md`
  / `TUNING_LOG.md`. (Change History not migrated — process meta, recoverable
  from git history; substantive rationale lives in `DECISIONS.md` D-56 +
  `RESEARCH_NOTES.md`.)
- Finding narrative (§10 ablation, §11 competitive scoring) → already canonical in
  `RESEARCH_NOTES.md` Note 1 / Note 2; dropped from NEXT_STEPS.
- Provider-consistency finding (former §1.7 / §1.8) → **consolidated into new
  `RESEARCH_NOTES.md` Note 3** ("Provider consistency as a deal-making variable");
  the follow-up tests moved to the Deferred icebox. Fixed the dangling pointer in
  `TUNING.md` (§1.7/§1.8 → Note 3).
- D-56 coaching-product items (§2.5 strategy routing, §3 conversation model, §4
  coaching loop / Run 13b, §5 game-platform, §7 per-role model, persona tuning) →
  Deferred icebox as one-liners.
- Numbering cleanup: the colliding "Phase 39 exogenous events" / "Phase 40 cascade
  scoring" labels (which clashed with DEVPLAN's actual completed Phase 39
  fill-narrative) → relabeled as **unnumbered deferred pressure mechanisms**.

**Files changed:** `NEXT_STEPS.md` (rewritten 1106 → 105 lines),
`RESEARCH_NOTES.md` (added Note 3), `TUNING.md` (fixed §1.7/§1.8 → Note 3 pointer).

**Known residue (low-harm, deferred):** a few soft `NEXT_STEPS §X` "see also"
pointers remain in frozen archives (`DEVLOG_archive.md`, `TUNING_LOG_archive.md` —
append-only, not edited) and in `DEVPLAN.md` / `PROJECT.md` / `DECISIONS.md`. The
filename is unchanged so the links resolve; only the §-anchors are stale. Can be
swept in the live docs (PROJECT.md, DECISIONS.md) in a later pass.
