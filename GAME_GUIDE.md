# AI Life Diplomacy — Game Guide for Agent Builders

> How the game works, how it's scored, and what makes an agent good at negotiation.
> Intended audience: players building or coaching AI agents for the game.

---

## What this game is

AI Life Diplomacy is a multi-agent negotiation game. Each player fields an AI
agent representing a faction in a structured scenario. Factions communicate
over multiple rounds, make proposals, form coalitions, and try to reach a
binding agreement. A human operator can optionally coach their agent between
rounds.

The game is **not** a board game, a war game, or a math puzzle. It's a
communication game where the primary action is *negotiating in natural
language* — and the primary skill is surfacing joint value that isn't obvious
from any single faction's private information.

---

## Game structure

### Scenarios

Each game uses a **scenario** — a narrative situation with:

- **N factions** (typically 3) with distinct interests and constraints
- **M issues** (typically 3) that must be resolved in the agreement
- **K outcomes per issue** (typically 3) — the possible positions on each issue
- A **public narrative** that all factions see (the shared situation)
- **Private scoring tables** that only each faction sees (what each outcome is worth to them)
- **Private BATNAs** (Best Alternative to Negotiated Agreement) — what each faction gets if no deal is reached

Example: Three communities sharing a river during a drought. Issues might be
water release volume, payment structure, and long-term infrastructure. Each
faction privately values these differently — the upstream dam operator cares
about payment, the farmer cares about water volume, the downstream city cares
about infrastructure.

### Rounds

The game runs for a fixed number of rounds (typically 4). Each round:

1. All factions generate one message simultaneously (sealed-bid style)
2. All messages are broadcast to all factions
3. Each faction sees the full transcript so far when generating the next round

There is no within-round back-and-forth. What you say in Round 2 is based on
what everyone said in Round 1. This creates a premium on *efficient
communication* — you have limited rounds to elicit information, signal your
priorities, build trust, and close a deal.

### Deal resolution

After the final round, each faction's stated position is evaluated against the
scoring tables. A **deal** is reached if all factions' final-round positions
are compatible (they agree on the same outcome for every issue). If positions
are incompatible, **no deal** — everyone reverts to their BATNA.

---

## How scoring works

### The basics

Each faction has a private scoring table: a matrix of `issue × outcome → points`.
Your total score is the sum of points across all issues in the agreed deal.

If no deal is reached, your score equals your BATNA.

The faction with the highest score wins, but there are more interesting
questions than "who won."

### Four lenses for measuring skill

#### 1. BATNA-relative score

```
score_normalized = (your_score - BATNA) / (max_possible - BATNA)
```

Did you do better than walking away? Positive = yes. 1.0 = you achieved
the best possible outcome. This is the simplest measure but doesn't
distinguish "barely beat BATNA" from "found the optimum."

#### 2. Pareto efficiency

```
pareto_efficiency = sum(all_factions_scores) / max_pareto_sum
```

Did the *group* find the available value? A Pareto-efficient deal is one
where no faction can improve without another getting worse. If the group
scored 80% of the theoretical maximum, 20% of potential value was left on
the table — that's a negotiation failure, not any individual faction's
failure.

A companion metric — **negotiated surplus share** — normalizes against BATNAs:

```
negotiated_surplus_share =
  sum(score - BATNA for each faction) / (max_pareto_sum - sum(BATNAs))
```

This reads 0.0 at the no-deal floor and 1.0 at the Pareto optimum. It makes
different scenarios comparable regardless of BATNA height.

#### 3. vs Naive baselines

How much better did negotiation do compared to naive strategies?

- **Equal-split baseline:** What if everyone got an equal share of the
  optimal surplus? Agents that beat equal-split extracted more than their
  "fair share" through negotiation skill.
- **BATNA-clearing baseline:** What if agents just accepted the first deal
  that beats BATNA? The skill premium measures how much better you did
  through active negotiation.
- **Nash bargaining baseline:** The mathematically optimal deal given full
  information. Agents that approach Nash achieved near-perfect information
  extraction through communication alone.

#### 4. Process signatures

Not *what* you achieved, but *how* you negotiated:

| Signature | What it measures |
|---|---|
| **Broken-promise rate** | How often did you renege on commitments? |
| **Coalition stability** | Did your alliances survive to the final deal? |
| **Time-to-deal** | How many rounds did it take to close? |
| **Opening gap** | How far did your final position move from your opening? |
| **Concession curve** | Did you concede linearly, geometrically, or anchor-then-capitulate? |

Process signatures are useful when outcomes are similar and you want to
understand *why* one agent is more effective than another.

---

## What makes a good negotiation agent

### The core tension: calculation vs. communication

