# ARCH: Self-Play Conversation Model

## Purpose
Captures the design space for how agents take turns and react to each other inside the self-play harness, the staging plan we're committed to, and the trade-offs at each level. This is *not* about the production Telegram orchestrator (which is reactive by design); it is about what the `GameEnvironment` test harness asks of those orchestrators when running games for experimentation.

## Why this doc exists
The first attempts at Run 7 surfaced that the orchestrator's built-in auto-response trigger (`_is_direct_address`) fires on every inbound message mentioning the faction id. In a 3-faction coalition game where every message mentions every faction, each agent ends up running its response pipeline 4-5 times per round — way more than the 1-per-agent-per-round that the harness is structured to capture. With instant fakes this just wastes work; with real ~5 s/call LLMs it produces silent message loss because most generations don't complete before the next round starts.

That bug forced an explicit design choice: how should agents converse inside a self-play game? Several valid models exist; this doc enumerates them and stakes out a staged migration path so future-us doesn't have to re-discover this design space from scratch.

## The Model Taxonomy

| Model | Mechanism | LLM calls per round | Realism | Build cost |
|-------|-----------|---------------------|---------|------------|
| **M1: Single-shot, sealed** | All agents speak once, simultaneously, can't see each other | F | Low | 0 (suppress auto-trigger) |
| **M1.5: Sequential within round** | All agents speak once, in order; later speakers see earlier ones | F | Medium | ~30 min |
| **M2-bounded: K passes** | Round = K passes; each agent speaks once per pass; e.g. K=2 → "open then react" | K×F | Medium-high | ~1-2 hr |
| **M2-debounced: Reactive with quiescence** | Agents auto-fire on what they care about; debounce filter; round ends on N-second silence or max-msg cap | Variable (3-10×F) | High | ~half-day |
| **M2-async + strategic timing** | Agents *choose* their delay before speaking. Delay itself becomes a signal (eagerness, deliberation, control) | Variable; plus a "speak again?" decision per agent | Very high | Multi-day, lots of design |

(Where **F** = number of factions and **K** = configured number of passes.)

## What Gets Harder as We Move Down

- **Round termination.** M1 has explicit `run_round()` control. M2-debounced needs quiescence detection ("everyone went silent for 5 s"). M2-async needs both that AND ways to break feedback loops.
- **Cost predictability.** M1/M1.5 are exactly F or K×F per round, easy to budget. M2-debounced can vary 3-10× from one round to the next.
- **Scoring snapshot.** With M1, the final-round response is unambiguous. With M2-debounced, what gets scored? The last message? The last "I commit to X"? An agent's overall position at the moment of round end?
- **LLM latency races.** With async, the agent with the fastest model effectively wins position. If A generates in 4 s and B in 6 s, A's response goes out first regardless of who *should* be the first speaker. This is technically interesting (treating response time as part of agent capability) but it confounds experimentation across model swaps.
- **Stale context.** If A is mid-generation when B finishes and broadcasts, should A re-generate to incorporate B's new statement? Discard? Send the now-stale response? These are real engineering choices, not just plumbing.
- **Feedback loops.** A responds to B, B responds to A's response, A responds back. Without bounds, oscillation forever. Need rate limits or fatigue.
- **Persona consistency.** Does each agent stay in character even when interrupted mid-thought?

## What Gets More Interesting

- **Strategic timing** in M2-async is genuinely novel research territory. "I want to be last so I can react to everyone" is real diplomatic behavior. Long silence as pressure. Rapid replies as enthusiasm or panic.
- **Real-time coalition formation.** In M2-bounded with K=2, A and B might co-propose in pass 1 before C even has a chance to weigh in. Closer to actual coalition-game dynamics.
- **Emergent patterns.** Agents may develop filibustering, anchoring, interrupting — behaviors we never programmed.

## Staged Migration Plan

Each stage is independently usable and informative. The decision to advance is gated on whether the previous stage's data suggested it's worth the extra complexity.

### Stage 0 — Current (broken hybrid; do not run)
The orchestrator's auto-trigger fires on every inbound message; `GameEnvironment` explicitly calls `run_response_pipeline()` once per round on top. With real LLM latency this produces a race where some generations are silently lost and the actual game state is unstable. **Status:** This is what produced the two failed Run 7 attempts. We are leaving Stage 0 immediately.

