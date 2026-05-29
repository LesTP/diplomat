# Multi-Party Negotiation Scenarios for AI Self-Play Simulation: A Sourced Catalogue

## TL;DR
- The richest, most directly scriptable multi-party scenarios fall into three tiers: (1) **structured academic role-plays** (Harvard PON/TNRC's Harborco, Three-Party Coalition, Chestnut Village, Abraham Path, World Trade Redevelopment) that already encode parties, interests, BATNAs, and in some cases exact point payoffs; (2) **historical diplomatic congresses** (Vienna 1814–15, Paris 1919, Camp David 1978, Dayton 1995, Good Friday 1998, Six-Party Talks, climate COPs, NAFTA) that supply real faction positions, leverage, and documented coalition shifts; and (3) **game-theoretic coalition templates** (weighted-voting/Shapley-Shubik games, characteristic-function coalition games, n-player public-goods/prisoner's-dilemma variants) that give clean numeric payoffs for AI agents.
- For immediate scripting, the **Harvard Three-Party Coalition Exercise** is the single best "drop-in" template: three organizations A, B, C, with confirmed coalition values v(AB)=118, v(AC)=84, v(BC)=50, v(ABC)=121, singletons=0 — every party can block any two-party deal, creating genuine coalition tension with a clean payoff matrix.
- The most dynamically interesting historical models for shifting alliances are the **Congress of Vienna** (Talleyrand splits the victorious "Big Four" by championing smaller powers) and the **Six-Party Talks** (a 4-vs-2 seating split where China is the indispensable broker), both of which feature a weaker party leveraging coalition dynamics against stronger ones.

## Key Findings

**1. Academic role-plays are the highest-value source** because they were purpose-built with confidential interests, scoring, and BATNAs — exactly the structural detail needed to script agent behavior. The Harvard Program on Negotiation's Teaching Negotiation Resource Center (TNRC) advertises "Over 250 negotiation exercises and role-play simulations" and is the definitive repository.

**2. Historical congresses provide the richest "shifting-alliance" narratives**, but require you to reconstruct payoffs. They are strongest on documented positions, leverage, and the actual coalition realignments that occurred.

**3. Game theory supplies the mathematical backbone.** Coalition-formation games, weighted-voting power indices, and n-player social dilemmas give you payoff functions you can plug directly into agent reward structures.

**4. Crisis/hostage and labor scenarios are inherently triadic** (perpetrator–authority–hostage; union–management–mediator), making them natural 3-party structures, though they have less coalition-building and more sequential bargaining.

---

## Details

### Category 1 — Historical Multi-Party Diplomatic Negotiations

#### Congress of Vienna (1814–1815) — the gold standard for shifting alliances
**Parties and positions:**
- **Austria (Metternich):** Preserve the multi-ethnic Habsburg Empire; suppress nationalist/liberal movements; balance of power; influence over Italy and the new German Confederation.
- **Russia (Tsar Alexander I, min. Nesselrode):** Wanted a Kingdom of Poland under his own scepter — his "primary demand," opposed by both Prussia and Austria. Combined liberal-mystical idealism with imperial expansion.
- **Prussia (Hardenberg, Humboldt):** Wanted to annex the Kingdom of Saxony (whose king had stayed loyal to Napoleon) and territorial compensation in the Rhineland.
- **Britain (Castlereagh):** "Insular" — wanted a continental balance so neither France nor Russia could dominate, protecting British maritime/commercial supremacy; opposed hegemony.
- **France (Talleyrand):** Defeated power that, through skillful maneuvering, inserted itself into the inner circle by championing the smaller powers and the principle of "legitimacy."

**Leverage & alliance shifts:** The four victors (Treaty of Chaumont, March 1814) initially excluded France. The decisive coalition shift: Russia and Prussia struck a deal (Prussia backs Russian Poland in exchange for Russian support for Prussia taking Saxony). In response, **Austria, Britain, and France signed a secret alliance on January 3, 1815, threatening war** to block the Russo-Prussian plan. Talleyrand's compromise (Russia gets most of Poland, Prussia gets part of Saxony plus Rhineland) resolved it. This is the textbook case of a defeated/weak party (France) using coalition realignment to regain great-power status.
**Why it's interesting for self-play:** Two-tier structure (the "Four"/"Five"/"Eight" committees vs. 200+ excluded delegations), a weak party with a strong BATNA-creation strategy, and a genuine war-threat blocking coalition.