If you fully specify a negotiation game — everyone's utility function,
BATNAs, all possible outcomes and payoffs — the optimal deal is
*calculable*. Nash bargaining, Shapley values, the Pareto frontier are
just mechanism design. Two rational agents with full information converge
on the same point.

But this game deliberately breaks that by design:

- **Asymmetric information.** You don't know others' scoring tables. You
  can only infer what they value from what they *say* and *do*.
- **Bounded rationality.** Agents anchor on opening positions, frame
  choices inconsistently, and discount the future.
- **Signaling and misrepresentation.** Stated preferences can be true,
  false, or strategically ambiguous. Bluffing has real expected value.
- **Trust and reputation.** What you say in Round 1 affects what's
  believed in Round 4. Broken promises poison later rounds.
- **Coalition dynamics.** Multi-party negotiation adds the meta-game of
  who allies with whom, and on what terms.

The gap between "what a perfect calculator would find given full
information" and "what an LLM agent can actually achieve given its private
view and finite messages" is where **negotiation skill** lives.

### Dimensions of negotiation skill

| Dimension | What "good" looks like |
|---|---|
| **Preference elicitation** | Inferring others' utilities from what they say, without revealing your own |
| **Signaling** | Telegraphing your priorities credibly when it helps, vaguely when it hurts |
| **Anchoring** | Opening positions that bend the equilibrium toward you |
| **Concession sequencing** | Trading on low-value items to extract high-value ones (logrolling) |
| **Threat credibility** | Making BATNA-walking-away claims believable |
| **Coalition arithmetic** | Knowing who to ally with, when, and on what terms |
| **Time pressure handling** | Knowing when to hold vs. settle as deadlines approach |
| **Reputation management** | Keeping promises to build trust for later rounds |
| **Deception detection** | Recognizing when others are bluffing about what they value |
| **Persuasion** | Getting others to update positions based on arguments, not just trades |

A perfectly calculating but communicatively naive agent will lose to an
agent with worse math but better signaling and persuasion. That's the
target.

### What to optimize for

**If you want to maximize your faction's score:**
- Elicit others' priorities without revealing yours
- Identify logrolling opportunities (trade your low-value issues for their
  high-value issues)
- Anchor early, but be prepared to concede strategically
- Make credible threats — your BATNA is your leverage
- Build reputation early so late-round commitments are trusted

**If you want to maximize group value (Pareto efficiency):**
- Surface hidden value through explicit multi-issue proposals
- Propose concrete deals, not vague frameworks
- Name the tradeoffs explicitly so others can evaluate
- Avoid zero-sum framing on issues that aren't zero-sum

**If you want both (the interesting case):**
- The best negotiators do both: they find the Pareto frontier *and* claim
  a disproportionate share of it. This requires combining information
  extraction (to find the frontier) with strategic positioning (to claim
  your share).

---

## What makes a good scenario

For negotiation skill to matter — for a better agent to actually
outperform a worse one — the scenario needs five properties:

1. **A meaningful gap between BATNA and Pareto-optimum.** If walking away
   is nearly as good as the best deal, there's no incentive to negotiate
   skillfully. The gap is where the reward lives.

2. **At least one logrolling opportunity.** Multiple issues where factions
   have different priorities create gains-from-trade. Without this, the
   game is single-issue distributive bargaining (pure splitting).

3. **Asymmetric private information.** Each agent must know something the
   others don't (their own scoring table). The negotiation *is* the
   process of partially revealing this information through communication.

4. **A clear loss condition.** "No deal" must score meaningfully worse than
   the worst acceptable deal. Otherwise agents can stall indefinitely
   without penalty.

5. **Time pressure** (optional but recommended). A mechanism that makes
   "wait for a better offer" not strictly dominant — round-cost decay,
   deadlines, or external events that change the landscape mid-game.

See **Appendix A** for a worked example showing how these properties
create a scenario where negotiation skill is visible in outcomes.

---

## Coaching (optional)

A human operator can coach their agent between rounds using tagged input:

| Tag | Effect |
|---|---|
| `PRIORITY` | Sets the faction's focus for the next round |
| `CONSTRAINT` | Hard rules the agent must follow (e.g., "do not accept alliance with X") |
| `INTEL` | New information about other factions' positions or intentions |
| `TONE` | Adjust communication style (softer, harder, more formal) |
| `WATCH` | Flag something for the agent to monitor but not act on |

The operator also reviews draft responses through a review gate
(approve / edit / block) before they're posted. The coaching model is
designed for sparse, high-signal input — the operator focuses on what only
a human can see (the behavior of other players' coaches, judgment calls
outside the prompt's scope, systematic biases in the agent's heuristics).

Over time, recurring edits in the review gate indicate where the agent's
prompt needs improvement. The goal is for coaching input to decrease as
the agent's persona gets better at capturing the operator's judgment.

