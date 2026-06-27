# Diplomat — Development Log

<!-- Reverse-chronological record of what happened during development.
     Each step or milestone gets a structured entry. This is the audit trail.
     Older phases are archived to DEVLOG_archive.md; the active log holds the current phase. -->

## 2026-06-27: Consolidate deal-explorer viz under one convention (operator-supervised)

- **Mode:** Debug / Refine -> Code
- **Outcome:** complete
- **Contract changes:** none (regeneration only; layout contract unchanged, 8/8 tests pass)

The Water Rights (beta-squeezed) and Joint Space Mission viz were ad-hoc artifacts
at repo root (`viz_wrbeta.html`, `viz_jsm1.html`) on the pre-D-63 `.scen2`/`.scencol`
layout, while the newer succ-v3/succ3b viz already lived in their scenario folders as
`deal_explorer.html` on the current `.scenflow` layout. Unified all four:
- Rewrote `tools/build_viz.py` into the canonical regen-all driver - one job per
  scenario, each rendering `scenarios/<name>/deal_explorer.html` (narrative .md
  auto-detected via `find_narrative`).
- Regenerated all four through the pipeline: WR-beta (29 runs) and JSM (28 runs) now
  carry the new layout + narrative; succ3b refreshed to Run 21's 6 runs; succ-v3
  unchanged (0 runs, not live-tested yet). All report `narrative yes`.
- Deleted the two stale root files.

Notes for the record (two false alarms ruled out during review): the `·` "mojibake"
was only a PowerShell console artifact (bytes are correct UTF-8 `C2 B7`); and the
scenario narratives were never stranded in the HTML - every scenario has a proper
narrative .md at `scenarios/` root (`water_rights.md`, `joint_space_mission.md`, ...),
which the renderer pulls in automatically. Contract locked by
`tests/test_scenario_viz.py` (8 passed).

## 2026-06-26: Fix verify_dryrun for bare-prompt runs (operator-supervised)

- **Mode:** Debug -> Code
- **Outcome:** complete
- **Contract changes:** none

`verify_dryrun` assumed full-mode prompt scaffolding (per-round `Round: N of M`
markers, PENULTIMATE/FINAL markers, adversarial/analyst/extraction calls), so on a
bare-prompt live result (Run 21) it raised false failures - the "0 GEN" symptom
was really: GEN calls WERE found but carried no round tag (bare prompts are
transcript-only), and ADV/analyst calls were expected though bare mode disables
them. Fix: detect `bare_mode` from the result and skip the round/marker/adversarial
invariants, checking the applicable subset instead (GEN count == F x R per faction
via the tagged `faction_id`, transcript message count, SCORE, provider routing).
Verified on the committed Run 21 bare result; the full dry-run still passes. Locked
by `tests/self_play/test_verify_dryrun.py`.

## 2026-06-26: Deal-explorer viz polish pass (operator-supervised)

- **Mode:** Debug / Refine -> Code (iterative, operator-verified renders)
- **Outcome:** complete
- **Contract changes:** none (extends the D-63 viz layout contract; locked by tests)

Iterative polish of the scenario deal-explorer (`scenario_viz.py`), all operator-spotted and regression-tested (`tests/test_scenario_viz.py` now 8 tests):
- **Bugs:** multi-line narrative/party bullets no longer truncated; per-issue grid sizes columns to the widest issue (a 2-outcome contested asset no longer clips 3-outcome issues to 2 columns); gamma BATNA label no longer clipped; parcoords height trimmed.
- **Per-issue grid:** faction-colored column headers with an 'Asset goes to:' annotation (dynamic; A/B/C fallback for non-holder-named scenarios); caption generated from the analysis (real faction names + a real example) stating each segment is a faction's payoff, NOT an asset share.
- **Layout:** 'Per-faction outcome' (bars) placed beside 'Parallel coordinates'; both share the faction x-geometry (aligned) and spread edge-to-edge (wide, small margins).
- **Ternary:** live surplus-split readout for the selected deal (replaces the redundant footer hint).
- **Interactivity:** parcoords lines + ternary circles are clickable -> `setDeal` propagates the selection to every chart (+ hover tooltips).

All deal-explorer charts share one renderer, so `tools/viz.py`, `build_viz.py`, and `compile`/`build`/`verify --viz` inherit these. Regenerated `deal_explorer.html` for succ-v3 + succ3b.

## 2026-06-26: Run 21 - succ3b homogeneous baselines (deepseek 0/3 vs sonnet 2/3) (operator-supervised)

