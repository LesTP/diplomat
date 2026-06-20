# Diplomat — Architecture Diagrams

Layered architecture diagrams. Read top-down: overview first, then drill into the
concern you care about. Render with the `render_mermaid_file` tool, or with the
VSCode `Markdown Preview Mermaid Support` extension (`bierner.markdown-mermaid`).

---

## Overview

Five logical groupings. Click any node to jump to its detailed architecture doc.

```mermaid
flowchart LR
    T[Transport<br/>Telegram · CLI]

    subgraph pipe["Pipeline — per-agent surface"]
        direction TB
        LLM[LLM modules<br/>Extraction · Reconciliation<br/>Analyst×2 · Divergence<br/>Generation · Adversarial]
        RG[Review Gate<br/>approve / edit / revise / block]
    end

    subgraph store["Persistence — SQLite"]
        direction TB
        ES[Event Store<br/>append-only log]
        SM[State Manager<br/>structured state + audit]
    end

    FLOW[Flow<br/>EventDrivenFlow · RoundSteppedFlow]
    TK([toolkit<br/>llm_client · structured_llm · cost_accountant])

    FLOW -.drives.-> pipe
    T -->|inbound| pipe
    pipe -->|outbound via RG| T
    pipe <--> store
    LLM -.LLM calls.-> TK

    click LLM "ARCH_extraction.md" "Drill-down: LLM module specs"
    click RG "ARCH_review_gate.md" "Drill-down: review gate"
    click ES "ARCH_event_store.md" "Drill-down: event store"
    click SM "ARCH_state_manager.md" "Drill-down: state manager"
    click FLOW "ARCH_flow.md" "Drill-down: scheduling strategies"
    click pipe "ARCH_orchestrator.md" "Drill-down: pipeline composition"
```

### What this view shows

- **Flow drives Pipeline** — the architectural lever that makes production vs
  benchmark cheap. `EventDrivenFlow` for live Telegram games; `RoundSteppedFlow`
  for self-play benchmarking. Same per-agent capability surface underneath.
- **Pipeline owns the LLM modules and the Review Gate** — every per-agent
  capability hangs off Pipeline.
- **Persistence is two files of one SQLite database** — Event Store
  (append-only log) and State Manager (structured state + audit) own separate
  tables but live in one file.
- **Transport is the only I/O** — Telegram in production, CLI in benchmark.
- **toolkit is the only external dependency** for LLM concerns. All LLM
  modules go through `toolkit/structured_llm` (which in turn uses
  `llm_client` + `cost_accountant`).

### Not shown

| Concern | Where to find it |
|---|---|
| Internal LLM module relationships (Analyst×2 → Divergence, Generation → Adversarial → Review Gate) | Drill-down: round boundary + response pipeline below |
| Coaching Parser, Persona, Context Assembler | Drill-down: inbound processing (Coaching Parser) + response pipeline (Persona, Context Assembler) below |
| Round-boundary sequence (Reconciliation → Analyst → Divergence → intel store) | Drill-down: round boundary below |
| Inbound message routing (extraction debouncing, INTEL routing) | Drill-down: inbound processing below |
| Operator command surface (slash commands, tag routing) | Drill-down: inbound processing below |
| Edit Classifier wiring | `ARCH_edit_classifier.md` |
| Scenario Compiler / Scenario Builder | `ARCH_*.md` for each — pre-game tools, not pipeline modules |
| What runs when (temporal view) | Lifecycle diagram below |

---

## Lifecycle

What happens during a game turn, **per agent**. Three phases in a cycle. Module
activation is the same under both `EventDrivenFlow` and `RoundSteppedFlow` —
only the trigger differs (table below).

