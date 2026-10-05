import json

import pytest

from evaluation.evaluate import (
    DEFAULT_QUESTIONS,
    contains_term,
    load_questions,
    score_answer,
    summarize,
)
from rag_pipeline.pipeline import NOT_FOUND_MESSAGE, RagAnswer

Q_FACT = {"id": 1, "question": "q", "must_include": [["24"], ["8", "eight"]]}
Q_NONE = {"id": 2, "question": "q", "expect_not_found": True}


def test_contains_term_whole_numbers_only():
    assert contains_term("You get 12 days.", "12")
    assert not contains_term("You get 120 days.", "12")
    assert not contains_term("Uptime of 99.9%", "99")
    assert contains_term("It costs US$99 per user", "99")
    assert contains_term("Budget is US$1,200 per year", "1200")
    assert contains_term("Budget is US$1,200 per year", "1,200")
    assert contains_term("a 25% credit", "25%")
    assert contains_term("Founded in PUNE", "Pune")


def test_all_groups_required():
    assert score_answer(Q_FACT, "24 days, and up to 8 can carry forward", True) == (True, "all required facts present")
    ok, reason = score_answer(Q_FACT, "24 days of leave", True)
    assert not ok and "8" in reason


def test_alternatives_within_group():
    assert score_answer(Q_FACT, "24 days; eight carry forward", True)[0]


def test_not_found_answer_fails_answerable_question():
    ok, reason = score_answer(Q_FACT, NOT_FOUND_MESSAGE, False)
    assert not ok and "not found" in reason


def test_unanswerable_question_requires_refusal():
    assert score_answer(Q_NONE, NOT_FOUND_MESSAGE, False)[0]
    assert not score_answer(Q_NONE, "Revenue was $5 million.", True)[0]


def test_found_flag_detects_not_found_message():
    assert not RagAnswer("q", NOT_FOUND_MESSAGE).found
    assert not RagAnswer("q", "I could not find the answer in the provided documents").found
    assert RagAnswer("q", "The CEO is Asha Menon.").found


@pytest.mark.parametrize("correct,expected_acc,passed", [(10, 1.0, True), (9, 0.9, True), (8, 0.8, False)])
def test_accuracy_threshold(correct, expected_acc, passed):
    results = [{"correct": i < correct} for i in range(10)]
    s = summarize(results)
    assert s["correct"] == correct and s["incorrect"] == 10 - correct
    assert s["accuracy"] == pytest.approx(expected_acc)
    assert s["passed"] is passed  # 8/10 = 80% must NOT pass an 85% target


def test_question_set_is_valid():
    questions = load_questions(DEFAULT_QUESTIONS)
    assert len(questions) == 10
    assert len({q["id"] for q in questions}) == 10
    assert sum(bool(q.get("expect_not_found")) for q in questions) >= 1
    sources = {s.strip() for q in questions if q.get("source") for s in q["source"].split(";")}
    assert len(sources) == 3  # questions cover all three documents
    from conftest import SAMPLE_PDFS

    assert sources == set(SAMPLE_PDFS)


def test_expected_answers_satisfy_their_own_criteria():
    """Sanity check: each expected answer must pass the scoring rule it defines."""
    for q in json.loads(DEFAULT_QUESTIONS.read_text(encoding="utf-8")):
        if q.get("expect_not_found"):
            continue
        assert score_answer(q, q["expected_answer"], True)[0], q["id"]


def test_expected_source_formatting():
    from evaluation.evaluate import format_expected_source

    assert format_expected_source(None, None) == "none (not in documents)"
    assert format_expected_source("a.pdf", 2) == "a.pdf, page 2"
    assert format_expected_source("a.pdf; b.pdf", "1; 3") == "a.pdf, page 1; b.pdf, page 3"