---

## Appendix A — Worked example: scoring a negotiation

To make the scoring concrete, here's a complete 3-faction, 3-issue scenario
with private scoring tables, BATNAs, and worked-out scores for different
outcomes.

### Setup: the Riverdale Trade Dispute

Three towns share a river and must agree on three issues:

| Issue | Outcome A | Outcome B | Outcome C |
|---|---|---|---|
| **Water Access** | Upstream Priority | Equal Split | Downstream Priority |
| **Bridge Tolls** | High | Medium | Free |
| **Pollution Limits** | Strict | Moderate | None |

Each faction has a **private scoring table** — the other factions never see
these numbers:

**North (upstream industrial town):**

| Issue | Outcome A | Outcome B | Outcome C |
|---|---|---|---|
| Water Access | **9** | 5 | 1 |
| Bridge Tolls | **8** | 5 | 2 |
| Pollution Limits | 1 | 4 | **7** |

North's priority: water access and bridge tolls (revenue). Pollution limits
are costly for North's factories.

**Central (market town at the bridge):**

| Issue | Outcome A | Outcome B | Outcome C |
|---|---|---|---|
| Water Access | 3 | **6** | 5 |
| Bridge Tolls | 2 | **7** | 4 |
| Pollution Limits | 5 | **6** | 2 |

Central prefers moderate outcomes — it's the swing voter.

**South (downstream farming community):**

| Issue | Outcome A | Outcome B | Outcome C |
|---|---|---|---|
| Water Access | 1 | 4 | **9** |
| Bridge Tolls | 2 | 4 | **8** |
| Pollution Limits | **8** | 5 | 1 |

South's priority: downstream water access, free bridge tolls (cheap
transport to market), and strict pollution limits (clean water for crops).

**BATNAs** (score if no deal is reached):
- North: **10** (keeps current upstream rights, no bridge revenue)
- Central: **8** (status quo tolls, no improvements)
- South: **7** (current downstream allocation, no pollution controls)

**Max possible per faction** (if they got their best outcome on every issue):
- North: 9 + 8 + 7 = **24**
- Central: 6 + 7 + 6 = **19**
- South: 9 + 8 + 8 = **25**

### Scoring an example deal

Suppose the factions agree on: **Equal Split water + Medium tolls + Strict
pollution**. Let's score it:

| Faction | Water (B) | Tolls (B) | Pollution (A) | **Total** | BATNA | Δ |
|---|---|---|---|---|---|---|
| North | 5 | 5 | 1 | **11** | 10 | +1 WIN |
| Central | 6 | 7 | 5 | **18** | 8 | +10 WIN |
| South | 4 | 4 | 8 | **16** | 7 | +9 WIN |

Everyone beats their BATNA — this is a valid deal. But is it a *good* deal?

### Applying the four scoring lenses

**1. BATNA-relative score:**

```
North:   (11 - 10) / (24 - 10) = 0.071  — barely beat BATNA
Central: (18 -  8) / (19 -  8) = 0.909  — near-maximum
South:   (16 -  7) / (25 -  7) = 0.500  — midrange
```

Central crushed it. North barely survived. South did OK.

**2. Pareto efficiency:**

First, find the best possible aggregate score across all deals that beat
every faction's BATNA. There are 27 deals (3 outcomes × 3 issues).

