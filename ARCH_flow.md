# ARCH: Flow

## Purpose

Flow is the scheduling layer around one or more `Pipeline` instances.
`Pipeline` exposes what an agent can do; a Flow decides when those
capabilities run.

This split keeps agent capability stable while allowing new operating
contexts to add their own driver. Production Telegram/CLI service,
self-play, Clankmates polling, customer-service streams, and turn-based
negotiation can share the same Pipeline contract without copying the
old Orchestrator event loop.

## Pipeline Contract

`src/pipeline.py` defines the per-agent capability surface:

- `start()` / `shutdown()`
- `store_event(event) -> event_id`
- `extract_from(event, event_id=None) -> event_id`
- `dispatch_operator(content, event_id="operator-dispatch")`
- `advance_to_round(n)`
- `reconcile_and_analyze()`
- `run_response(trigger_event=None) -> bool`
- `get_state()`
- `get_intelligence()`
- `get_ledger()`

The current implementation is a thin wrapper around the internal
Orchestrator core. That is intentional: the boundary is now public, and
future cleanup can move methods behind it without changing Flow callers.

## Flow Contract

A Flow owns scheduling and external event shape. It may own:

- Listener loops and shutdown behavior
- Debounce or batching strategy
- Round-boundary detection
- Response-trigger policy
- Multi-agent turn order
- Moderator or platform-specific routing

A Flow should call Pipeline methods rather than reaching into module
internals. If a new application needs a capability that is not on
`Pipeline`, add it deliberately to the Pipeline contract instead of
coupling the Flow to the old Orchestrator core.

## Implementations

### EventDrivenFlow

`src/flows/event_driven.py`

Used by production via the `Orchestrator(...)` compatibility factory.
It owns:

- `Transport.listen()` loop
- Per-event extraction tasks (`_extraction_tasks`)
- Signal round detection (`signal_round_detector(pattern)`)
- Time-based round intervals
- Direct-address response trigger (`faction_address_detector(faction_id)`)
- Transport shutdown cleanup

Ordering matches the previous production Orchestrator behavior:

```
store event
if operator: dispatch operator command/coaching
else: schedule per-event extraction
if round boundary: reconcile + analyze, skip direct response
elif direct address: run response pipeline
```

### RoundSteppedFlow

`src/flows/round_stepped.py`

Used by self-play through `GameEnvironment`. It owns:

- Public round advancement via `Pipeline.advance_to_round(n)`
- Moderator round updates
- One explicit response per pipeline per round
- Broadcasting each response to other agents
- Direct end-of-round `Pipeline.reconcile_and_analyze()` calls

`[ROUND END]` is still recorded in the transcript for continuity, but it
is no longer injected through every agent transport as a scheduling
signal. Round stepping is direct now.

## Compatibility Shim

`orchestrator.Orchestrator(...)` remains the public constructor used by
`src/main.py` and older tests. It now returns:

```
EventDrivenFlow(
    pipeline=Pipeline(_OrchestratorCore(...)),
    transport=core.transport,
    round_detector=...,
    address_detector=...,
)
```

`EventDrivenFlow` delegates unknown attribute gets/sets to the core so
existing integration points such as `main._attach_reconciler()` continue
to work during the migration.

## Worked Example: TurnBasedFlow

A new turn-based negotiation driver can be additive:

```python
class TurnBasedFlow:
    def __init__(self, pipelines, moderator, turn_order):
        self.pipelines = {p.orchestrator.faction_id: p for p in pipelines}
        self.moderator = moderator
        self.turn_order = list(turn_order)

    async def run_turn(self, faction_id, message):
        await self.moderator.broadcast_to_all("moderator", message)
        pipeline = self.pipelines[faction_id]
        await pipeline.run_response()

    async def close_round(self, round_number):
        for pipeline in self.pipelines.values():
            pipeline.advance_to_round(round_number)
            await pipeline.reconcile_and_analyze()
```

No extraction, analyst, generation, review-gate, or state-manager code
changes are required unless the new driver needs a genuinely new
capability. In that case, extend `Pipeline` first and keep the Flow as a
scheduler.

## Experimental Harness Configurations

`GameEnvironment` accepts `extra_module_overrides` to substitute stand-in implementations for pipeline modules — used by two experimental configurations:

- **Coached self-play** (`tests/self_play/coached_game.py`): injects `OperatorReviewGate` / `TelegramBotTransport` for one faction, routing that faction through a live Telegram review loop while other factions auto-approve.
- **Bare-prompt ablation** (`tests/self_play/bare_mode.py`): `bare_module_overrides()` produces no-op stand-ins for Extraction, Analyst, Divergence, Reconciliation, Adversarial, and Coaching. `GameEnvironment(bare_mode=True)` calls this automatically and sets `bare_mode=True` on each faction's `OrchestrationOptions` so `DefaultContextAssembler` assembles persona + raw transcript only. Enables the Phase 34 ablation experiment (does the harness contribute, or could a bare-prompt agent perform comparably?).

