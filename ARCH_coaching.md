# ARCH: Coaching (Diplomat-specific operational notes)

> The **module specification** (parser API, types, config format, usage) is
> in `toolkit/ARCH_coaching.md`. This doc holds only the Diplomat-specific
> operational guidance for how coaching is used in a multi-round diplomacy
> game: philosophy, cadence, edit-log feedback loop, and forward-only
> behavior. Wiring in Diplomat is in `src/orchestrator.py` (consumes
> `toolkit.coaching.TaggedCoachingParser`) and the routes config is in
> `config/coaching_routes.yaml`.

## Diplomat routing

Tags used (see `config/coaching_routes.yaml`):

| Tag | Route | Notes |
|---|---|---|
| `PRIORITY` | `coaching_queue` | Compass for next round; consumed by next Generation |
| `CONSTRAINT` | `coaching_queue` | Hard boundary or trap detected |
| `INTEL` | `state_updater` | Factual correction; routed through Extraction to State Manager |
| `TONE` | `coaching_queue` | Behavioral adjustment |
| `WATCH` | `coaching_queue` | Attention direction |
| `default` (untagged) | `coaching_queue` | Free coaching |

Slash commands handled by the Orchestrator: `/preview`, `/approve`, `/edit`,
`/revise`, `/block`, `/status`, `/state`, `/ledger`, `/intel`, `/divergences`,
`/edits`, `/edits-summary`, `/commands`.

## Outputs in Diplomat

- `CoachingEvent` with `route='state_updater'` → forwarded to Extraction
  with `trigger_type='intel_correction'`.
- `CoachingEvent` with `route='coaching_queue'` → stored in the `coaching`
  table, consumed by the next Generation call.
- `Command` → dispatched by the Orchestrator to the appropriate handler.

## Philosophy & Operational Notes

> Originally diplomat-system-spec.md §7. Migrated here 2026-06-02 when the
> spec was retired. Kept here (rather than in toolkit) because operational
> cadence is domain-specific — toolkit defines the mechanism, Diplomat
> defines the practice.

### Philosophy

Coaching is an **intervention, not a feed.** Frequent low-signal coaching
creates noise in the Context Assembler's input and makes agent behavior
erratic. The goal is sparse, high-signal input that steers without replacing
the agent's judgment.

The agent executes negotiation, promise tracking, and faction heuristics.
Coaching addresses what only the operator can see: the behavior of human
coaches behind opposing agents, judgment calls outside the faction prompt's
scope, and systematic biases in the configured heuristics.

Coaching should **decrease over the game** as the faction prompt improves
from review gate feedback. Heavy coaching in final rounds indicates a prompt
that needs updating, not a coaching cadence that needs increasing.

### Cadence

Typical round:
- *Pre-round:* one `PRIORITY`, one `CONSTRAINT` if a trap is visible
- *Mid-round:* zero to one targeted correction
- *Pre-response:* approve, edit, or block via the review gate

More than two or three inputs per round signals that either the faction
prompt needs tightening or the operator is playing the game rather than
coaching an agent.

### Review Gate Edit Log → Prompt Refinement

Every review gate decision is written to `review_gate_edits`. At each round
boundary, `/edits` returns this log.

**Auto-classification (Phase 33):** Every `action='edited'` row in `review_gate_edits`
can now be classified into one of six categories (`tone_softer`, `tone_harder`,
`commitment_removed`, `ambiguity_added`, `constraint_enforcement`, `persona_correction`)
by `LLMEditClassifier` (see `src/modules/edit_classifier/`). Two surfaces:

- **`/edits-summary`** — operator command available mid-game. Lazy-classifies any
  unclassified edits on the fly and renders a markdown summary table: category, count,
  most-recent example pair (original + edited, truncated to 80 chars). Use during a
  game to detect emerging patterns without leaving the chat.
- **`tools/classify_edit_log.py`** — post-game bulk classifier. Query the DB, skip
  already-classified rows (unless `--force`), write results to `edit_classifications`
  table, print a summary table. Use after a full run when you want the complete picture.

Recurring patterns — consistently `constraint_enforcement` or `persona_correction` edits —
indicate the faction prompt is not enforcing its own rules. Those patterns should be
written into `config/faction_prompt.txt` directly. The coaching correction should
eventually become unnecessary.

**Target state:** by mid-game, the review gate is mostly approving without edit.

### What Coaching Does NOT Affect

- Messages already posted (the event log is append-only — there is no recall)
- Analyst outputs already written for the current round (regenerate only on the next round boundary)
- INTEL corrections do **not** backfill past intelligence records — they update state forward from the point of correction, and the next Analyst run will reflect them

This forward-only behavior is intentional: it keeps the audit trail clean
and prevents the operator from rewriting history mid-game.