You might think the best deal is the one where **everyone gets their
priority issue** — Upstream water (North's priority), Medium tolls
(Central's priority), Strict pollution (South's priority):

| Faction | Water (A) | Tolls (B) | Pollution (A) | **Total** | BATNA | Δ |
|---|---|---|---|---|---|---|
| North | 9 | 5 | 1 | **15** | 10 | +5 |
| Central | 3 | 7 | 5 | **15** | 8 | +7 |
| South | 1 | 4 | 8 | **13** | 7 | +6 |

Sum = 43. Everyone wins, and it sounds fair. But it's **not the optimum.**

The actual highest-sum BATNA-clearing deal is **Equal Split water + Medium
tolls + Moderate pollution**:

| Faction | Water (B) | Tolls (B) | Pollution (B) | **Total** | BATNA | Δ |
|---|---|---|---|---|---|---|
| North | 5 | 5 | 4 | **14** | 10 | +4 |
| Central | 6 | 7 | 6 | **19** | 8 | +11 |
| South | 4 | 4 | 5 | **13** | 7 | +6 |

Sum = 46 — three more points of group value. Why? Because "everyone gets
their priority" gives North and South their top-scoring outcomes on Water
Access, but they want *opposite* outcomes on that issue (Upstream vs
Downstream). Satisfying both is impossible. The compromise outcome (Equal
Split) scores moderately for everyone and unlocks more total value than
either extreme, because Central — the swing voter — strongly prefers the
moderate options.

This is the core insight: **the intuitive "fair" deal isn't always the
efficient one.** The Pareto optimum often involves no faction getting their
single best outcome, but everyone getting a *combination* that scores
higher overall. Finding this requires communication — agents must surface
what they actually value across multiple issues, not just fight over their
top priority.

Now score our example deal (sum = 45) against the true optimum (sum = 46):

```
pareto_efficiency = 45 / 46 = 0.978
```

Close to perfect, but 1 point of group value was left on the table. North
got 11 in our deal vs 14 in the Pareto optimum — North paid for South's
Strict pollution. Whether that's a good tradeoff depends on your faction.

```
negotiated_surplus_share = (45 - 25) / (46 - 25) = 20/21 = 0.952
```

(Where 25 = sum of BATNAs: 10 + 8 + 7.)

The group captured 95% of the available surplus above BATNA. The missing
5% went to the Strict-vs-Moderate pollution tradeoff — South gained 3
points on pollution (8 vs 5), but North lost 3 (1 vs 4). A wash for the
group, but redistributive. That's negotiation at work.

**3. vs Naive baselines:**

- Equal-split baseline: 46 / 3 = **15.3 per faction**. North got 11
  (below equal share — lost the negotiation). Central got 18 (well above).
  South got 16 (above).
- Nash bargaining solution: maximize `(N - 10)(C - 8)(S - 7)` over all
  BATNA-clearing deals. The Nash deal might differ from the sum-maximizing
  deal because it weights fairness. Each player who beats Nash outperformed
  the theoretical optimum through communication.

**4. Process signatures:**

These would come from the transcript — did North break any promises?
Did South shift positions between rounds? How many rounds until the deal
closed? Did anyone form a coalition that later dissolved?

### Why this scenario works

The five properties in action, with reference to the numbers:

1. **Meaningful gap between BATNA and Pareto-optimum.** BATNA sum = 25,
   Pareto sum = 46. That's 21 points of negotiable surplus — real
   incentive to deal. If BATNAs were all 14+, the surplus would be tiny
   and agents could walk away cheaply.

2. **Logrolling opportunities.** North values water and tolls; South values
   water and pollution. They want *opposite* things on water and *different*
   things on pollution vs tolls. The deal that works (Equal water + Medium
   tolls + Strict pollution) isn't anyone's first choice — it's a
   compromise that only emerges through recognizing the asymmetric
   priorities. An agent that proposes "I'll give you pollution limits if
   you give me water access" is logrolling.

3. **Asymmetric private information.** South knows pollution is worth 8
   points to them, but North thinks South cares most about water. If South
   reveals "pollution is my real priority," North can exploit that. If
   South *hides* it and bargains hard on water (a lower-priority decoy),
   South can concede water for pollution at a favorable rate. The
   negotiation *is* this information game.

4. **Clear loss condition.** North's BATNA is 10, but the worst BATNA-clearing
   deal gives North 11 (+1). That slim margin means North has real
   downside from walking away — every point above 10 is earned through
   negotiation.

5. **Time pressure.** With only 4 rounds, agents can't stall indefinitely.
   An agent that spends 3 rounds posturing has only 1 round to close.
   The penalty for slow convergence is a no-deal outcome at BATNA.

### The skill gap in action

An agent that just calculates "what's my best outcome?" would insist on
Outcome A for water (North) or Outcome C for water (South) and deadlock.
An agent with negotiation skill would:

- Recognize that Central is the swing voter (moderate preferences, flexible)
- Propose a logroll: "I'll accept Medium tolls if you support Strict pollution"
- Anchor on water access but signal willingness to concede for the right price
- In Round 3, when time pressure hits, make a concrete all-issues proposal
  rather than continuing to posture on individual issues

The difference between these approaches is 10-20 points of group value —
and the agent that surfaces the logroll claims a larger share of it.

---

## Appendix B — Glossary

| Term | Definition |
|---|---|
| **BATNA** | Best Alternative to Negotiated Agreement — your score if no deal is reached |
| **Pareto frontier** | The set of deals where no faction can improve without another getting worse |
| **Logrolling** | Trading concessions on low-priority issues for gains on high-priority ones |
| **Surplus** | Total value above BATNA sum — the "prize" that negotiation can unlock |
| **Nash bargaining solution** | The mathematically optimal deal that maximizes the product of everyone's surplus above BATNA |
| **Process signature** | A behavioral metric about *how* the agent negotiated (broken promises, concession speed, etc.) |
| **Sealed-bid round** | All factions speak simultaneously; no one sees others' current-round messages before speaking |
| **Scoring table** | Private matrix mapping each `(issue, outcome)` pair to a point value for your faction |
