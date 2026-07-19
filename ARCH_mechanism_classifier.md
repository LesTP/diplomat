# ARCH — Mechanism Classifier

> **Contract for the mechanism classifier** (`PAPER_PLAN.md` §4.1) — an
> LLM-as-judge that labels each self-play game outcome by *failure mechanism*, so
> the three-mechanism "zero-lift" taxonomy (`PAPER_PLAN.md` §1) becomes systematic
> data instead of hand-inspected anecdote. This is a **Diplomat-side analysis
> module** (factory + prompt + CLI + κ harness), sibling to `edit_classifier`, not a
> pipeline module and not a shared toolkit primitive.
> Companion docs: `ARCH_self_play.md` (result-JSON shape + aggregation),
> `papers/PAPER_PLAN.md` §1/§4.1 (the claim + method), `ASSESSMENT.md` §2 (skill
> dimensions — distinct from these failure-mode labels).

## Method — binary-question decomposition (BINEVAL-style)

The judge answers five independent yes/no questions from **transcript + final
positions only**; a deterministic rule derives the label (the LLM never emits the
label directly — same split as outcome scoring, where the LLM extracts facts and
code does the math).

| Q | Question (judge answers Y/N from transcript + final positions) |
|---|---|
| Q1 | Substantive engagement — did every faction make concrete proposals beyond restating openings? |
| Q2 | Subset convergence — did factions agree on some but not all issues? |
| Q3 | Explicit BATNA preference — did any faction state it preferred walking away / its BATNA over the live deal? |
| Q4 | Identity/coherence failure — did any faction lose its role or contradict its persona basics? |
| Q5 | Full agreement — did all factions agree on every issue? |

Deterministic derivation (`derive_label`, pure function — no judge math):
- Q5 = Y → `closed` (ceiling-vs-lift is read from the full/bare comparison, not here)
- else Q4 = Y → `incoherence`
- else Q3 = Y and Q1 = Y → `strategic_refusal`
- else Q2 = Y and Q1 = Y → `near_miss`
- else → `breakdown`

**Guardrail (§4.1):** the judge must be a **fixed independent model, not a
contestant scoring itself** — a dedicated `_MECHANISM_JUDGE` provider config (analogous
to `_SELF_PLAY_PRIMARY` in `game_environment.py`), operator-selected.

## Architecture — mirror `edit_classifier`

- **Module:** `src/modules/mechanism_classifier/` — `build_mechanism_classifier(llm_client,
  llm_providers_config, tier="commodity", attribution=None)` returning `None` when no
  primary provider (the optional-build convention), else a `MechanismClassifier` that
  calls `toolkit.structured_llm.structured_call(schema=<5-boolean schema>,
  system_prompt=<prompt file>, purpose="mechanism", max_retries=1)` and runs
  `derive_label` on the validated answers.
- **Prompt:** `config/prompts/mechanism_classifier.txt` (role + the 5 questions +
  guidance + few-shot; return `{q1..q5: bool, rationale: str}`).
- **Input:** `results["transcript"]` (channel/message log) + `results["round_responses"]
  [str(results["rounds_completed"])]` (final positions). `results["scores"].*`
  (`deal_reached`, `agreed_outcomes`, `no_deal_reason`) is used only for
  *validation-time* cross-checks, never as judge input.
- **Batch CLI:** `tools/classify_mechanisms.py` over a directory of result JSONs
  (mirror `tools/classify_edit_log.py`).
- **κ harness:** per-question Cohen's κ vs the hand-label seed set, **stdlib** (no
  `sklearn`; the suite is stdlib-light — reuse the seeded approach of
  `tests/self_play/aggregate_stats.py::bootstrap_ci` if κ CIs are wanted).

---

## Phase 52 — Mechanism classifier (machinery + initial prompt) (complete · Build 🔨)