#### Paris Peace Conference / Versailles (1919) — the "Big Four"
**Parties:**
- **France (Clemenceau, "The Tiger"):** Harsh terms — maximum reparations, return of Alsace-Lorraine, German war guilt, security against future invasion, a weakened Germany.
- **Britain (Lloyd George):** More moderate — balance of power, Germany retained as a trading partner/economic engine, protection of the British Empire's unity (e.g., sacrificed the Japanese Racial Equality Proposal to placate Australia).
- **USA (Wilson):** The Fourteen Points — League of Nations, self-determination, no punitive Article 231; opposed secret treaties and Italian Adriatic claims.
- **Italy (Orlando):** Weakest of the four; demanded fulfillment of the secret 1915 Treaty of London (Trento, Tyrol, Trieste, Istria, Dalmatia). Clashed with Wilson over Dalmatia and **walked out of the conference**.

**Leverage/dynamics:** US economic leverage and Wilson's idealism vs. Anglo-French victors' demands; Italy's weak position and dramatic exit; defeated powers excluded entirely. A good model for a "victors' coalition" with internal value-claiming conflict and one party (Italy) whose poor BATNA leads to a walkout.

#### Camp David (1978) — trilateral mediation
**Parties:**
- **Egypt (Sadat):** Recover the Sinai; reorient toward Washington/NATO economic aid; wanted a broader framework addressing the Palestinian question to retain Arab legitimacy.
- **Israel (Begin, first Likud government):** Strategic depth, security, international legitimacy; willing to trade Sinai land for binding peace; refused commitments on the West Bank; insisted the PLO be excluded.
- **USA (Carter, mediator):** Wanted a comprehensive "land for peace" deal; used the "single-document" shuttle method.

**Key structural feature for scripting:** After three days the Sadat–Begin relationship broke down so completely that **the two principals never met face-to-face for the remaining ~10 days**; Carter shuttled a single negotiating text between separate cabins. The Jimmy Carter Library confirms the single text "went through 23 drafts," and Carter recalled: "For the first three days, I attempted to have Begin and Sadat come together... So for the next 10 days, they never saw each other." This is a model of **mediated indirect negotiation** where the third party controls the single negotiating text. Leverage points: a US oil-supply guarantee to Israel, plus US aid to both — per State Department/CRS figures and History.com, the post-treaty informal 3:2 ratio set Israel at ~$3 billion/yr and Egypt at $1.3 billion/yr in military aid. Absent parties (Jordan's Hussein, Syria's Assad, the PLO) refused to participate, shaping the outcome toward a separate peace.

#### Dayton Accords (1995) — proximity talks ending the Bosnian War
**Parties:** Serbia (Milošević), Croatia (Tuđman), Bosnia (Izetbegović), with the US (Holbrooke) as coercive mediator. The Bosnian Serbs were represented through Milošević, who sidelined them.
**Leverage:** NATO airstrikes as the BATNA-shaper; Holbrooke's "proximity" format (parties housed separately on an air base, media blackout); the simulated threat to walk out (planes revving). The final sticking point — the town of Brčko — was resolved only by deferring it to international arbitration. Good model for coercive mediation, ripe-moment timing, and last-minute concession dynamics.

