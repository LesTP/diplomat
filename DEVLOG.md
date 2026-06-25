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