### Stage 1 — M1 (single-shot sealed) ← TARGET FOR RUN 7
Suppress the orchestrator's auto-trigger when the harness asks for it. Each agent runs its response pipeline exactly once per round, only via the explicit call from `run_round()`. All three agents generate at roughly the same time without seeing each other's current-round responses. Their context includes the prior round's transcript.

- **Build:** small flag on the orchestrator (`auto_response_enabled = False` in self-play setup).
- **Cost:** 1× F generations per round.
- **Pros:** predictable, cheap, easy to analyze, comparable to all prior runs (which were effectively M1 by accident — silent message loss meant most auto-responses didn't matter anyway).
- **Cons:** sealed-bid feel; no within-round reactivity.

**Decision rule to advance:** if Run 7 produces clean endgame data (agents do shift commitment language late vs early), then the experimental question is answered and we can take time on Stage 2. If Run 7 shows agents being too "isolated" (e.g. ignoring obvious trades that opponents proposed), Stage 2 may be necessary to surface real dialogue dynamics.

### Stage 2 — M2-bounded with K=2 (open + react)
Each round consists of K=2 passes. In pass 1 each agent opens (sees only the prior-round transcript). In pass 2 each agent reacts (sees pass-1 responses from all factions). Round ends after pass 2. Randomize agent order each pass to balance position advantage.

- **Build:** restructure `run_round()` to call agents K times; broadcast pass-1 responses to all transports before pass 2 starts. ~1-2 hr.
- **Cost:** K × F generations per round (2× M1 baseline).
- **Pros:** real within-round reactivity; coalition formation can happen in real time; still bounded cost.
- **Cons:** 2× cost; more complex result analysis (per-pass metrics).

K could be configured per scenario (`K=2` for trade summits, `K=3` for coalition games where the close-pass matters more, `K=1` to reduce to M1).

**Decision rule to advance:** if K=2 dialogue is meaningfully richer than M1 sealed responses AND we want to study real-time conversation dynamics (interruptions, alliances forming mid-round), proceed to Stage 3. If K=2 is enough, stay here.

### Stage 3 — M2-debounced (reactive with quiescence)
Agents react to messages they care about, with a debounce filter (no more than 1 message per agent per T seconds). Round ends after N seconds of channel silence OR a hard max-message-count.

- **Build:** ~half-day. Quiescence detection, debounce mechanism, round-end conditions, feedback-loop guards. Requires rethinking scoring snapshot.
- **Cost:** variable, 3-10× M1; needs hard cap to be budgetable.
- **Pros:** realistic conversation dynamics; emergent behaviors.
- **Cons:** harder to analyze; variable cost; race conditions become real; LLM latency starts mattering experimentally.

### Stage 4 — M2-async with strategic timing
Agents output not just text but also a "next-response-delay" choice or probability of speaking again. Delay itself becomes a strategic signal.

- **Build:** multi-day. New schema for generation output. New scoring rules. Heavy design work on what timing means.
- **Cost:** variable, similar to Stage 3.
- **Pros:** novel research territory. Timing is a real diplomatic dimension.
- **Cons:** confounds model-quality experiments (fast model wins by default); huge design surface.

## Current Commitment

We are at **Stage 1** as of 2026-05-29. The single auto-trigger gate is the only change needed to leave the broken Stage 0 hybrid. Run 7 will execute under Stage 1 (Model 1).

Stage 2 work begins after Run 7 produces results, IF those results either (a) confirm endgame awareness works and we want to push for richer dialogue, or (b) show agents are too isolated to test interesting hypotheses.

Stages 3 and 4 are not on the near roadmap. They are documented here so we don't reinvent them later.

## Out of Scope for This Doc

- Specific scoring rules per model (Stage 3+ will need this; deferred until Stage 3 is on the table).
- Anti-collusion rules for agents that share architecture/model (relevant in Stage 2+ when agents can react in real time).
- How to handle agent silence as a strategic move (Stage 4 territory).
- Production Telegram orchestrator behavior — that is governed by `ARCH_orchestrator.md` and stays reactive by design; this doc is about the *harness*.

## Cross-References

- `ARCH_orchestrator.md` — the orchestrator's `auto_response_enabled` flag (added at Stage 1) and the existing `_is_direct_address` auto-trigger logic.
- `tests/self_play/game_environment.py` — the harness that drives self-play.
- `TUNING_LOG.md` — Run 7 entry will reference this doc to record the conversation model in use.
- `DRY_RUN_PLAN.md` — the dry-run infrastructure that lets us validate each stage cheaply before live runs.
