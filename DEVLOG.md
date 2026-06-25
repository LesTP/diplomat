# Diplomat — Development Log

<!-- Reverse-chronological record of what happened during development.
     Each step or milestone gets a structured entry. This is the audit trail.
     Older phases are archived to DEVLOG_archive.md; the active log holds the current phase. -->

## Phase 47 close (2026-06-25)

**Mode:** Close  
**Outcome:** complete  
**Tests:** 583 passed

**What was built:** Coalition-exclusion scoring contract in `tests/self_play/game_environment.py` locked with 23 unit tests across two test classes. `TestFindCoalitionValue` (9 tests): sorted-set match for all coalition pairs + grand, order-normalization, unknown-subset/single-member/empty-list/missing-key → None. `TestResolveDealScores` (14 tests): AB/AC/BC partial coalition paths (members get coalition_values, excluded faction gets BATNA, deal_reached True); grand coalition uses full-agreement path (`faction_score` on `agreed_outcomes`), NOT coalition_values; unknown subset → no-deal (`partial_coalition_without_coalition_values`); below-BATNA → no-deal (`deal_below_batna_for_some_faction`); `deal_reached`+empty agreed_outcomes → normalized (`deal_reached_without_agreed_outcomes`); member absent from entry's values dict → BATNA; non-faction id → no-deal; missing batna key defaults to 0.0; missing factions key → empty faction_scores. `_find_coalition_value` and `_resolve_deal_scores` docstrings updated with precise path documentation per D-61. ARCH_scenario_authoring.md updated with "Coalition Path B scoring contract" section including locked scoring-path table and explicitly deferred supervised items. D-61 closed.

**DEVLOG learning review:** Phase was clean — 3 steps, all committed first-time with no trial-and-error. No new gotchas to promote.

**Contract changes scan:** No external contract changes. `game_environment.py` semantics unchanged (tests lock existing behavior, not new behavior). No upstream propagation needed.

**Governance updates:** D-61 closed, ARCHITECTURE.md row 20 + test count updated, DEVPLAN Phase 47 condensed, entries archived.

## 2026-06-25 — Phase 48 iteration 1

PLAN: activated Phase 48 (frontmatter phase→48, state→execute; removed activation block; committed).

EXECUTE 48.1: created `src/scenario_authoring/scenario_narrative.py` with `apply_relabel` + `assert_structure_preserved` (deterministic core, no LLM, stdlib + sibling imports only). 27 unit tests cover identity round-trip, themed relabel preserving all values, score/batna/coalition_values numeric drift rejection, non-bijective map rejection, incomplete map rejection. 609 tests passing (+27).

## 2026-06-25 — Phase 48 iteration 2

EXECUTE 48.2: added `extract_catalogue_entry(catalogue_text, heading) -> str` to `scenario_narrative.py`. Deterministic heading-scoped slicer: finds exact heading line (### or ####), collects lines until next heading of equal or higher Markdown level. Raises ValueError for unknown headings or non-heading input. Helper `_heading_level(line) -> int` extracted. 6 new tests against real `Multi-Party Negotiation Scenarios.md`: known #### entry extraction, boundary (does not bleed into next peer), content presence, ### level extraction, unknown heading error, non-heading error. 615 tests passing (+6).
