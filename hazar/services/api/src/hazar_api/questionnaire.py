"""Structured questionnaire, driven by the tax-engine rule registry (ADR 0003).

A question is asked only if some registry rule needs the fact it provides. Question *text* lives in the
web app's he.json, keyed by question id. This module defines ids, answer kinds, conditions and validation,
and derives the profile and life events from the answers.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Literal

from hazar_api.models import LifeEventType
from hazar_tax_engine import Fact, LocalityPeriod, ScreeningInput, refund_window, required_facts

Kind = Literal["yes_no", "choice", "date", "dates", "years", "window_years", "localities"]
Answers = dict[str, Any]

MIN_YEAR = 1940
MAX_LIST = 20


class InvalidAnswerError(ValueError):
    pass


@dataclass(frozen=True)
class Question:
    id: str
    kind: Kind
    provides: Fact
    options: tuple[str, ...] = ()
    ask_if: Callable[[Answers], bool] = field(default=lambda _a: True)


def _yes(qid: str) -> Callable[[Answers], bool]:
    return lambda a: a.get(qid) is True


def _single_parent_applies(a: Answers) -> bool:
    return a.get("has_children") is True and a.get("marital_status") not in (None, "married")


ALL_QUESTIONS: tuple[Question, ...] = (
    Question("resident", "yes_no", Fact.RESIDENT),
    Question("sex", "choice", Fact.SEX, options=("female", "male")),
    Question(
        "marital_status",
        "choice",
        Fact.MARITAL_STATUS,
        options=("single", "married", "divorced", "widowed", "separated"),
    ),
    Question("has_children", "yes_no", Fact.CHILDREN),
    Question("children_birth_dates", "dates", Fact.CHILDREN, ask_if=_yes("has_children")),
    Question("single_parent", "yes_no", Fact.SINGLE_PARENT, ask_if=_single_parent_applies),
    Question("has_degree", "yes_no", Fact.DEGREES),
    Question("degree_years", "years", Fact.DEGREES, ask_if=_yes("has_degree")),
    Question("discharged", "yes_no", Fact.DISCHARGE),
    Question("discharge_date", "date", Fact.DISCHARGE, ask_if=_yes("discharged")),
    Question("aliyah", "yes_no", Fact.ALIYAH),
    Question("aliyah_date", "date", Fact.ALIYAH, ask_if=_yes("aliyah")),
    Question("disability", "yes_no", Fact.DISABILITY),
    Question("multiple_employers", "yes_no", Fact.MULTIPLE_EMPLOYER_YEARS),
    Question(
        "multiple_employer_years",
        "window_years",
        Fact.MULTIPLE_EMPLOYER_YEARS,
        ask_if=_yes("multiple_employers"),
    ),
    Question("partial_year", "yes_no", Fact.PARTIAL_YEARS),
    Question("partial_years", "window_years", Fact.PARTIAL_YEARS, ask_if=_yes("partial_year")),
    Question("donations", "yes_no", Fact.DONATION_YEARS),
    Question("donation_years", "window_years", Fact.DONATION_YEARS, ask_if=_yes("donations")),
    Question("life_insurance", "yes_no", Fact.LIFE_INSURANCE_YEARS),
    Question(
        "life_insurance_years", "window_years", Fact.LIFE_INSURANCE_YEARS, ask_if=_yes("life_insurance")
    ),
    Question("pension_self", "yes_no", Fact.PENSION_SELF_YEARS),
    Question("pension_self_years", "window_years", Fact.PENSION_SELF_YEARS, ask_if=_yes("pension_self")),
    Question("localities", "localities", Fact.LOCALITIES),
)

# Registry-driven: drop questions whose fact no rule needs.
QUESTIONS: tuple[Question, ...] = tuple(q for q in ALL_QUESTIONS if q.provides in required_facts())
QUESTIONS_BY_ID: dict[str, Question] = {q.id: q for q in QUESTIONS}


# --- validation ---------------------------------------------------------------------------------------------


def _parse_date(raw: Any, today: date) -> date:
    if not isinstance(raw, str):
        raise InvalidAnswerError("date must be a string")
    try:
        value = date.fromisoformat(raw)
    except ValueError:
        raise InvalidAnswerError("bad date") from None
    if value > today or value.year < MIN_YEAR:
        raise InvalidAnswerError("date out of range")
    return value


def _year_list(raw: Any, allowed: Callable[[int], bool]) -> list[int]:
    if not isinstance(raw, list) or not raw or len(raw) > MAX_LIST:
        raise InvalidAnswerError("expected a non-empty list")
    years: set[int] = set()
    for y in raw:
        if not isinstance(y, int) or isinstance(y, bool) or not allowed(y):
            raise InvalidAnswerError("year out of range")
        years.add(y)
    return sorted(years)


def validate(question: Question, raw: Any, today: date) -> Any:
    """Return the normalized answer or raise InvalidAnswerError."""
    match question.kind:
        case "yes_no":
            if not isinstance(raw, bool):
                raise InvalidAnswerError("expected true/false")
            return raw
        case "choice":
            if raw not in question.options:
                raise InvalidAnswerError("unknown option")
            return raw
        case "date":
            return _parse_date(raw, today).isoformat()
        case "dates":
            if not isinstance(raw, list) or not raw or len(raw) > MAX_LIST:
                raise InvalidAnswerError("expected a non-empty list")
            return sorted(_parse_date(d, today).isoformat() for d in raw)
        case "years":
            return _year_list(raw, lambda y: MIN_YEAR <= y <= today.year)
        case "window_years":
            window = refund_window(today)
            return _year_list(raw, lambda y: y in window)
        case "localities":
            if not isinstance(raw, list) or not raw or len(raw) > MAX_LIST:
                raise InvalidAnswerError("expected a non-empty list")
            out = []
            for item in raw:
                if not isinstance(item, dict):
                    raise InvalidAnswerError("expected objects")
                name = item.get("name")
                from_year, to_year = item.get("from_year"), item.get("to_year")
                if not isinstance(name, str) or not 1 <= len(name.strip()) <= 80:
                    raise InvalidAnswerError("bad locality name")
                if not isinstance(from_year, int) or not MIN_YEAR <= from_year <= today.year:
                    raise InvalidAnswerError("bad from_year")
                if to_year is not None and (
                    not isinstance(to_year, int) or not from_year <= to_year <= today.year
                ):
                    raise InvalidAnswerError("bad to_year")
                out.append({"name": name.strip(), "from_year": from_year, "to_year": to_year})
            return sorted(out, key=lambda p: (p["from_year"], p["name"]))
    raise InvalidAnswerError("unknown kind")  # pragma: no cover


# --- flow ---------------------------------------------------------------------------------------------------


def applicable(answers: Answers) -> list[Question]:
    return [q for q in QUESTIONS if q.ask_if(answers)]


def effective_answers(answers: Answers) -> Answers:
    """Drop answers to questions that no longer apply (e.g. children dates after answering 'no children')."""
    effective: Answers = {}
    for q in QUESTIONS:
        if q.ask_if(effective) and q.id in answers:
            effective[q.id] = answers[q.id]
    return effective


def next_question(answers: Answers) -> Question | None:
    effective = effective_answers(answers)
    for q in QUESTIONS:
        if q.ask_if(effective) and q.id not in effective:
            return q
    return None


# --- derivation ---------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class EventSpec:
    type: LifeEventType
    date_from: date
    date_to: date | None = None
    data: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Derived:
    resident: bool | None
    sex: str | None
    marital_status: str | None
    single_parent: bool
    disability: bool
    events: list[EventSpec]


def _year_event(kind: LifeEventType, year: int) -> EventSpec:
    return EventSpec(kind, date(year, 1, 1), date(year, 12, 31))


YEAR_LIST_EVENTS: dict[str, LifeEventType] = {
    "multiple_employer_years": LifeEventType.MULTIPLE_EMPLOYERS,
    "partial_years": LifeEventType.PARTIAL_YEAR,
    "donation_years": LifeEventType.DONATION,
    "life_insurance_years": LifeEventType.LIFE_INSURANCE,
    "pension_self_years": LifeEventType.PENSION_SELF,
}


def derive(answers: Answers) -> Derived:
    a = effective_answers(answers)
    events: list[EventSpec] = [
        EventSpec(LifeEventType.CHILD_BIRTH, date.fromisoformat(d)) for d in a.get("children_birth_dates", [])
    ]
    events += [_year_event(LifeEventType.DEGREE_COMPLETED, y) for y in a.get("degree_years", [])]
    if "discharge_date" in a:
        events.append(EventSpec(LifeEventType.DISCHARGE, date.fromisoformat(a["discharge_date"])))
    if "aliyah_date" in a:
        events.append(EventSpec(LifeEventType.ALIYAH, date.fromisoformat(a["aliyah_date"])))
    for qid, kind in YEAR_LIST_EVENTS.items():
        events += [_year_event(kind, y) for y in a.get(qid, [])]
    for p in a.get("localities", []):
        to = date(p["to_year"], 12, 31) if p["to_year"] is not None else None
        events.append(EventSpec(LifeEventType.LOCALITY, date(p["from_year"], 1, 1), to, {"name": p["name"]}))
    return Derived(
        resident=a.get("resident"),
        sex=a.get("sex"),
        marital_status=a.get("marital_status"),
        single_parent=a.get("single_parent") is True,
        disability=a.get("disability") is True,
        events=sorted(events, key=lambda e: (e.date_from, e.type)),
    )


def to_screening_input(
    *,
    resident: bool | None,
    sex: str | None,
    marital_status: str | None,
    single_parent: bool,
    disability: bool,
    events: list[EventSpec],
) -> ScreeningInput:
    """Build the engine's input from profile fields and life events (from any source)."""

    def years(kind: LifeEventType) -> list[int]:
        return sorted({e.date_from.year for e in events if e.type == kind})

    def first_date(kind: LifeEventType) -> date | None:
        dates = [e.date_from for e in events if e.type == kind]
        return min(dates) if dates else None

    return ScreeningInput(
        resident=resident,
        sex=sex if sex in ("female", "male") else None,
        marital_status=marital_status,
        single_parent=single_parent,
        disability=disability,
        child_birth_dates=sorted(e.date_from for e in events if e.type == LifeEventType.CHILD_BIRTH),
        degree_completion_years=years(LifeEventType.DEGREE_COMPLETED),
        discharge_date=first_date(LifeEventType.DISCHARGE),
        aliyah_date=first_date(LifeEventType.ALIYAH),
        multiple_employer_years=years(LifeEventType.MULTIPLE_EMPLOYERS),
        partial_years=years(LifeEventType.PARTIAL_YEAR),
        donation_years=years(LifeEventType.DONATION),
        life_insurance_years=years(LifeEventType.LIFE_INSURANCE),
        pension_self_years=years(LifeEventType.PENSION_SELF),
        localities=[
            LocalityPeriod(
                name=str(e.data.get("name", "")),
                from_year=e.date_from.year,
                to_year=e.date_to.year if e.date_to else None,
            )
            for e in events
            if e.type == LifeEventType.LOCALITY
        ],
    )
