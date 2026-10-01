from __future__ import annotations

from datetime import date

import pytest

from hazar_api.models import LifeEventType
from hazar_api.questionnaire import (
    ALL_QUESTIONS,
    QUESTIONS,
    QUESTIONS_BY_ID,
    InvalidAnswerError,
    derive,
    effective_answers,
    next_question,
    to_screening_input,
    validate,
)
from hazar_tax_engine import required_facts, screen

from .conftest import ALL_NO

TODAY = date(2026, 10, 1)


def test_registry_drives_questions() -> None:
    provided = {q.provides for q in QUESTIONS}
    assert provided == required_facts(), "every fact a rule needs has a question, and nothing else is asked"
    assert len(QUESTIONS_BY_ID) == len(QUESTIONS)
    assert len(ALL_QUESTIONS) == len(QUESTIONS)


def test_first_question_and_completion() -> None:
    first = next_question({})
    assert first is not None
    assert first.id == "resident"
    assert next_question(ALL_NO) is None


def test_follow_up_questions_appear_only_when_relevant() -> None:
    answers = {k: v for k, v in ALL_NO.items() if k not in ("has_children",)}
    answers["has_children"] = True
    nxt = next_question(answers)
    assert nxt is not None
    assert nxt.id == "children_birth_dates"
    answers["children_birth_dates"] = ["2022-03-01"]
    # Married → the single-parent question is skipped.
    assert next_question(answers) is None
    answers["marital_status"] = "divorced"
    nxt = next_question(answers)
    assert nxt is not None
    assert nxt.id == "single_parent"


def test_stale_answers_are_dropped() -> None:
    answers = dict(ALL_NO, has_children=False, children_birth_dates=["2022-03-01"])
    assert "children_birth_dates" not in effective_answers(answers)
    assert derive(answers).events == [e for e in derive(ALL_NO).events]


@pytest.mark.parametrize(
    ("qid", "raw", "expected"),
    [
        ("resident", True, True),
        ("sex", "female", "female"),
        ("children_birth_dates", ["2024-01-02", "2020-05-06"], ["2020-05-06", "2024-01-02"]),
        ("degree_years", [2018, 2018, 2021], [2018, 2021]),
        ("discharge_date", "2019-08-01", "2019-08-01"),
        ("donation_years", [2025, 2020], [2020, 2025]),
        (
            "localities",
            [{"name": " באר שבע ", "from_year": 2019, "to_year": 2021}],
            [{"name": "באר שבע", "from_year": 2019, "to_year": 2021}],
        ),
    ],
)
def test_validate_ok(qid: str, raw: object, expected: object) -> None:
    assert validate(QUESTIONS_BY_ID[qid], raw, TODAY) == expected


@pytest.mark.parametrize(
    ("qid", "raw"),
    [
        ("resident", "yes"),
        ("resident", 1),
        ("sex", "other"),
        ("children_birth_dates", []),
        ("children_birth_dates", ["2030-01-01"]),
        ("children_birth_dates", ["not-a-date"]),
        ("degree_years", [True]),
        ("degree_years", [2027]),
        ("donation_years", [2026]),  # current year is not yet a completed tax year
        ("donation_years", [2019]),  # outside the refund window
        ("localities", [{"name": "", "from_year": 2019}]),
        ("localities", [{"name": "x", "from_year": 2021, "to_year": 2019}]),
        ("localities", ["x"]),
    ],
)
def test_validate_rejects(qid: str, raw: object) -> None:
    with pytest.raises(InvalidAnswerError):
        validate(QUESTIONS_BY_ID[qid], raw, TODAY)


def test_derive_builds_life_events_and_engine_input() -> None:
    answers = dict(
        ALL_NO,
        marital_status="divorced",
        has_children=True,
        children_birth_dates=["2021-04-01"],
        single_parent=True,
        has_degree=True,
        degree_years=[2022],
        donations=True,
        donation_years=[2024],
    )
    d = derive(answers)
    assert d.single_parent is True
    types = [e.type for e in d.events]
    assert LifeEventType.CHILD_BIRTH in types
    assert LifeEventType.DEGREE_COMPLETED in types
    assert LifeEventType.DONATION in types
    assert LifeEventType.LOCALITY in types

    facts = to_screening_input(
        resident=d.resident,
        sex=d.sex,
        marital_status=d.marital_status,
        single_parent=d.single_parent,
        disability=d.disability,
        events=d.events,
    )
    rules = {f.rule_id: f.years for f in screen(facts, TODAY).findings}
    assert rules["credit.children"] == [2021, 2022, 2023, 2024, 2025]
    assert rules["credit.single_parent"] == [2021, 2022, 2023, 2024, 2025]
    assert rules["credit.academic_degree"] == [2022, 2023, 2024, 2025]
    assert rules["deduction.donations"] == [2024]
    assert rules["credit.eligible_locality"] == [2020, 2021, 2022, 2023, 2024, 2025]
