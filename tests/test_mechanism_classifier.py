from __future__ import annotations

import itertools

import pytest

from modules.mechanism_classifier import derive_label


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


@pytest.mark.parametrize(
    "q1,q2,q3,q4,q5",
    list(itertools.product([False, True], repeat=5)),
)
def test_derive_label_truth_table(q1: bool, q2: bool, q3: bool, q4: bool, q5: bool) -> None:
    answers = {"q1": q1, "q2": q2, "q3": q3, "q4": q4, "q5": q5}
    assert derive_label(answers) == _ref_derive_label(q1, q2, q3, q4, q5)


def test_q5_takes_priority_over_everything() -> None:
    answers = {"q1": True, "q2": True, "q3": True, "q4": True, "q5": True}
    assert derive_label(answers) == "closed"


def test_q4_takes_priority_over_q3_and_q1() -> None:
    answers = {"q1": True, "q2": True, "q3": True, "q4": True, "q5": False}
    assert derive_label(answers) == "incoherence"


def test_q3_and_q1_prefer_strategic_refusal_over_near_miss() -> None:
    answers = {"q1": True, "q2": True, "q3": True, "q4": False, "q5": False}
    assert derive_label(answers) == "strategic_refusal"


def test_q1_is_required_for_q2_or_q3_routes() -> None:
    answers_q2 = {"q1": False, "q2": True, "q3": False, "q4": False, "q5": False}
    answers_q3 = {"q1": False, "q2": False, "q3": True, "q4": False, "q5": False}
    assert derive_label(answers_q2) == "breakdown"
    assert derive_label(answers_q3) == "breakdown"