```mermaid
flowchart LR
    L["Phase 1 — Listening<br/>(inbound message processing)<br/>Extraction · State Manager"]
    B["Phase 2 — Round boundary<br/>(analyze the round)<br/>Reconciliation<br/>Analyst ×2 · Divergence"]
    G["Phase 3 — Generate + review<br/>(own turn)<br/>Context Assembler · Generation<br/>Adversarial · Review Gate"]

    L -->|round signal| B
    B -->|intel stored| G
    G -.->|posted to moderator<br/>round N+1 begins| L

    classDef listen fill:#e8f4e8,stroke:#5a8a5a,color:#000
    classDef boundary fill:#e8e8f4,stroke:#5a5a8a,color:#000
    classDef generate fill:#f4e8e8,stroke:#8a5a5a,color:#000
    class L listen
    class B boundary
    class G generate
```

### What each phase does

- **Phase 1 — Listening.** Every inbound message (faction speech, moderator,
  operator) is appended to Event Store and routed. Game messages trigger
  debounced Extraction → StatePatch → State Manager. `INTEL:` operator tags
  trigger immediate Extraction with `intel_correction`. Other operator tags
  become unconsumed coaching on State Manager.
- **Phase 2 — Round boundary.** Reconciliation passes over the round's state
  changes (dedup promises, detect fulfillments, flag inconsistencies). Then
  both Analysts read full state + recent transcript in parallel; Divergence
  compares their outputs. Intel + divergences land on State Manager for use
  in Phase 3.
- **Phase 3 — Generate + review.** Triggered on the agent's own turn. Runs the
  response pipeline (see drill-down below): Context Assembler → Generation →
  Adversarial → Review Gate → Transport. After posting, unconsumed coaching
  is marked consumed.

### Trigger differences

| Phase | EventDrivenFlow (production) | RoundSteppedFlow (self-play) |
|---|---|---|
| 1 — Listening | `Transport.listen()` fires on each inbound | Collected messages flushed at step boundary |
| 2 — Round boundary | round_signal message from moderator | End-of-round (all factions have spoken) |
| 3 — Generate + review | Agent's turn signal in the chat | `round_step()` iterates over factions |

### Multi-agent fan-out

- **RoundSteppedFlow** drives N Pipelines (one per faction), each with its own
  Event Store + State Manager file. The cycle runs per faction; Phase 3
  iteration is sequential across factions within a round.
- **EventDrivenFlow** typically drives one Pipeline — the bot is a single
  faction among human players in the same Telegram chat. The cycle runs only
  for the bot's Pipeline.

### Not shown

| Concern | Where to find it |
|---|---|
| Per-phase message sequence (who sends what to whom) | Per-phase sequence diagrams in each drill-down below |
| Operator command interleaving during Phase 1 | Drill-down: inbound processing below |
| Extraction debounce / per-message cooldown | Drill-down: inbound processing below |
| Cost accountant per-round budget reset (happens at Phase 2 entry) | `ARCH_orchestrator.md` |

---

## Inbound processing

What happens to every message arriving at the agent, **per agent**. Covers both
game messages (from moderator + other factions) and operator input (tagged
coaching, INTEL corrections, slash commands).

```mermaid
flowchart TB
    T[Transport<br/>Telegram · CLI]
    P{{Pipeline<br/>process_event / dispatch_operator}}

    ES[(Event Store)]
    SM[(State Manager)]

    EXT[Extraction<br/>text → StatePatch]
    CP[Coaching Parser<br/>parse tags + commands]
    CMD[Command handler<br/>/preview · /status · /ledger · /state<br/>/approve · /edit · /revise · /block · …]

    T -->|InboundEvent| P

    P -->|game message<br/>append| ES
    P ==>|game message<br/>debounced · per-message cooldown| EXT
    P -->|operator input| CP

    CP -->|INTEL: tag<br/>intel_correction trigger| EXT
    CP -->|PRIORITY · CONSTRAINT · TONE<br/>WATCH · untagged<br/>store as unconsumed coaching| SM
    CP -->|slash command| CMD

    EXT -->|StatePatch + audit| SM

    click EXT "ARCH_extraction.md" "Extraction module"
    click CP "ARCH_coaching.md" "Coaching module"
    click CMD "ARCH_review_gate.md" "Review-gate commands handled via Pipeline.dispatch_operator"
    click ES "ARCH_event_store.md" "Event Store"
    click SM "ARCH_state_manager.md" "State Manager"
```

