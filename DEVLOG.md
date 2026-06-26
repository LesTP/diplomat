# Diplomat — Development Log

<!-- Reverse-chronological record of what happened during development.
     Each step or milestone gets a structured entry. This is the audit trail.
     Older phases are archived to DEVLOG_archive.md; the active log holds the current phase. -->

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