> Phase intent for the i2c PLAN action. Regime: **Build** for the loopable slice
> below; the **validation is a supervised follow-on** (see "Assisted"). This mirrors
> the Phase-48/D-62 boundary: the loop authors the machinery + an initial prompt +
> fake-backed tests and STOPS before the human-judgment steps. Pre-decided
> architecture (D-67) so PLAN goes straight to steps. Foundation for the paper's
> co-primary harness-lift contribution (`PAPER_PLAN.md` §1) and reused by the
> offering's detection tier + tactic-library calibration (`papers/OPEN_ITEMS.md` §5).

### Autonomous — the loopable Build slice (hermetic, fake-backed tests)

**Acceptance criteria (tests-first):**
1. **Deterministic rule:** `derive_label({q1..q5})` returns the correct label for
   every combination in the derivation table (exhaustive truth-table test; pure
   function, no LLM).
2. **Classifier path:** with a **fake** `llm_client` whose `complete()` returns a
   canned 5-boolean JSON (keyed on `purpose="mechanism"`), `MechanismClassifier`
   produces the schema-validated answers → correct derived label — fully offline.
3. **Factory:** `build_mechanism_classifier` mirrors `build_edit_classifier` —
   translates the `pipeline.yaml` provider shape, returns `None` without a primary
   provider (unit-tested like `test_edit_classifier.py`).
4. **Input extraction:** given a synthetic result JSON, the classifier reads exactly
   `transcript` + final-round `round_responses` and passes them to the judge; it does
   **not** feed `scores.*` into the judge prompt (asserted on the fake's recorded call).
5. **Batch CLI:** `tools/classify_mechanisms.py` labels a directory of result JSONs
   with a fake classifier (mirror `test_classify_edit_log.py`) — hermetic.
6. **κ function:** a stdlib `cohens_kappa(labels_a, labels_b)` returns known values on
   synthetic agreement/disagreement fixtures (incl. perfect-agreement = 1.0,
   chance-level ≈ 0, degenerate single-class handled).
7. **Fake route:** `DryRunLLMClient` gains a `_mechanism_response()` returning
   schema-valid 5-boolean JSON on `purpose="mechanism"` (so dry-run self-play +
   classification stay offline).
8. **No regression:** full suite still passes.

The loop also authors an **initial** `config/prompts/mechanism_classifier.txt` (best
effort) and the ARCH/ARCHITECTURE doc-update step. It does **not** tune the prompt or
run any live judge.

### Assisted — supervised follow-on (the loop stops here; tracked as an FU / later phase)

- **A. Hand-label seed set** — serialize the prose seed labels (14e = strategic_refusal;
  gemini jsm1 = incoherence; mid jsm1 = near_miss; nano-bare = breakdown; ≥1 `closed`)
  into a machine-readable `tests/self_play/mechanism_seed_labels.json` (per-result-file
  `{q1..q5, derived_label}`), following the
  `tests/prompt_regression/scenarios/edit_classification/*.json` convention. Requires
  reading transcripts + human judgment; **no seed set exists today** (only prose in
  `PAPER_PLAN.md` §4.1 / `experiments/TUNING_LOG.md`).
- **B. Judge-prompt quality tuning** — Refine the 5-question prompt against the seed
  set (via `tests/prompt_regression/`).
- **C. Live κ validation** — run the fixed judge over the seed set (real keys + cost),
  compute per-question κ, ship only if acceptable; operator sets the threshold.
- **D. Independent-judge model choice** — operator selects `_MECHANISM_JUDGE` (must not
  be a contestant; cost/quality tradeoff).

### Out of scope
- Applying the classifier across the full campaign transcripts (that is the §5
  post-hoc analysis pass, gated on the unified campaign — a later phase).
- The capability probe battery (§4.2) — a separate build.

**Regime.** Build 🔨 for the machinery (autonomous-loopable); the validation (A–D) is
Refine/Run 👁 (supervised). Loops run on pirozhok via the i2c bot, not the laptop
(`rules/deployment.md`, FU-28).