#### Good Friday / Belfast Agreement (1998) — genuine multi-party
**Parties:** Eight Northern Ireland political parties (including the Ulster Unionists, SDLP, Sinn Féin, and the Northern Ireland Women's Coalition) plus the British and Irish governments, chaired by US Senator George Mitchell. The DUP opposed and walked out.
**Structure:** Three "strands" (internal NI governance; North-South cross-border; East-West UK-Ireland), power-sharing via d'Hondt allocation, "constructive ambiguity" in the text. Excellent for modeling a large multi-party table with cross-cutting cleavages (unionist/nationalist), spoilers, and an external chair.

#### Six-Party Talks (2003–2009) — North Korean nuclear program
**Parties & interests:**
- **North Korea:** Used nuclear weapons as leverage for economic aid, security guarantees, and regime survival; preferred bilateral talks with the US.
- **USA:** Verifiable denuclearization (CVID); insisted on multilateral format to deny NK bilateral leverage.
- **China (host/chair):** Feared regime collapse and refugee influx; reluctant to use its energy/food leverage; the indispensable broker.
- **South Korea:** Feared collapse/refugees; favored step-by-step engagement.
- **Japan:** Hard line on missiles plus the **abductees issue**, which complicated and sometimes blocked progress.
- **Russia:** Sought to reassert regional influence; generally aligned with China against harsh sanctions.

**Coalition structure:** A documented **4-vs-2 split** — in one simulation, participants seated the US, Japan, and South Korea on one side and Russia, China, and North Korea on the other. China and Russia favored a milder phased reward model; the Joint Statement of the Fourth Round (Beijing, 19 September 2005) codified this verbatim: "The Six Parties agreed to take coordinated steps to implement the aforementioned consensus in a phased manner in line with the principle of 'commitment for commitment, action for action.'" The US, Japan, and (by the second round) South Korea wanted full dismantlement first. This is an ideal template: six agents, an indispensable broker, embedded bilateral channels, and one party (Japan) with a side-issue that can derail consensus.

#### Climate negotiations (Kyoto/Copenhagen/Paris) — bloc politics
**Negotiating blocs (each a coalition agent):**
- **EU:** Pushed for ambitious, binding emissions cuts.
- **Umbrella Group** (US, Canada, Australia, Russia, Norway, Japan, etc.): Non-EU developed states, more reluctant.
- **G77+China:** Large developing-country bloc; emphasized CBDR (common but differentiated responsibilities) and climate finance.
- **BASIC** (Brazil, South Africa, India, China): Formed at Copenhagen 2009; negotiated the Copenhagen Accord directly with the US, breaking from the broader G77.
- **AOSIS** (small island states): Most vulnerable; pushed the 1.5°C target; frequently allied informally with the EU.
- **LDCs** (Least Developed Countries): At Copenhagen openly clashed with BASIC despite both being in G77.
- **ALBA** (Venezuela, Bolivia, Cuba, Ecuador): Radical bloc that helped block formalization of the Copenhagen Accord.
- **Like-Minded Developing Countries** (incl. oil producers Saudi Arabia, Venezuela): Resisted equal obligations.
- **High Ambition Coalition:** At Paris 2015, the EU + small islands + others; the US joined late to pressure China and India on transparency and 5-year ratchet cycles.

**Why it's the best large-N model:** Almost every country belongs to multiple blocs, blocs realign between summits, and the Copenhagen→Paris arc shows a coalition (High Ambition) deliberately assembled to isolate holdouts. Genuine free-rider/public-goods structure.

#### NAFTA / USMCA renegotiation — trilateral trade with bilateral fallback
**Parties:** US, Canada, Mexico. **Original NAFTA (1991–94):** Canada asked to join US-Mexico talks specifically to avoid being undercut by a separate US-Mexico deal. Agriculture was so contentious it was **not negotiated trilaterally** — three separate bilateral agreements were signed; Canada refused to touch its dairy/poultry supply management.
**USMCA renegotiation (2017–2020):** The US made extreme opening demands (5-year sunset clause — a "nonstarter" for the others) and threatened to split into separate bilateral deals (the classic "divide and conquer" of the strongest party). Canada and Mexico reaffirmed trilateralism because **weaker parties gain strength through alliance**. Mexico conceded on autoworker wages; per the USTR fact sheet, the USMCA "uses trade rules to drive higher wages by requiring that 40-45 percent of auto content be made by workers earning at least $16 per hour." The US dropped the sunset clause. Excellent model of a strong party trying to fragment a coalition of two weaker parties.

#### WTO Doha Round — large-N trade deadlock
**Key groupings:** The **G-6** (US, EU, Brazil, India, Australia, Japan) reached the 2006 impasse. The talks collapsed in July 2008 when the US and India could not agree on a "special safeguard mechanism" letting developing countries raise tariffs on import surges. The **G-20 developing bloc** (Brazil, India, China) sought agricultural subsidy/tariff cuts from developed states while protecting their own. Good model of cross-cutting coalitions where the "development" framing entices participation but core agricultural interests deadlock.

### Category 2 — Structured Academic / Business Case Studies (PON / TNRC)

These are the most directly usable because they ship with confidential role instructions, defined interests, and BATNA/scoring data. The TNRC advertises "Over 250 negotiation exercises and role-play simulations," searchable by number of parties.

#### Harborco (six-party, scoreable) — the flagship coalition simulation
**Scenario:** A consortium ("Harborco") wants to build a deep-water port but needs a license from the Federal Licensing Agency, which will grant it **only if Harborco secures the support of at least 4 of the 5 other parties.**
**Parties and max achievable scores:** Harborco (max 77), Environmental League (100), Unions (90), Other Ports (64), Federal Dept. of Coastal Resources/DCR (100), Governor (77).
**Issues:** industry mix, environmental mitigation, role of organized labor, federal financial assistance, and compensation to other ports for economic losses.
**Coalition dynamics:** Pro-port parties (Unions want jobs; Governor wants development) vs. blockers (Environmental League opposes coastal development; Other Ports fear competition and may form a blocking coalition). The "4-of-5" rule is a built-in winning-coalition threshold — ideal for AI self-play. Joint gains are possible because parties weight the issues differently (integrative potential).

#### Three-Party Coalition Exercise (Susskind) — the cleanest payoff template
**Scenario:** Three organizations A, B, C negotiate over forming a 2- or 3-party coalition. **Confirmed payoff schedule (characteristic function):**
- v(A) = v(B) = v(C) = 0 (any party alone gets nothing)
- v(A+B) = 118
- v(A+C) = 84
- v(B+C) = 50
- v(A+B+C) = 121

Only one agreement is possible — either a three-way split of 121 or a single two-party coalition (leaving the third with zero); any division within a coalition is negotiable. (These values are confirmed by two independent reproductions of the actual role-instruction sheets, plus the official PON and Susskind/MIT pages confirming the 121 total.)
**Why it's perfect for AI self-play:** Asset-power ranks A>B>C, but **every party can block any two-party coalition and each has an equally bad BATNA (walking away with 0)**, so "weak" C has real leverage. The grand coalition (121) is barely larger than the AB coalition (118), creating intense tension over whether to include C at all and how to split. This maps directly onto cooperative-game reward structures. Related PON exercises with the same mathematical structure: **The Parking Facility Venture, Rushing River Cleanup, and Social Services: A Three-Party Exercise** (the latter adds an optional fourth-party mediator).

#### Chestnut Village (multi-party, multi-issue)
3–4 construction-company representatives vs. 5–6 neighborhood representatives over safety and nuisance complaints; **internal team negotiations precede external negotiations** — a two-level game ideal for modeling intra-coalition coordination before inter-coalition bargaining.

#### Abraham Path (six-party, non-scoreable)
The Abraham Path Initiative (an NGO) plus four local Middle East partner organizations plus a filmmaker negotiate a 1,000-mile cross-border trail. Teaches coalition formation, spoiler management, and the role of values/public perception.

#### World Trade Redevelopment (six-party, facilitated)
Inspired by the real rebuilding of the WTC site; illustrates value creation vs. value distribution tension and how emotional issues intertwine with public-policy questions.

#### Great Negotiator case studies (factual, multi-party)
PON's Great Negotiator series includes Tommy Koh (US-Singapore FTA — "complex multi-party negotiations across multiple fronts"), Stuart Eizenstat (Holocaust reparations — "facilitating negotiations among multiple governments and industries"), Lakhdar Brahimi (forming a new Afghan government), and Christiana Figueres (leading the UNFCCC Secretariat to the Paris Agreement — a three-part case). These give real multi-stakeholder structure.

#### Other relevant TNRC items
Data Center Negotiation (eight-party, multi-issue, new); DONS Negotiation (four-person); Win As Much As You Can (four-person iterated prisoner's dilemma); Oil Pricing Exercise (two-team prisoner's-dilemma-style).

### Category 3 — Game-Theoretic Coalition / Bargaining Templates

#### Characteristic-function coalition games
Define a value v(S) for every coalition S. Solution concepts that give AI agents target payoffs: **the core** (no coalition can profitably deviate), the **Shapley value** (average marginal contribution across all orderings), the **nucleolus** (minimizes maximum dissatisfaction), and the **bargaining set**. The Three-Party Coalition Exercise above is a ready-made example. Experimental work (continuous-time three-player bargaining) finds **minimum-winning coalitions and uneven divisions are common, but the most stable outcome is the three-way equal split**, and players punish partners who defect from "loyal" coalitions — useful behavioral priors for agents.

#### Weighted-voting games & power indices
A game [q; w1, w2, …, wn] with quota q and weights w. Example [8: 7, 6, 2]: Shapley-Shubik power = (0.67, 0.33, 0) — the third player is a **dummy** (never pivotal) despite having weight. This captures the counterintuitive truth that raw resources ≠ bargaining power. The **Shapley-Shubik index** (fraction of orderings in which a player is pivotal) and **Banzhaf index** (swing-voter counts) let you assign each agent an a-priori power score. Applied historically to the UN Security Council and EU Council. Note [8: 7,6,2] gives the two largest players all the power even though the third holds 2 votes — a clean illustration for scripting "apparent vs. real" leverage.

#### N-player social dilemmas (public goods / multiplayer PD)
The **public-goods game** is the canonical n-player prisoner's dilemma: each agent chooses how much to contribute to a common pool; defection (free-riding) dominates individually but universal cooperation is collectively optimal. Variants include the **hierarchical public-goods game** (groups compete for resources while individuals within groups choose whether to pay "tax" — a two-level dilemma directly analogous to coalitions of states whose members can defect) and **zero-determinant / Tit-for-Tat / Win-Stay-Lose-Shift** strategies that sustain cooperation in repeated multiplayer dilemmas. These map cleanly onto climate-negotiation free-riding.

#### Sequential coalition-formation bargaining
Models (Bloch; Ray-Vohra; Baron-Ferejohn-style demand bargaining) where a proposer is recognized, proposes a coalition and a surplus split, and others accept or reject. With externalities, use a **partition function** (a coalition's value depends on how outsiders are organized) rather than a characteristic function — important when modeling that the value of an alliance depends on rival alliances.

### Category 4 — Crisis Negotiation Scenarios (3+ parties)

#### Hostage/barricade structure (inherently triadic)
The core triad is **hostage-taker → authorities (negotiator) → the hostage(s)**, plus often a fourth "target" third party (government/company) from whom the demand is actually extracted. Key dynamics for scripting: the hostage-taker's true target is not the hostage but the third party who can grant demands; quid-pro-quo bargaining (never concede without getting something — e.g., food for a released hostage); buying time to lower emotion. The FBI's **HOBAS** (Hostage Barricade Database System) is a real repository of scenario seeds — the FBI's Crisis Negotiation Unit states "There are currently over 5,000 incidents in HOBAS, contributed by law enforcement agencies in the U.S. and Canada," while peer-reviewed analyses cite larger pulls (Neller et al. analyzed "7,216 hostage and barricade incidents that had been reported to the Federal Bureau of Investigation over a 35-year period," 1982–2023). The FBI's CNU also maintains role-play scenarios in three categories (family/domestic, workplace, suicide). Multi-party complexity arises with negotiation teams, tactical units, and media as competing voices.

#### Labor disputes (union–management–mediator)
Triadic by design: union and management state opening demands, and if they stall, an **impartial third party** enters as either a **mediator** (recommends) or **arbitrator** (imposes binding terms). The US Federal Mediation and Conciliation Service and Federal Service Impasses Panel are real third-party institutions. Academic three-party models add a **government/social mediator** as a third agent to reach win-win outcomes. The PBS labor/management simulation ships with demand sheets for each side. Good for modeling a 3-party game where the third party's role (facilitator vs. imposer) changes the payoff structure.

#### Territorial disputes
Covered above under Dayton (Brčko arbitration), Vienna (Saxony/Poland), and Camp David (Sinai/West Bank) — all feature territory as the indivisible stake that forces creative splitting (arbitration, demilitarization, phased withdrawal).

### Category 5 — Scenario Repositories

- **Harvard PON Teaching Negotiation Resource Center (TNRC):** "Over 250 negotiation exercises and role-play simulations," searchable by number of parties, time, and concept; downloadable Teacher's Package samples; All-In-One Curriculum Packages. The single best repository for structured multi-party cases. (casestudies.law.harvard.edu and pon.harvard.edu/shop)
- **Lawrence Susskind / MIT** materials (consensus-building, public-dispute simulations).
- **FBI HOBAS** (Hostage Barricade Database System) — 5,000+ catalogued incidents (peer-reviewed pulls cite 7,216 over 1982–2023).
- **US State Department Office of the Historian / National Museum of American Diplomacy** — primary-source accounts of Camp David, Dayton, Paris.
- **Columbia International Affairs Online (CIAO)** — case studies including "The Camp David Accords: A Case of International Bargaining" and "Two-Level Bargaining: The NAFTA Negotiation."
- **DiploFoundation (diplomacy.edu)** — analyses such as Paul Meerts on persuasion at the Congress of Vienna.
- **UNFCCC bloc trackers** (Carbon Brief's interactive negotiating-alliances map; Climate Policy Info Hub) — for climate coalition structures.

---

## Recommendations

**Stage 1 — Prototype with clean game-theoretic templates (week 1).** Start with the **Three-Party Coalition Exercise** (v(AB)=118, v(AC)=84, v(BC)=50, v(ABC)=121, singletons=0). It is the minimal viable multi-party game with genuine coalition tension and exact payoffs, letting you validate that your agents (a) form winning coalitions, (b) recognize that weak parties hold blocking power, and (c) negotiate splits. Benchmark: do agents discover that A's apparent dominance doesn't guarantee inclusion, and that the grand coalition's tiny premium (121 vs. 118) makes excluding C tempting? Add a weighted-voting layer ([8:7,6,2]) to test whether agents detect dummy players.

**Stage 2 — Add structured role-play richness (weeks 2–4).** Port **Harborco** (six parties, a 4-of-5 winning-coalition threshold, integrative multi-issue trades) to test blocking coalitions and issue-linkage. Then **Chestnut Village** to test two-level (intra-team then inter-team) negotiation. These supply defined interests and scoring you can convert to reward functions.

**Stage 3 — Layer in historical narrative scenarios for qualitative richness (weeks 4+).** Script the **Six-Party Talks** (best for an indispensable-broker + side-issue-spoiler structure), the **Congress of Vienna** (best for a weak party using realignment to break a strong coalition), and the **climate COP blocs** (best for large-N, multi-bloc, free-rider dynamics with documented realignment from Copenhagen to Paris). For these, you must hand-author payoff matrices from the documented positions, since history gives you positions and leverage but not numbers.

**Thresholds that should change your approach:**
- If agents collapse to trivial equal splits in every game, **increase payoff asymmetry** (widen the gap between v(AB) and v(BC)) and add **externalities via partition functions** so a coalition's value depends on rivals' groupings.
- If agents never form blocking coalitions, **add a winning-coalition threshold** (like Harborco's 4-of-5) so blocking is mechanically possible.
- If you need spoiler/walkout behavior, seed scenarios with a party that has a strong outside option (Italy at Paris, the DUP at Good Friday) or an unrelated side-demand (Japan's abductees issue).

**Sourcing priority:** Purchase or download the TNRC Teacher's Package samples for Harborco, Three-Party Coalition, and Chestnut Village — they contain the confidential role instructions and exact scoring you cannot fully reconstruct from secondary descriptions.

## Caveats

- **Confidential scoring is paywalled.** PON/TNRC role-play point allocations (beyond the maxima and the Three-Party Coalition values confirmed here) are sold to instructors; secondary sources give structure but not every number. The Three-Party Coalition payoffs (118/84/50/121) come from two independent student reproductions plus official PON/MIT confirmation of the 121 total, and are reliable, but other simulations' internal point splits should be verified against purchased Teacher's Packages.
- **Historical payoffs are reconstructions.** History supplies positions, leverage, and the alliances that actually formed, but not cardinal utilities. Any reward matrix you build for Vienna, Paris, Camp David, etc., is an interpretive model, not a documented fact — which is acceptable given your stated priority of dynamic richness over historical accuracy.
- **Some sources are tertiary or speculative.** Several climate-bloc and historical descriptions come from encyclopedic or secondary outlets; bloc memberships shift between summits and are sometimes characterized differently across sources. Treat bloc lists as approximate and time-dependent.
- **Crisis/hostage and labor scenarios have weaker coalition-building** than diplomatic congresses — they are more sequential and mediator-centric. Use them for triadic mediation dynamics, not for rich multi-coalition formation.
- **HOBAS counts differ by source:** the FBI cites "over 5,000 incidents," while a peer-reviewed analysis (Neller et al.) reports 7,216 over 1982–2023 — likely reflecting different cutoff dates and inclusion criteria; treat the count as 5,000–7,000+.
- **One conflicting characterization to note:** sources differ on China's pivotal importance in the Six-Party Talks — most call China the indispensable host/broker, but at least one analysis argues "the notion that China is extremely vital… is exaggerated." Model both framings to test robustness.