- **Scope:** live bare self-play, succ3b, homogeneous baselines (one model on all 3 seats), 3 games each: deepseek-chat and claude-sonnet-4-6. Full RUN_PROTOCOL pre-flight (scenario brief PASS, dry-run PASS, both probes PASS).
- **What this is NOT:** not a seat-rotated mixed-model ranking run (that is the next experiment); not full-mode.
- **Result:** HEADROOM CONFIRMED. deepseek-chat 0/3; claude-sonnet-4-6 2/3. Mechanism: gamma (kingmaker) over-grabs both treasury + defense, starving the heartland loser below BATNA -> partial-coalition no-deal. sonnet avoids it 2/3 (loser gets one asset, gamma the other) = the brief-validated 3-way split. succ3b discriminates capability; not broken.
- **Caveats:** possible alpha seat-bias (alpha won both sonnet deals, n=2 - needs seat rotation); deepseek-r1 unusable (CoT-not-JSON); verify_dryrun mis-reads bare-mode logs.
- **Files:** `tests/self_play/results/run17_bare_{deepseekchat,claudesonnet46}_succ3b_*.json` (committed via git add -f); TUNING_LOG.md Run 21.
- **Cost:** ~$1.3. **Next:** single-provider tier ladder, seat-rotated.

## 2026-06-25: Deal-explorer viz layout - balanced columns + locked contract (operator-supervised)

- **Mode:** Debug -> Code
- **Outcome:** complete
- **Contract changes:** none (viz rendering + a new layout contract, D-63)

Created deal-explorer viz files for succ-v3 and succ3b, then fixed a narrative
layout bug the operator reported (gaping white space). The old `.scen2`/`.scencol`
fixed grid put the intro + most sections in the left column and ONLY the parties
section in the right, leaving a large empty right column whenever parties was
short. Replaced it with a single balanced multi-column flow (`.scenflow`,
columns:2, column-fill:balance) that breaks at PARAGRAPH boundaries
(break-inside:avoid on paragraphs/bullets/issue-lists, break-after:avoid on
headings). Made the requirement durable across sessions (the operator had hit it
repeatedly and the preference did not carry over): DECISIONS.md D-63, a LAYOUT
CONTRACT docstring on `build_scenario_html`, an `ARCH_scenario_authoring.md` note,
and a regression test (`tests/test_scenario_viz.py::test_narrative_layout_is_balanced`)
so any future regression fails the suite. Commits 1c5f1dc, 1b3228c, 009882d.

## 2026-06-25: Author succ3b - 2-outcome-heartland variant (operator-supervised)

- **Mode:** Discuss -> Code (scenario design)
- **Outcome:** complete (brief-passing; live-test pending)
- **Contract changes:** none

Authored `scenarios/succession_division_v3b/` - a 2-outcome-heartland variant of succ-v3 giving a structurally clean alpha-vs-beta contest. Motivation: succ-v3 (3-outcome heartland) routed ~67% of clearing deals to the neutral steward (gamma) - a structural artifact of strict constant-sum + a 3-outcome contested asset, confirmed by a failed gamma-lane rebalance (weakening gamma only raised the clearing count and brought the sweep back). succ3b drops the Gamma-Administered outcome entirely (heartland = Alpha/Beta only), eliminating gamma-steward BY CONSTRUCTION.

**Key finding:** with a 2-outcome heartland, gamma is a PURE KINGMAKER - a BATNA sweep showed gamma cannot win at any non-trivial BATNA (0 wins at BATNA 6-7; 2 only at BATNA 4, where all 18 deals clear = degenerate). So the all-faction `winner_spread` check is wrong for this design and was dropped from the brief; the discrimination signal is the alpha-vs-beta heartland split (3/4 at BATNA 6), with seat rotation making gamma a constant wash. Surfaced a brief-check limitation: no subset-scoped winner_spread (contestants only).

Config: BATNA 6 -> 7 clearing deals, heartland alpha 3 / beta 4, gamma=12 constant, no ties. Brief PASSES (constant_sum, priority_collision soft, no_focal_point, batna_clearing 4-14). Registered as `succ3b` in ablation_multi.sh; narrative succession_division_v3b.md. succ-v3 retained - the two are different instruments (succ-v3 = 3-way contest with steward noise; succ3b = clean 2-way + kingmaker).

Live test (operator, on Pi):
```
bash tools/ablation_multi.sh runrotate 'M1,M2,M3' succ3b bare 3
python -m tests.self_play.rank_aggregator
```

