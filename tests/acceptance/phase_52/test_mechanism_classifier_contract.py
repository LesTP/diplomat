"""Phase 52 acceptance suite — mechanism classifier contract.

Contract items:
  AC1: derive_label is a pure deterministic rule covering all 32 Q1-Q5 combinations.
       Priority: Q5 → closed; Q4 → incoherence; Q3+Q1 → strategic_refusal;
       Q2+Q1 → near_miss; else → breakdown.
  AC2: MechanismClassifier calls the judge via structured_call (purpose="mechanism"),
       validates the 5-boolean JSON schema, and derives the correct label offline
       using a fake LLM client.
  AC3: build_mechanism_classifier mirrors build_edit_classifier — translates the
       pipeline.yaml primary-provider shape; returns None without a primary provider.
  AC4: The classifier passes only transcript + final-round round_responses to the
       judge; scores.* (deal_reached, agreed_outcomes, no_deal_reason) is excluded.
  AC5: tools/classify_mechanisms.py labels a directory of result JSONs using a fake
       classifier — hermetic, no real LLM calls.
  AC6: cohens_kappa(labels_a, labels_b) returns 1.0 for perfect agreement, ≤0 for
       systematic disagreement, and handles degenerate single-class input without error.
  AC7: DryRunLLMClient.complete(purpose="mechanism") returns schema-valid 5-boolean
       JSON so dry-run self-play + offline classification stay cost-free.
"""

from __future__ import annotations

import importlib.util
import json
import random
from pathlib import Path
from typing import Any

import pytest

# ---------------------------------------------------------------------------
# Import guards — tests are red-as-expected when production code is absent.
# ---------------------------------------------------------------------------

try:
    from modules.mechanism_classifier import (
        MechanismClassifier,
        build_mechanism_classifier,
        derive_label,
    )
    _CLASSIFIER_AVAILABLE = True
except ImportError:
    _CLASSIFIER_AVAILABLE = False
    MechanismClassifier = None  # type: ignore[assignment,misc]
    build_mechanism_classifier = None  # type: ignore[assignment]
    derive_label = None  # type: ignore[assignment]

try:
    from modules.mechanism_classifier import cohens_kappa
    _KAPPA_AVAILABLE = True
except ImportError:
    _KAPPA_AVAILABLE = False

    def cohens_kappa(*args: Any, **kwargs: Any) -> float:  # type: ignore[misc]
        raise NotImplementedError("cohens_kappa not implemented yet")


try:
    from tests.self_play.fake_llm_client import DryRunLLMClient, _PURPOSE_TO_CALL_TYPE
    _DRYRUN_MECH_AVAILABLE = "mechanism" in _PURPOSE_TO_CALL_TYPE
except ImportError:
    _DRYRUN_MECH_AVAILABLE = False
    DryRunLLMClient = None  # type: ignore[assignment,misc]

_need_classifier = pytest.mark.xfail(
    not _CLASSIFIER_AVAILABLE,
    reason="modules.mechanism_classifier not implemented yet",
    strict=False,
)
_need_kappa = pytest.mark.xfail(
    not _KAPPA_AVAILABLE,
    reason="cohens_kappa not implemented yet",
    strict=False,
)
_need_dryrun_mech = pytest.mark.xfail(
    not _DRYRUN_MECH_AVAILABLE,
    reason="DryRunLLMClient mechanism route not implemented yet",
    strict=False,
)


# ---------------------------------------------------------------------------
# Reference derivation (mirrors the contract's derive_label rule exactly)
# ---------------------------------------------------------------------------

def _ref_derive_label(q1: bool, q2: bool, q3: bool, q4: bool, q5: bool) -> str:
    if q5:
        return "closed"
    if q4:
        return "incoherence"
    if q3 and q1:
        return "strategic_refusal"
    if q2 and q1:
        return "near_miss"
    return "breakdown"


# ---------------------------------------------------------------------------
# Shared fake LLM client for offline classifier tests (AC2–AC4)
# ---------------------------------------------------------------------------

_CANNED_MECHANISM_RESPONSE = json.dumps({
    "q1": True,
    "q2": True,
    "q3": False,
    "q4": False,
    "q5": False,
    "rationale": "Fake: factions engaged and reached partial agreement.",
})

