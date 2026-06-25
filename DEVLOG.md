# Diplomat — Development Log

<!-- Reverse-chronological record of what happened during development.
     Each step or milestone gets a structured entry. This is the audit trail.
     Older phases are archived to DEVLOG_archive.md; the active log holds the current phase. -->

## Phase 46 close (2026-06-25)

**Mode:** Close  
**Outcome:** complete  
**Tests:** 559 passed, 1 skipped

**What was built:** `scenario_authoring` is now a liftable, self-contained package. The lone load-time pipeline coupling (`scenario_compiler.py → modules.persona`) was severed by extracting `CoachingContext` + `render_round_context_section` + 6 stdlib-only helpers into `src/scenario_authoring/round_context.py`; `modules/persona` re-exports them for back-compat. Standalone contract locked by `tests/test_scenario_authoring_standalone.py` (subprocess isolation check + ImportError-on-missing-toolkit). Unified `python -m scenario_authoring build|compile|verify|brief` dispatcher added in `__main__.py`. Package README written.

**DEVLOG learning review:** Two codex-backend failures in Phase 46 (iter 192 left work uncommitted; iter 196 committed but was cut off before bookkeeping — steps_remaining left at 0). Claude iter 195 finished 46.2 cleanly. Pattern: codex backend repeatedly fails to finish iterations on this project due to turn/time limits and budget re-dispatch anti-pattern. Recommend CLAUDE backend for diplomat iterations (or raise codex turn/time budget and guard against double-dispatch). Promoted to Gotchas.

**Contract changes scan:** No cross-module external contract changes. `modules/persona` public API preserved via re-export. New intra-system direction: `modules.persona` → `scenario_authoring.round_context` (pipeline → package, intentional per D-60).

**Governance updates:** D-60 closed, ARCHITECTURE.md rows 19 + test count + coupling note updated, DEVPLAN Phase 46 condensed, entries archived.

## Phase 47 — Step 47.1 (2026-06-25)

**Mode:** Execute  
**Outcome:** complete  
**Tests:** 19 new, all passed

### Step 47.1: Coalition scoring unit tests

Added `tests/self_play/test_game_environment_coalition.py` with 19 tests covering `_find_coalition_value` and `_resolve_deal_scores` imported directly from `game_environment.py` (no live LLM).

`TestFindCoalitionValue` (9 tests): sorted-set match for AB/AC/BC/grand coalitions; reversed-order input normalizes correctly; unknown subset / single-member not in fixture returns None; empty list and missing key return None.

`TestResolveDealScores` (10 tests): AB/AC/BC partial coalition paths verified — members get coalition_values, excluded faction gets BATNA, deal_reached True; grand coalition (members==all factions) uses faction_score() on agreed_outcomes, NOT coalition_values (key distinction — assertion locks that scoring["a"]["coalition_formation"]["a_b_c"]=10, not cv value 7); full deal with empty coalition_members also uses faction_score(); unknown subset no-deal with `partial_coalition_without_coalition_values`; below-BATNA no-deal with custom analysis (a's BATNA=5, gets 3) with `deal_below_batna_for_some_faction`; deal_reached+empty/None agreed_outcomes normalized to `deal_reached_without_agreed_outcomes`; deal_reached=False gives all-BATNA.

## Phase 47 — Step 47.2 (2026-06-25)

**Mode:** Execute  
**Outcome:** complete  
**Tests:** 4 new edge-case tests, 582 total (23 coalition tests)

### Step 47.2: Harden coalition scoring edges + precise contract docstrings

Added 4 edge-case tests: member present in `coalition_members` but absent from entry's `values` dict → BATNA (not KeyError); non-faction id in `coalition_members` → no-deal (`partial_coalition_without_coalition_values`); missing `batna` key in faction entry defaults to 0.0; missing `factions` key returns empty `faction_scores`. Updated `_find_coalition_value` and `_resolve_deal_scores` docstrings to document all paths precisely per D-61. Explicit handling added only where 47.1 exposed a gap; pre-existing normalizations unchanged.

## Phase 47 — Step 47.3 (2026-06-25)

**Mode:** Execute  
**Outcome:** complete  
**Tests:** full suite green (582 passed)

### Step 47.3: Doc update + Phase 47 close prep

Added "Coalition Path B scoring contract (locked — Phase 47 / D-61)" section to `ARCH_scenario_authoring.md`: locked scoring-path table (5 rows), `_find_coalition_value` sorted-set semantics, and explicitly deferred supervised items (representation rationalization, builder emission, runtime detection, live validation). Phase 47 DEVLOG entries written for 47.2 and 47.3. Step 47.3 checked off in DEVPLAN.