## 2026-06-25: Author succ-v3 discriminating distributive scenario (operator-supervised)

- **Mode:** Discuss -> Code (scenario design; Refine / iterative)
- **Outcome:** complete (authored + brief-passing; live-test pending)
- **Contract changes:** none

Authored `scenarios/succession_division_v3/` - the discriminating distributive scenario Runs 19/20 were reaching for - using the new Phase 44 brief-check as the pre-flight gate. Threads between succ (Run 19 focal-point convergence) and succ2 (Run 20 deadlock): keeps the contested heartland (alpha and beta both rank it #1 -> no focal point) but lowers BATNAs to 7 + widens loser compensation so the contest RESOLVES (13 BATNA-clearing deals; winner_spread {alpha:3, beta:4, gamma:5}). Brief-check PASSES all required features (constant_sum, priority_collision soft, no_focal_point, winner_spread min>=2, batna_clearing 6-18).

**Operator decision (relax no_exact_ties):** a balanced symmetric contest inherently produces a few tied-top deals (the reference `succ` has them too); eliminating every tie requires asymmetry that re-introduces seat-bias. A few ties among 13 contest deals are tolerated and are not a single Schelling focal point. `no_exact_ties` dropped from the brief.

Registered as `succ3` in `tools/ablation_multi.sh` (scenario_paths + error text); narrative seed `scenarios/succession_division_v3.md`. Bundle: scenario_analysis.json, brief.json, brief.md, README.md (auto-doc). Uses `--analysis-json` like succ/succ2, so no persona files are pre-generated.

**Residual to watch in the live run** (brief-check is structural, does not capture this): ~9/13 clearing deals route the heartland to the neutral steward (Gamma-Administered), and one deal (8/8/20) lets gamma sweep while alpha/beta barely clear BATNA. If the live run shows gamma-steward convergence regardless of skill, make Gamma-Administered less attractive and/or raise BATNAs.

**Live test is the real discrimination check** (succ/succ2 were only revealed non-discriminating by live Runs 19/20). Next, on the Pi:
```
bash tools/ablation_multi.sh runrotate 'M1,M2,M3' succ3 bare 3
python -m tests.self_play.rank_aggregator
```

## Phase 48 close (2026-06-25)

**Mode:** Close  
**Outcome:** complete  
**Tests:** 620 passed

**What was built:** Narrative re-skin shell in `src/scenario_authoring/scenario_narrative.py`:
- `apply_relabel(analysis, relabel_map)` — deterministic bijective relabeling of faction/issue/outcome identifiers across the full analysis structure (scores, BATNAs, coalition_values member ids), preserving all numeric values unchanged.
- `assert_structure_preserved(source, reskinned, relabel_map)` — value-isomorphism guard: rejects numeric drift, non-bijective/incomplete maps, missing labels.
- `extract_catalogue_entry(catalogue_text, heading)` — deterministic `###`/`####` heading-scoped section slicer over the prose catalogue.
- `reskin_scenario(analysis, source_context, llm_client, llm_config, tier, *, domain_context)` — one `structured_call` emitting `{relabel_map, logrolling, deception_tactics, narrative_md}`; applies relabel + guard; returns `(reskinned_analysis, narrative_md)`. Initial `RESKIN_SYSTEM_PROMPT` authored (prompt-quality tuning deferred to supervised phase per D-62).
- `main()` CLI entry point for `python -m scenario_authoring narrative`.

Wired into package: `__init__.__all__` exports `reskin_scenario` + `assert_structure_preserved`; `__main__.py` dispatches `narrative` subcommand; `tests/test_scenario_authoring_api.py` pins the public surface. 37 new tests total (27 deterministic core + 6 catalogue extractor + 5 mocked LLM shell). Docs updated: `ARCH_scenario_authoring.md`, `CLI_REFERENCE.md`, `SCENARIO_GUIDE.md`. D-62 closed.

**DEVLOG learning review:** Phase was clean — 4 steps across 4 iterations, each committed first-time with no trial-and-error. No new gotchas to promote.

**Contract changes scan:** `reskin_scenario` + `assert_structure_preserved` added to public API (`__init__.__all__`). No pipeline modules affected. `tests/test_scenario_authoring_api.py` pinned surface updated. No upstream propagation needed.

**Governance updates:** D-62 already closed in DECISIONS.md, ARCHITECTURE.md row 21 + test count updated, coupling note updated, DEVPLAN Phase 48 condensed, entries archived.