### What this view shows

- **Two destinations for every game message** (fan-out at Pipeline): append to
  Event Store *and* schedule Extraction. Both happen for the same inbound.
- **Debounce on game-message Extraction.** Per-message cooldown: each new game
  message cancels the pending extraction task and replaces it. Extraction
  runs once per burst, not once per message. Bold edge marks the debounced
  path.
- **Operator input is parsed by tag**, three destinations:
  - `INTEL: …` routes to Extraction with the `intel_correction` trigger (no
    debounce — operator intent is treated as direct).
  - Other tags + untagged text → stored as unconsumed coaching on State
    Manager, awaiting the next Phase 3 (Context Assembler reads it).
  - Slash commands → command handler. Review-gate commands (`/approve`,
    `/edit`, `/revise`, `/block`) route through `Pipeline.dispatch_operator`
    → `ReviewGate.handle_command` and are how Phase 3 advances.
- **Asymmetric Event Store write:** game messages append; operator messages
  do not. The Event Store is a game-state log, not an audit of operator
  interaction (operator interactions show up in State Manager via coaching
  table and edit-log instead).

### Sequence

Time order for one representative round opener: a game message, a `PRIORITY:`
tag, an `INTEL:` correction, and a `/status` command.

```mermaid
sequenceDiagram
    autonumber
    participant G as Game source<br/>(moderator/faction)
    participant Op as Operator
    participant T as Transport
    participant P as Pipeline
    participant CP as Coaching Parser
    participant EXT as Extraction
    participant ES as Event Store
    participant SM as State Manager

    G->>T: game message
    T->>P: InboundEvent (game)
    P->>ES: append event
    P->>EXT: schedule extraction (debounced)
    EXT->>SM: apply StatePatch

    Op->>T: PRIORITY: focus on X
    T->>P: InboundEvent (operator)
    P->>CP: parse
    CP->>SM: store unconsumed coaching

    Op->>T: INTEL: Y is bluffing
    T->>P: InboundEvent (operator)
    P->>CP: parse
    CP->>EXT: trigger intel_correction
    EXT->>SM: apply StatePatch

    Op->>T: /status
    T->>P: InboundEvent (operator)
    P->>CP: parse
    Note over CP: dispatch slash command
```

### Not shown

| Concern | Where to find it |
|---|---|
| Extraction's JSON schema enforcement + retry | `ARCH_extraction.md` |
| Cost accountant budget gating on the Extraction LLM call | `ARCHITECTURE.md` § Coupling Notes — `DiplomatCostGate` |
| How Flow drives `Transport.listen()` vs. `round_step()` | Lifecycle above — trigger-differences table |
| What "unconsumed coaching" looks like once accumulated | Response pipeline below — Context Assembler input |
| Edit Classifier post-hook (fires when `/edit` completes) | `ARCH_edit_classifier.md` |
| Coaching Parser is a toolkit primitive (`toolkit.coaching`) | `ARCHITECTURE.md` § Implementation Sequence |

---

## Round boundary