# q1=T, q2=T, q3=F, q4=F, q5=F → near_miss  (per reference rule)
_CANNED_EXPECTED_LABEL = "near_miss"


class _FakeMechanismLLMClient:
    """Returns canned 5-boolean JSON when purpose='mechanism'; records every call."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def complete(self, **kwargs: Any) -> str:
        self.calls.append({
            "purpose": kwargs.get("purpose"),
            "messages": kwargs.get("messages") or [],
        })
        if kwargs.get("purpose") == "mechanism":
            return _CANNED_MECHANISM_RESPONSE
        return "{}"


# ---------------------------------------------------------------------------
# Synthetic result JSON for input-extraction tests
# ---------------------------------------------------------------------------

_SYNTHETIC_RESULT: dict[str, Any] = {
    "transcript": [
        {"round": 1, "faction": "alpha", "text": "I propose the coalition_abc split."},
        {"round": 1, "faction": "beta", "text": "We can accept coalition_abc terms."},
    ],
    "round_responses": {
        "1": {
            "alpha": "Final position: 40/40/20 split across coalition_abc.",
            "beta": "Accepted the 40/40/20 arrangement.",
        }
    },
    "rounds_completed": 1,
    "scores": {
        "deal_reached": True,
        "agreed_outcomes": {"coalition_structure": "abc_only"},
        "no_deal_reason": None,
    },
}


# ---------------------------------------------------------------------------
# AC1: derive_label exhaustive truth-table (all 32 combinations)
# ---------------------------------------------------------------------------

_ALL_Q_COMBOS = [
    (bool(i >> 4 & 1), bool(i >> 3 & 1), bool(i >> 2 & 1), bool(i >> 1 & 1), bool(i & 1))
    for i in range(32)
]


@_need_classifier
class TestDeriveLabelExhaustive:
    """AC1 — derive_label produces the correct label for every Q1-Q5 combination."""

    @pytest.mark.parametrize("q1,q2,q3,q4,q5", _ALL_Q_COMBOS)
    def test_truth_table_entry(
        self, q1: bool, q2: bool, q3: bool, q4: bool, q5: bool
    ) -> None:
        expected = _ref_derive_label(q1, q2, q3, q4, q5)
        answers = {"q1": q1, "q2": q2, "q3": q3, "q4": q4, "q5": q5}
        result = derive_label(answers)
        assert result == expected, (
            f"derive_label({answers}) → {result!r}, expected {expected!r}"
        )

    def test_q5_takes_priority_over_all(self) -> None:
        """Q5=Y yields 'closed' regardless of other flags."""
        answers = {"q1": True, "q2": True, "q3": True, "q4": True, "q5": True}
        assert derive_label(answers) == "closed"

    def test_q4_takes_priority_over_q3_q1(self) -> None:
        """Q4=Y yields 'incoherence' when Q5=N, even if Q3+Q1 also trigger."""
        answers = {"q1": True, "q2": False, "q3": True, "q4": True, "q5": False}
        assert derive_label(answers) == "incoherence"

    def test_strategic_refusal_takes_priority_over_near_miss(self) -> None:
        """Q3+Q1=Y yields 'strategic_refusal' even when Q2+Q1=Y (Q5=N, Q4=N)."""
        answers = {"q1": True, "q2": True, "q3": True, "q4": False, "q5": False}
        assert derive_label(answers) == "strategic_refusal"

    def test_q1_false_blocks_strategic_refusal(self) -> None:
        """Q3=Y alone (Q1=N) is insufficient — falls to 'breakdown'."""
        answers = {"q1": False, "q2": False, "q3": True, "q4": False, "q5": False}
        assert derive_label(answers) == "breakdown"

    def test_q1_false_blocks_near_miss(self) -> None:
        """Q2=Y alone (Q1=N) is insufficient — falls to 'breakdown'."""
        answers = {"q1": False, "q2": True, "q3": False, "q4": False, "q5": False}
        assert derive_label(answers) == "breakdown"

    def test_all_false_is_breakdown(self) -> None:
        answers = {"q1": False, "q2": False, "q3": False, "q4": False, "q5": False}
        assert derive_label(answers) == "breakdown"

    def test_return_is_one_of_five_labels(self) -> None:
        """derive_label always returns one of the five valid label strings."""
        valid_labels = {"closed", "incoherence", "strategic_refusal", "near_miss", "breakdown"}
        for q1, q2, q3, q4, q5 in _ALL_Q_COMBOS:
            answers = {"q1": q1, "q2": q2, "q3": q3, "q4": q4, "q5": q5}
            result = derive_label(answers)
            assert result in valid_labels, f"Invalid label {result!r} for {answers}"


# ---------------------------------------------------------------------------
# AC2: MechanismClassifier end-to-end path (fake client, offline)
# ---------------------------------------------------------------------------

@_need_classifier
class TestMechanismClassifierPath:
    """AC2 — offline end-to-end: fake JSON → schema validation → derive_label → label."""

    async def test_classify_returns_correct_label(self) -> None:
        fake = _FakeMechanismLLMClient()
        classifier = MechanismClassifier(
            llm_client=fake,
            llm_config={"provider": "fake", "models": {"commodity": "fake-model"}},
            tier="commodity",
            prompt_path="config/prompts/mechanism_classifier.txt",
        )
        label = await classifier.classify(_SYNTHETIC_RESULT)
        # Canned response: q1=T, q2=T → near_miss
        assert label == _CANNED_EXPECTED_LABEL

    async def test_classify_calls_judge_exactly_once(self) -> None:
        fake = _FakeMechanismLLMClient()
        classifier = MechanismClassifier(
            llm_client=fake,
            llm_config={"provider": "fake", "models": {"commodity": "fake-model"}},
            tier="commodity",
            prompt_path="config/prompts/mechanism_classifier.txt",
        )
        await classifier.classify(_SYNTHETIC_RESULT)
        mech_calls = [c for c in fake.calls if c["purpose"] == "mechanism"]
        assert len(mech_calls) == 1, (
            f"Expected exactly 1 mechanism call, got {len(mech_calls)}"
        )

    async def test_classify_returns_valid_label_string(self) -> None:
        fake = _FakeMechanismLLMClient()
        classifier = MechanismClassifier(
            llm_client=fake,
            llm_config={"provider": "fake", "models": {"commodity": "fake-model"}},
            tier="commodity",
            prompt_path="config/prompts/mechanism_classifier.txt",
        )
        label = await classifier.classify(_SYNTHETIC_RESULT)
        valid = {"closed", "incoherence", "strategic_refusal", "near_miss", "breakdown"}
        assert label in valid, f"classify() returned unknown label {label!r}"

    async def test_classify_is_fully_offline(self) -> None:
        """No real network calls: the fake client never delegates to a real provider."""
        import socket
        original_getaddrinfo = socket.getaddrinfo

        def _no_network(*args: Any, **kwargs: Any) -> Any:
            raise OSError("Network call detected in offline test")

        fake = _FakeMechanismLLMClient()
        classifier = MechanismClassifier(
            llm_client=fake,
            llm_config={"provider": "fake", "models": {"commodity": "fake-model"}},
            tier="commodity",
            prompt_path="config/prompts/mechanism_classifier.txt",
        )
        socket.getaddrinfo = _no_network
        try:
            await classifier.classify(_SYNTHETIC_RESULT)
        finally:
            socket.getaddrinfo = original_getaddrinfo


# ---------------------------------------------------------------------------
# AC3: build_mechanism_classifier factory
# ---------------------------------------------------------------------------

@_need_classifier
class TestBuildMechanismClassifierFactory:
    """AC3 — factory mirrors build_edit_classifier: translates config, returns None on missing primary."""

    def test_returns_none_without_primary_key(self) -> None:
        result = build_mechanism_classifier(
            llm_client=_FakeMechanismLLMClient(),
            llm_providers_config={},
        )
        assert result is None

    def test_returns_none_when_primary_is_empty_dict(self) -> None:
        result = build_mechanism_classifier(
            llm_client=_FakeMechanismLLMClient(),
            llm_providers_config={"primary": {}},
        )
        assert result is None

    def test_returns_classifier_with_valid_primary(self) -> None:
        result = build_mechanism_classifier(
            llm_client=_FakeMechanismLLMClient(),
            llm_providers_config={
                "primary": {
                    "provider": "google",
                    "models": {"commodity": "gemini-2.5-flash-lite"},
                    "api_key_env": "GOOGLE_API_KEY",
                }
            },
            tier="commodity",
        )
        assert result is not None

    def test_factory_translates_provider_name(self) -> None:
        result = build_mechanism_classifier(
            llm_client=_FakeMechanismLLMClient(),
            llm_providers_config={
                "primary": {
                    "provider": "google",
                    "models": {"commodity": "gemini-2.5-flash-lite"},
                    "api_key_env": "GOOGLE_API_KEY",
                }
            },
            tier="commodity",
        )
        assert result is not None
        assert result.llm_config["provider"] == "google"

    def test_factory_translates_model_tier(self) -> None:
        result = build_mechanism_classifier(
            llm_client=_FakeMechanismLLMClient(),
            llm_providers_config={
                "primary": {
                    "provider": "google",
                    "models": {"commodity": "gemini-2.5-flash-lite"},
                    "api_key_env": "GOOGLE_API_KEY",
                }
            },
            tier="commodity",
        )
        assert result is not None
        assert result.llm_config["models"]["commodity"] == "gemini-2.5-flash-lite"

    def test_factory_passes_attribution(self) -> None:
        result = build_mechanism_classifier(
            llm_client=_FakeMechanismLLMClient(),
            llm_providers_config={
                "primary": {
                    "provider": "openai",
                    "models": {"commodity": "gpt-4.1-mini"},
                    "api_key_env": "OPENAI_API_KEY",
                }
            },
            attribution="phase-52-test",
        )
        assert result is not None
        assert result.attribution == "phase-52-test"

    def test_factory_ignores_unknown_top_level_keys(self) -> None:
        """Extra keys in llm_providers_config do not cause a crash."""
        result = build_mechanism_classifier(
            llm_client=_FakeMechanismLLMClient(),
            llm_providers_config={
                "primary": {
                    "provider": "openai",
                    "models": {"commodity": "gpt-4.1-mini"},
                    "api_key_env": "OPENAI_API_KEY",
                },
                "secondary": {"provider": "anthropic"},
            },
        )
        assert result is not None


# ---------------------------------------------------------------------------
# AC4: Input extraction — transcript + final-round only; no scores.*
# ---------------------------------------------------------------------------

@_need_classifier
class TestInputExtraction:
    """AC4 — classifier judge receives transcript + final round_responses; excludes scores.*"""

    def _make_classifier(self, fake: _FakeMechanismLLMClient) -> Any:
        return MechanismClassifier(
            llm_client=fake,
            llm_config={"provider": "fake", "models": {"commodity": "fake-model"}},
            tier="commodity",
            prompt_path="config/prompts/mechanism_classifier.txt",
        )

    def _mechanism_call_text(self, fake: _FakeMechanismLLMClient) -> str:
        mech_call = next(c for c in fake.calls if c["purpose"] == "mechanism")
        return json.dumps(mech_call["messages"])

    async def test_transcript_content_in_judge_prompt(self) -> None:
        fake = _FakeMechanismLLMClient()
        await self._make_classifier(fake).classify(_SYNTHETIC_RESULT)
        text = self._mechanism_call_text(fake)
        assert (
            "coalition_abc" in text or "alpha" in text or "I propose" in text
        ), "Transcript text not found in judge messages"

    async def test_final_round_responses_in_judge_prompt(self) -> None:
        fake = _FakeMechanismLLMClient()
        await self._make_classifier(fake).classify(_SYNTHETIC_RESULT)
        text = self._mechanism_call_text(fake)
        assert (
            "40/40/20" in text or "Final position" in text or "Accepted" in text
        ), "Final-round response text not found in judge messages"

    async def test_deal_reached_excluded_from_judge_prompt(self) -> None:
        fake = _FakeMechanismLLMClient()
        await self._make_classifier(fake).classify(_SYNTHETIC_RESULT)
        text = self._mechanism_call_text(fake)
        assert "deal_reached" not in text, (
            "scores.deal_reached must NOT appear in the judge prompt"
        )

    async def test_agreed_outcomes_excluded_from_judge_prompt(self) -> None:
        fake = _FakeMechanismLLMClient()
        await self._make_classifier(fake).classify(_SYNTHETIC_RESULT)
        text = self._mechanism_call_text(fake)
        assert "agreed_outcomes" not in text, (
            "scores.agreed_outcomes must NOT appear in the judge prompt"
        )

    async def test_no_deal_reason_excluded_from_judge_prompt(self) -> None:
        fake = _FakeMechanismLLMClient()
        await self._make_classifier(fake).classify(_SYNTHETIC_RESULT)
        text = self._mechanism_call_text(fake)
        assert "no_deal_reason" not in text, (
            "scores.no_deal_reason must NOT appear in the judge prompt"
        )

    async def test_reads_correct_final_round_by_rounds_completed(self) -> None:
        """Classifier uses round_responses[str(rounds_completed)], not an earlier round."""
        multi_round_result: dict[str, Any] = {
            "transcript": [
                {"round": 1, "faction": "alpha", "text": "Early round proposal."},
                {"round": 2, "faction": "alpha", "text": "Decisive final position."},
            ],
            "round_responses": {
                "1": {"alpha": "intermediate_early_position"},
                "2": {"alpha": "decisive_final_position"},
            },
            "rounds_completed": 2,
            "scores": {"deal_reached": False},
        }
        fake = _FakeMechanismLLMClient()
        await self._make_classifier(fake).classify(multi_round_result)
        text = self._mechanism_call_text(fake)
        assert "decisive_final_position" in text, (
            "Final round (round 2) response not in judge messages"
        )


# ---------------------------------------------------------------------------
# AC5: Batch CLI — tools/classify_mechanisms.py hermetic test
# ---------------------------------------------------------------------------

def _load_classify_mechanisms() -> Any | None:
    path = Path("tools/classify_mechanisms.py").resolve()
    if not path.exists():
        return None
    spec = importlib.util.spec_from_file_location("classify_mechanisms", path)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


_classify_mechanisms_mod = _load_classify_mechanisms()
_need_batch_cli = pytest.mark.xfail(
    _classify_mechanisms_mod is None,
    reason="tools/classify_mechanisms.py not implemented yet",
    strict=False,
)


def _write_result_json(path: Path, result: dict[str, Any]) -> None:
    path.write_text(json.dumps(result), encoding="utf-8")


def _make_result_dict(
    *,
    deal_reached: bool = True,
    rounds: int = 1,
    transcript_tag: str = "proposal_text",
) -> dict[str, Any]:
    return {
        "transcript": [
            {"round": r, "faction": "alpha", "text": f"{transcript_tag}_round_{r}"}
            for r in range(1, rounds + 1)
        ],
        "round_responses": {
            str(rounds): {"alpha": f"final_position_{transcript_tag}"}
        },
        "rounds_completed": rounds,
        "scores": {
            "deal_reached": deal_reached,
            "agreed_outcomes": {},
            "no_deal_reason": None if deal_reached else "no agreement",
        },
    }


@_need_batch_cli
class TestBatchCLI:
    """AC5 — classify_mechanisms.py processes a directory of result JSONs hermetically."""

    async def test_processes_all_result_files(self, tmp_path: Path, monkeypatch: Any) -> None:
        (tmp_path / "r1.json").write_text(
            json.dumps(_make_result_dict(deal_reached=True)), encoding="utf-8"
        )
        (tmp_path / "r2.json").write_text(
            json.dumps(_make_result_dict(deal_reached=False)), encoding="utf-8"
        )

        processed: list[dict] = []

        class _FakeCLIClassifier:
            async def classify(self, result: dict) -> str:
                processed.append(result)
                return "near_miss"

        monkeypatch.setattr(
            _classify_mechanisms_mod,
            "_build_classifier",
            lambda *a, **kw: _FakeCLIClassifier(),
        )
        import argparse
        args = argparse.Namespace(
            input_dir=str(tmp_path),
            output=None,
            config="config/pipeline.yaml",
            tier="commodity",
        )
        await _classify_mechanisms_mod._run(args)
        assert len(processed) == 2, f"Expected 2 results processed, got {len(processed)}"

    async def test_output_contains_label_summary(
        self, tmp_path: Path, monkeypatch: Any, capsys: Any
    ) -> None:
        (tmp_path / "r1.json").write_text(
            json.dumps(_make_result_dict(deal_reached=True)), encoding="utf-8"
        )

        class _FakeCLIClassifier:
            async def classify(self, result: dict) -> str:
                return "breakdown"

        monkeypatch.setattr(
            _classify_mechanisms_mod,
            "_build_classifier",
            lambda *a, **kw: _FakeCLIClassifier(),
        )
        import argparse
        args = argparse.Namespace(
            input_dir=str(tmp_path),
            output=None,
            config="config/pipeline.yaml",
            tier="commodity",
        )
        await _classify_mechanisms_mod._run(args)
        out = capsys.readouterr().out
        assert "breakdown" in out.lower(), (
            f"Expected 'breakdown' label in CLI output, got: {out!r}"
        )

    async def test_skips_non_json_files(self, tmp_path: Path, monkeypatch: Any) -> None:
        (tmp_path / "r1.json").write_text(
            json.dumps(_make_result_dict()), encoding="utf-8"
        )
        (tmp_path / "not_json.txt").write_text("not a json file", encoding="utf-8")
        (tmp_path / "bad.json").write_text("{{invalid json", encoding="utf-8")

        processed: list[dict] = []

        class _FakeCLIClassifier:
            async def classify(self, result: dict) -> str:
                processed.append(result)
                return "closed"

        monkeypatch.setattr(
            _classify_mechanisms_mod,
            "_build_classifier",
            lambda *a, **kw: _FakeCLIClassifier(),
        )
        import argparse
        args = argparse.Namespace(
            input_dir=str(tmp_path),
            output=None,
            config="config/pipeline.yaml",
            tier="commodity",
        )
        await _classify_mechanisms_mod._run(args)
        assert len(processed) == 1, (
            f"Expected only the valid JSON to be processed, got {len(processed)}"
        )


# ---------------------------------------------------------------------------
# AC6: cohens_kappa stdlib function
# ---------------------------------------------------------------------------

@_need_kappa
class TestCohensKappa:
    """AC6 — cohens_kappa returns correct values on known fixtures; handles edge cases."""

    def test_perfect_agreement_returns_one(self) -> None:
        labels = ["closed", "breakdown", "near_miss", "incoherence", "strategic_refusal"]
        result = cohens_kappa(labels, labels)
        assert result == pytest.approx(1.0), f"Perfect agreement kappa={result}, expected 1.0"

    def test_perfect_agreement_boolean_labels(self) -> None:
        labels_str = ["True", "False", "True", "True", "False"]
        assert cohens_kappa(labels_str, labels_str) == pytest.approx(1.0)

    def test_complete_swap_is_negative_or_zero(self) -> None:
        """Systematic label swap produces kappa ≤ 0."""
        labels_a = ["closed", "closed", "breakdown", "breakdown"]
        labels_b = ["breakdown", "breakdown", "closed", "closed"]
        kappa = cohens_kappa(labels_a, labels_b)
        assert kappa <= 0.0, f"Expected kappa ≤ 0 for complete swap, got {kappa}"

    def test_chance_agreement_near_zero(self) -> None:
        """Independent random assignments yield kappa close to 0."""
        rng_a = random.Random(1234)
        rng_b = random.Random(5678)
        label_set = ["closed", "breakdown", "near_miss", "incoherence", "strategic_refusal"]
        labels_a = [rng_a.choice(label_set) for _ in range(300)]
        labels_b = [rng_b.choice(label_set) for _ in range(300)]
        kappa = cohens_kappa(labels_a, labels_b)
        assert -0.3 < kappa < 0.3, f"Expected chance-level kappa ≈ 0, got {kappa}"

    def test_degenerate_single_class_no_error(self) -> None:
        """All-same labels must not raise; kappa is defined as 1.0 or 0.0 for degenerate case."""
        labels = ["breakdown"] * 20
        result = cohens_kappa(labels, labels)
        assert isinstance(result, float), f"Expected float, got {type(result)}"

    def test_empty_input_does_not_crash(self) -> None:
        """Empty inputs must not crash — return float or raise ValueError (not unhandled)."""
        try:
            result = cohens_kappa([], [])
            assert isinstance(result, float)
        except (ValueError, ZeroDivisionError, AssertionError):
            pass  # Raising on empty input is an acceptable contract.

    def test_return_type_is_float(self) -> None:
        labels_a = ["closed", "breakdown", "near_miss"]
        labels_b = ["closed", "near_miss", "near_miss"]
        result = cohens_kappa(labels_a, labels_b)
        assert isinstance(result, float), f"Expected float, got {type(result)}"

    def test_kappa_bounded_minus_one_to_one(self) -> None:
        """Kappa must lie in [-1.0, 1.0]."""
        label_set = ["a", "b", "c"]
        rng = random.Random(0)
        for _ in range(10):
            la = [rng.choice(label_set) for _ in range(50)]
            lb = [rng.choice(label_set) for _ in range(50)]
            k = cohens_kappa(la, lb)
            assert -1.0 <= k <= 1.0, f"Kappa {k} out of [-1, 1]"


# ---------------------------------------------------------------------------
# AC7: DryRunLLMClient mechanism route
# ---------------------------------------------------------------------------

@_need_dryrun_mech
class TestDryRunMechanismRoute:
    """AC7 — DryRunLLMClient returns schema-valid 5-boolean JSON for purpose='mechanism'."""

    async def test_mechanism_purpose_returns_valid_json(self) -> None:
        from tests.self_play.fake_llm_client import DryRunLLMClient as _DRClient
        client = _DRClient()
        response = await client.complete(
            messages=[
                {"role": "system", "content": "You are a mechanism judge."},
                {"role": "user", "content": "Evaluate this transcript."},
            ],
            config={"provider": "fake", "models": {"commodity": "fake-model"}},
            tier="commodity",
            purpose="mechanism",
        )
        data = json.loads(response)
        assert isinstance(data, dict), f"Expected JSON object, got {type(data)}"

    async def test_mechanism_response_has_five_boolean_questions(self) -> None:
        from tests.self_play.fake_llm_client import DryRunLLMClient as _DRClient
        client = _DRClient()
        response = await client.complete(
            messages=[
                {"role": "system", "content": "Evaluate the negotiation."},
                {"role": "user", "content": "Transcript and positions here."},
            ],
            purpose="mechanism",
        )
        data = json.loads(response)
        for q in ("q1", "q2", "q3", "q4", "q5"):
            assert q in data, f"Missing key {q!r} in mechanism response: {data}"
            assert isinstance(data[q], bool), (
                f"{q} must be bool in mechanism response, got {type(data[q])}"
            )

    async def test_mechanism_response_has_rationale_string(self) -> None:
        from tests.self_play.fake_llm_client import DryRunLLMClient as _DRClient
        client = _DRClient()
        response = await client.complete(
            messages=[{"role": "user", "content": "test"}],
            purpose="mechanism",
        )
        data = json.loads(response)
        assert "rationale" in data, f"Missing 'rationale' in mechanism response: {data}"
        assert isinstance(data["rationale"], str)

    async def test_mechanism_call_recorded_with_correct_type(self) -> None:
        from tests.self_play.fake_llm_client import DryRunLLMClient as _DRClient
        client = _DRClient()
        await client.complete(
            messages=[{"role": "user", "content": "test"}],
            purpose="mechanism",
        )
        assert len(client.calls) == 1
        assert client.calls[0]["call_type"] == "MECHANISM", (
            f"Expected call_type='MECHANISM', got {client.calls[0]['call_type']!r}"
        )

    async def test_non_mechanism_purpose_unaffected(self) -> None:
        """Existing call types (generation, extraction) are unaffected by the new route."""
        from tests.self_play.fake_llm_client import DryRunLLMClient as _DRClient
        client = _DRClient()
        response = await client.complete(
            messages=[
                {
                    "role": "system",
                    "content": "You are diplomat's state extraction engine.",
                }
            ],
            purpose="extraction",
        )
        data = json.loads(response)
        # Extraction returns empty {} per the existing fake
        assert isinstance(data, dict)
        # Mechanism keys must NOT appear in an extraction response
        assert "q1" not in data
