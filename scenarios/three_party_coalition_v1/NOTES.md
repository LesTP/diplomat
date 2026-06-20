# Three-Party Coalition v1 — Scenario Notes

## Source

Generated 2026-06-12 from `scenarios/three_party_coalition.md`
via `scenario_authoring.scenario_compiler --scenario ... --output-dir
scenarios/three_party_coalition_v1/ --scenario-title
"Three-Party Coalition"`.

Narrative source: Susskind / Harvard PON Three-Party Coalition Exercise per
`Multi-Party Negotiation Scenarios.md` — three organizations A, B, C, with
confirmed coalition values v(AB)=118, v(AC)=84, v(BC)=50, v(ABC)=121,
singletons=0. The "barely better than AB" knife-edge on grand coalition
plus the indifference dynamic for excluded factions is what makes the
scenario interesting as a coalition-formation test.

## Hand-patched 2026-06-12 — restore Susskind structure

The compiler softened the coalition-coercive structure into cooperative-flavored
issues. Direct edits applied to `scenario_analysis.json` to restore the
Susskind dynamics. All patches are surgical — schema unchanged, no field
additions or removals.

| Field | Compiler default | Patched value | Rationale |
|---|---|---|---|
| `batna.a` | 5 | **0** | Match narrative "A alone: 0" |
| `batna.b` | 5 | **0** | Match narrative "B alone: 0" |
| `batna.c` | 4 | **0** | Match narrative "C alone: 0" |
| `scoring.a.coalition_choice["BC coalition formed and value split"]` | 1 | **0** | Excluded faction in 2-party coalition gets nothing |
| `scoring.b.coalition_choice["AC coalition formed and value split"]` | 2 | **0** | Excluded faction in 2-party coalition gets nothing |
| `scoring.c.coalition_choice["AB coalition formed and value split"]` | 1 | **0** | Excluded faction in 2-party coalition gets nothing |
| `scoring.a.coalition_choice["ABC ..."]` | 8 | **7** | Drop ABC `sum` from 23 to 21, restoring the AB=19 ≈ ABC=21 knife-edge |
| `scoring.b.coalition_choice["ABC ..."]` | 7 | **7** | (unchanged — already 7) |
| `scoring.c.coalition_choice["ABC ..."]` | 8 | **7** | Drop ABC `sum` from 23 to 21 |
| `pressure.round_cost_decay` | 0.5 | **0** | Strip pressure for clean Path A baseline; can re-enable later for pressure variant |
| `pressure_profile.time_pressure` | medium | **low** | Strip pressure for clean Path A baseline |

Asymmetric clocks (`pressure.asymmetric_clocks`) left as compiler default
since they're informational rather than penalty-applying in the current
schema rendering.

## Resulting landscape

After patches, `verify_scenario_optimum.py` reports:

| Deal | a | b | c | Sum | Pareto? | Beats all BATNAs? |
|---|---|---|---|---|---|---|
| **ABC** | 7 | 7 | 7 | 21 | **P+** | **YES (strict)** |
| AB | 9 | 10 | 0 | 19 | P- | No (c=0=BATNA, tied) |
| AC | 7 | 0 | 9 | 16 | P- | No (b=0=BATNA, tied) |
| BC | 0 | 6 | 7 | 13 | dominated | No (a=0=BATNA, tied) |

**Three Pareto-optimal deals** (ABC strict, AB and AC tied with one
excluded faction). **Only ABC strictly beats all BATNAs** because excluded
factions in 2-party coalitions get exactly BATNA = 0.

**The key dynamic for Path A / B testing:** AB is reachable only if C
agrees to a deal that gives C nothing (= BATNA). C is **indifferent**
between agreeing to AB (gets 0) and blocking (gets 0). What C *does* in
that indifference determines whether the harness produces "no deal,
everyone at BATNA" or "A+B coalition forms and splits 19."

Under the current `score_game()` unanimity logic, "C agrees to AB" still
produces an outcome where A+B share the 19 (assuming the deal-detection
treats AB as a valid agreed outcome). Under Path B (§3.6 coalition-value
scoring engine), C dissent on `coalition_choice = AB` triggers a partial
agreement detection → A+B split coalition_value(AB) → C scored at BATNA.

## First consumer

Path B build (`ASSESSMENT.md` §3.6 coalition-value scoring engine, queued
as Tier 1 under `DECISIONS.md` D-56). When that lands, this scenario is
the first test case — exercises the partial-agreement detection,
coalition value lookup, split-share extraction from transcript, and
excluded-faction BATNA assignment.

Until Path B lands, Path A (`NEXT_STEPS.md` §11.b) uses this scenario in
the existing unanimity frame — useful for transcript inspection of
mixed-model coalition behavior even without proper exclusion scoring.

## Re-generation

If the compiler output ever needs to be re-generated (e.g., to test
compiler improvements), the patches above are mechanical and should be
re-applied to the fresh compile. Alternative: extract the post-patch
scoring tables into a fixture file that the compiler can be asked to
preserve verbatim.

## Cross-references

- `Multi-Party Negotiation Scenarios.md` — Susskind narrative source
- `NEXT_STEPS.md` §11 — competitive scoring path discussion + §11.b Path A test
- `RESEARCH_NOTES.md` Note 2 — coalition-exclusion gap diagnosis
- `ASSESSMENT.md` §3.6 — coalition-value scoring lens specification
- `DECISIONS.md` D-56 — direction commit putting Path B + Path A on Tier 1
- `scenarios/three_party_coalition.md` — original narrative
- Conversation log 2026-06-12 — patch decisions discussed in detail