Neither configuration touches production code. The `extra_module_overrides` seam is the intended extension point for experimental module substitution.

## Testing

Contract coverage lives in:

- `tests/test_pipeline.py` for the Pipeline surface
- `tests/test_flows.py` for EventDrivenFlow and RoundSteppedFlow behavior
- `tests/integration/` for compatibility with the production-style flow
- `tests/test_self_play.py` for GameEnvironment as a RoundSteppedFlow
  wrapper

As of Phase 22.6, the full suite is 308 passing.

---

## Phase 51 — Client-agent ingress (prompt path) + asymmetric 1:1 harness (planned · Build 🔨)

> Phase intent for the i2c PLAN action. Regime: **Build** (AI-evaluable) with the
> one architecture choice pre-decided below (so PLAN can go straight to steps).
> Larger than a leaf phase — several components. Foundation for the Negotiation-QA
> offering (see `OFFERING.md` §3 T1/T2; `papers/OPEN_ITEMS.md` §4).

**Intent.** Let an *external* agent-under-test — a client's customer-service bot,
represented by its **system prompt + model** — negotiate 1:1 against a *simulated
customer* (our persona: hidden priorities + BATNA), scored by the existing
game-theoretic engine. This is the product's foundational capability: a config-only
audit needing no client code and no live integration.

**Two coupled pieces:**

**T1 — Agent-under-test ingress (prompt path).**
- Add a dedicated `ClientAgentGenerator` (implements the generation seam / the
  `llm_client.complete` duck type the pipeline consumes) that produces the
  agent-under-test's turn from **[client system prompt] + [running dialogue
  transcript] → `llm_client.complete()`**, and **bypasses the Context Assembler /
  persona / analyst / adversarial / intel scaffolding entirely** — so we test
  *their* agent, not our harness around it.
- Select the client's model via the existing `--per-faction-providers` mechanism
  (works when the model is a callable provider: OpenAI / Anthropic / Google /
  OpenRouter).

**T2 — Asymmetric 1:1 harness.**
- Extend `GameEnvironment` with an explicit **asymmetric 2-party mode**: roles
  `agent_under_test` (driven by `ClientAgentGenerator`) vs `customer` (our persona,
  on a fixed model we control; full or bare as configured).
- Bounded bilateral exchange (reuse RoundSteppedFlow's turn mechanics at N=2 with
  alternation): terminate on **deal reached / walk-away / turn cap**.
- **2-party-aware scoring/report:** suppress coalition / multi-party analytics at
  N=2; score with the existing BATNA-relative + Pareto + Nash + surplus lenses
  (N-generic) for both parties.

**Pre-decided architecture (keeps this Build, not Explore).** Use a *dedicated*
`ClientAgentGenerator` that sidesteps context assembly (cleaner + more faithful than
reusing `bare_mode` + a `system_prompt_override`), and reuse the existing
round-stepped machinery for the bounded bilateral loop (not a brand-new
`TurnBasedFlow`). Revisit `TurnBasedFlow` only if reactive/variable turn-taking is
later required (`ARCH_conversation_model.md`).

**Acceptance criteria (tests-first — specify before implementing).**
1. **Fidelity (linchpin):** with a fixed client system prompt and a **fake**
   `llm_client`, the agent-under-test's outgoing request contains **exactly**
   `[client system prompt] + [dialogue transcript]` and **none** of our
   persona / analyst / adversarial / intel blocks.
2. **Asymmetric roles:** a 2-party game runs to completion with distinct
   `agent_under_test` vs `customer` roles; no coalition/multi-party analytics are
   produced at N=2; scoring yields BATNA-relative + Pareto + surplus for both.
3. **Termination:** the loop ends correctly on each of deal / walk-away / turn-cap
   (test all three with fakes).
4. **Model wiring:** the agent-under-test uses the configured client model via
   per-faction-providers (unit-testable with a fake provider).
5. **No regression:** existing multi-party self-play (RoundSteppedFlow, N≥3) is
   unaffected; the full suite still passes.

**Scope / fidelity caveat (record, don't build here).** Prompt path is **faithful
only for case-A agents** (client = system prompt + callable base model). Case-B
(tool use / RAG / business-logic wrapper) and case-C (fine-tuned / proprietary /
self-hosted) need the **live-API path** — a separate follow-on that proxies
`complete()` to the client's HTTP endpoint. Out of scope this phase.

**Out of scope.** Live-API ingress; the tactic library + A/B susceptibility metric
(later offering phase, builds on this); continuous-value scoring (T3); any
guardrail/enforcement (Secure tier).

**Regime.** Build 🔨 (autonomous-loopable). Larger phase — expect multiple steps
(generator seam · asymmetric harness mode · termination conditions · 2-party
reporting · tests).