What runs between rounds, **per agent**. Triggered by `Pipeline.advance_to_round(N+1)`
(triggers per Flow — see Lifecycle's trigger-differences table above).

```mermaid
flowchart TB
    P["Pipeline<br/>advance_to_round N+1<br/>reset per-round budget"]
    REC["Reconciliation<br/>dedup · fulfill · flag · catch-missed"]

    subgraph parallel["Both analysts dispatched in parallel"]
        direction LR
        A1[Analyst Primary]
        A2[Analyst Secondary]
    end

    DIV["Divergence<br/>compare · pure-Python · no LLM"]

    SM[(State Manager)]
    ES[(Event Store)]

    P --> REC
    REC ==>|sequential gate<br/>edits committed first| parallel
    parallel --> DIV

    SM <-->|state read · edits written| REC
    SM -.->|full state| A1
    SM -.->|full state| A2
    ES -.->|recent transcript| A1
    ES -.->|recent transcript| A2
    DIV -.->|intel + divergences stored| SM

    click REC "ARCH_reconciliation.md" "Reconciliation module"
    click A1 "ARCH_analyst.md" "Analyst module"
    click A2 "ARCH_analyst.md" "Analyst module (Secondary)"
    click DIV "ARCH_analyst.md" "Divergence (in Analyst module)"
    click SM "ARCH_state_manager.md" "State Manager"
    click ES "ARCH_event_store.md" "Event Store"
```

### What this view shows

- **Sequential gate before the parallel fan-out.** Reconciliation completes
  and commits its edits to State Manager *before* either Analyst starts, so
  both Analysts read post-reconciled state. Bold edge marks the gate.
- **Two Analysts dispatched in parallel.** Same inputs (full state + recent
  transcript), different LLM providers. The duality is what makes Divergence
  meaningful — it's a cross-provider sanity check on intel quality.
- **Divergence is pure-Python.** No LLM call, no toolkit dependency. It
  compares the two `AnalysisResult` objects against configurable thresholds
  and emits a `List[Divergence]`.
- **Per-round budget reset happens here**, at boundary entry, before any LLM
  call. A round-blowing call in the previous round does not leak into the
  next round's budget.

### Sequence

Time order between rounds. Shows the sequential gate (Reconciliation commits
edits before Analysts read) and the parallel analyst dispatch.

```mermaid
sequenceDiagram
    autonumber
    participant P as Pipeline
    participant REC as Reconciliation
    participant A1 as Analyst Primary
    participant A2 as Analyst Secondary
    participant DIV as Divergence
    participant ES as Event Store
    participant SM as State Manager

    Note over P: round trigger (per Flow)
    P->>P: advance_to_round(N+1)<br/>reset per-round budget
    P->>REC: reconcile
    REC->>SM: read state
    REC->>SM: write edits (dedup / fulfill / flag)

    par Both analysts dispatched in parallel
        P->>A1: analyze
        A1->>SM: read full state
        A1->>ES: read recent transcript
        A1-->>P: AnalysisResult (primary)
    and
        P->>A2: analyze
        A2->>SM: read full state
        A2->>ES: read recent transcript
        A2-->>P: AnalysisResult (secondary)
    end

    P->>DIV: compare(primary, secondary)
    DIV-->>P: List[Divergence]
    P->>SM: store intelligence (both + divergences)
```

### Not shown

| Concern | Where to find it |
|---|---|
| Per-call cost-accountant budget gating (every LLM call is checked against `available_budget()`) | `ARCHITECTURE.md` § Coupling Notes — `DiplomatCostGate` |
| Divergence thresholds (configurable in `pipeline.yaml`) | `ARCH_analyst.md` |
| Reconciliation prompt structure + categories of edits | `ARCH_reconciliation.md` |
| How the round signal is detected (per-Flow) | Lifecycle above — trigger-differences table |
| What Phase 3 does with the stored intel | Response pipeline below |
| Reconciliation factory wiring (`build_reconciler`) | `ARCHITECTURE.md` § Coupling Notes |

---

## Response pipeline

How a faction produces one outbound message. Triggered after the round boundary
has populated intelligence + reconciled state, on the agent's own turn.

```mermaid
flowchart LR
    subgraph upstream["Upstream — already populated"]
        direction TB
        PER[Persona<br/>faction_prompt.txt]
        SM[(State Manager<br/>intel · divergences<br/>· unconsumed coaching)]
        ES[(Event Store<br/>recent transcript)]
    end

    CA[Context<br/>Assembler]
    GEN[Generation]
    ADV[Adversarial<br/>skippable]
    RG{Review Gate}
    T[Transport<br/>→ moderator]
    X[dropped]

    PER -->|base_prompt<br/>+ round_context| CA
    SM -->|intel + coaching| CA
    ES -->|recent events| CA

    CA -->|DecisionContext| GEN
    GEN -->|draft| ADV
    GEN -->|draft + reasoning| RG
    ADV -->|trap analysis| RG

    RG ==>|/approve · /edit| T
    RG -->|/revise: directive<br/>capped at 3| GEN
    RG -.->|/block| X

    click PER "ARCH_persona.md" "Persona module"
    click CA "ARCH_context_assembler.md" "Context Assembler module"
    click GEN "ARCH_generation.md" "Generation module"
    click ADV "ARCH_adversarial.md" "Adversarial module"
    click RG "ARCH_review_gate.md" "Review Gate module"
```

### What this view shows

- **Context assembly is fan-in.** Persona + intel + coaching + recent transcript
  flow into Context Assembler, which produces a single `DecisionContext`. Context
  Assembler is the only module that knows the shape of the Generation prompt.
- **Adversarial is skippable but parallel.** When enabled, Adversarial reads the
  same draft as Review Gate and sends trap analysis alongside. When disabled,
  draft goes straight to Review Gate.
- **Four review outcomes:** `/approve` and `/edit` send to Transport (bold edge).
  `/revise: <directive>` loops back to Generation with the operator's directive,
  capped at 3 per review. `/block` drops the draft.

### Sequence

Time order for one turn, including all four review outcomes.

```mermaid
sequenceDiagram
    autonumber
    participant P as Pipeline
    participant CA as Context Assembler
    participant SM as State Manager<br/>+ Event Store<br/>+ Persona file
    participant GEN as Generation
    participant ADV as Adversarial
    participant RG as Review Gate
    participant T as Transport
    participant Op as Operator
    participant Mod as Moderator

    Note over P: agent's turn trigger
    P->>CA: assemble context
    CA->>SM: persona + intel + coaching<br/>+ recent transcript
    CA-->>P: DecisionContext
    P->>GEN: generate
    GEN-->>P: draft + reasoning

    opt adversarial enabled
        P->>ADV: read draft
        ADV-->>P: trap analysis
    end

    P->>RG: submit(draft, adversarial)
    RG->>T: send to operator (coaching channel)
    T->>Op: review prompt

    alt /approve or /edit
        Op->>T: /approve (or /edit: ...)
        T->>RG: command
        RG-->>P: decision (approved text)
        P->>T: send final response
        T->>Mod: posted
        P->>SM: mark coaching consumed
    else /revise: directive
        Op->>T: /revise: directive
        T->>RG: command
        RG-->>P: regenerate with directive (capped at 3)
        Note over P: loop back to GEN
    else /block
        Op->>T: /block
        T->>RG: command
        RG-->>P: decision (dropped)
        Note over P: nothing posted
    end
```

### Not shown

| Concern | Where to find it |
|---|---|
| Edit Classifier post-hook (each `/edit` is LLM-classified into six categories and stored) | `ARCH_edit_classifier.md` |
| Review Gate lazy-fetch (reasoning + adversarial fetched on demand to keep coaching messages short) | `ARCH_review_gate.md` |
| `toolkit/structured_llm` + `cost_accountant` — every LLM call goes through them | Overview diagram above |
| How intel + coaching get into State Manager in the first place | Drill-down: round boundary above |

---

## Drill-downs

Each drill-down combines a structural flowchart with a sequence diagram for that phase:

- [x] Inbound processing path (Transport → Event Store + Extraction → State Manager)
- [x] Operator coaching path (Coaching Parser routing + INTEL → Extraction split) — *covered by Inbound processing*
- [x] Round boundary (Reconciliation + dual Analyst + Divergence)
- [x] Response pipeline (Persona + Context Assembler → Generation → Adversarial → Review Gate)
- [x] Per-phase sequence diagrams (Listening / Round boundary / Generate+review) — *embedded in each drill-down above*
