# Three-Party Coalition — Scenario Notes

Source narrative: `../three_party_coalition.md`
Compiled: 2026-06-20 via `python -m scenario_authoring.scenario_compiler` with
the Phase 2a `coalition_values` support landed.

## Structure

This is a **coalition-coercive** scenario (cooperative game theory). The
narrative gives the characteristic function directly:

| Coalition | Total value | Source |
|---|---|---|
| A alone | 0 | narrative |
| B alone | 0 | narrative |
| C alone | 0 | narrative |
| A+B | 118 | narrative |
| A+C | 84 | narrative |
| B+C | 50 | narrative |
| A+B+C | 121 | narrative |

The compiler maps these onto Diplomat's 1-10 point scale via the new
`coalition_values` field on `scenario_analysis.json`. The values preserve
the narrative ordering (ABC > AB > AC > BC) within the available range:

| Coalition | a's share | b's share | c's share | Sum (compiled) | Narrative |
|---|---|---|---|---|---|
| A+B | 6 | 7 | — | 13 | 118 |
| A+C | 5 | — | 6 | 11 | 84 |
| B+C | — | 4 | 3 | 7 | 50 |
| A+B+C | 7 | 6 | 5 | 18 | 121 |

The 1-10 scale compresses the dynamic range, but the ordering and relative
gaps are preserved enough for the negotiation dynamic (ABC barely beats AB;
BC is the worst pair).

## Manual edits after compilation

The compiler was re-run on 2026-06-20 with default settings; the operator's
prior calibration was restored via a small hand-edit before commit:

| Field | Compiler default | Operator value | Why |
|---|---|---|---|
| `batna.{a,b,c}` | 5 (50% of max score) | 0 | Narrative is explicit: "alone: 0" |
| `pressure.round_cost_decay` | 0.5 | 0 | Narrative has no time-pressure language |
| `pressure_profile.time_pressure` | medium | low | Same |

Persona `.txt` files were regenerated from the patched JSON so they
reflect the BATNA=0 calibration.

## Why coalition_values matters

Before Phase 2a, partial-coalition payoffs were encoded by hand in the
`scoring` tables of a synthetic `coalition_choice` issue (e.g., setting
`scoring.a["BC coalition formed"] = 0` to represent A being excluded).
That workaround had two problems:

1. The "everyone agreed on the BC coalition outcome" interpretation
   doesn't make sense — BC by definition excludes A; A wouldn't agree.
2. The scoring engine couldn't distinguish partial agreement from full
   agreement; both went through `faction_score()` on agreed outcomes.

With Phase 2a's `coalition_values` field and the updated `score_game()`
branching, partial coalitions are first-class: the LLM scorer identifies
the agreeing subset (`coalition_members`), the engine looks up
`coalition_values` for that subset, members get their values, and
excluded factions fall back to BATNA.

The `scoring` tables remain populated (for the synthetic
`coalition_formation` issue) because Phase 2a runtime detection of
partial coalitions still happens at scoring time, not during gameplay
(that is Phase 2b). The grand-coalition entry in `coalition_values` is
documentation; it is unused at scoring time because `score_game()`
routes full agreement through the `scoring` tables, not
`coalition_values`.

## Outstanding

- Phase 2b would surface partial-coalition formation during gameplay
  (in `RoundSteppedFlow` / round loop), not just at game end. Today the
  LLM scorer at game-end is the only consumer.
- The synthetic `coalition_formation` issue is now somewhat redundant
  with `coalition_values` as the canonical source for partial outcomes.
  Future cleanup could deprecate it.
