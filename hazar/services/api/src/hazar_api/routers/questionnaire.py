from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from hazar_api import audit
from hazar_api.deps import CurrentUser, DbSession
from hazar_api.models import LifeEvent, LifeEventSource, LifeEventType, Profile, QuestionnaireAnswer, User
from hazar_api.questionnaire import (
    QUESTIONS_BY_ID,
    EventSpec,
    InvalidAnswerError,
    Question,
    applicable,
    derive,
    effective_answers,
    next_question,
    to_screening_input,
    validate,
)
from hazar_tax_engine import ENGINE_VERSION, ScreeningResult, refund_window, screen

router = APIRouter(prefix="/api", tags=["questionnaire"])


def get_today(request: Request) -> date:
    """Israel-local date. Tests override app.state.today."""
    today: date = request.app.state.today()
    return today


Today = Annotated[date, Depends(get_today)]


class QuestionOut(BaseModel):
    id: str
    kind: str
    options: list[str] = Field(default_factory=list)
    window: list[int] = Field(default_factory=list)

    @classmethod
    def of(cls, q: Question, today: date) -> QuestionOut:
        window = refund_window(today) if q.kind == "window_years" else []
        return cls(id=q.id, kind=q.kind, options=list(q.options), window=window)


class AnsweredOut(BaseModel):
    id: str
    kind: str
    value: Any


class QuestionnaireState(BaseModel):
    next: QuestionOut | None
    answered: list[AnsweredOut]
    total: int
    complete: bool


class AnswerIn(BaseModel):
    question_id: str = Field(max_length=64)
    value: Any


async def _answers(db: AsyncSession, user: User) -> dict[str, QuestionnaireAnswer]:
    rows = await db.scalars(select(QuestionnaireAnswer).where(QuestionnaireAnswer.user_id == user.id))
    return {r.question_id: r for r in rows}


def _state(answers: dict[str, Any], today: date) -> QuestionnaireState:
    effective = effective_answers(answers)
    nxt = next_question(effective)
    answered = [
        AnsweredOut(id=qid, kind=QUESTIONS_BY_ID[qid].kind, value=value) for qid, value in effective.items()
    ]
    return QuestionnaireState(
        next=QuestionOut.of(nxt, today) if nxt else None,
        answered=answered,
        total=len(applicable(effective)),
        complete=nxt is None,
    )


async def _sync(db: AsyncSession, user: User, rows: dict[str, QuestionnaireAnswer]) -> dict[str, Any]:
    """Drop answers that no longer apply, then re-derive profile + questionnaire life events (ADR 0003 §5)."""
    raw = {qid: r.value for qid, r in rows.items()}
    effective = effective_answers(raw)
    for qid, row in rows.items():
        if qid not in effective:
            await db.delete(row)

    derived = derive(effective)
    profile = await db.get(Profile, user.id)
    if profile is None:
        profile = Profile(user_id=user.id)
        db.add(profile)
    profile.resident = derived.resident
    profile.sex = derived.sex
    profile.marital_status = derived.marital_status
    profile.single_parent = derived.single_parent
    profile.disability = derived.disability

    await db.execute(
        delete(LifeEvent).where(
            LifeEvent.user_id == user.id, LifeEvent.source == LifeEventSource.QUESTIONNAIRE.value
        )
    )
    for e in derived.events:
        db.add(
            LifeEvent(
                user_id=user.id,
                type=e.type.value,
                date_from=e.date_from,
                date_to=e.date_to,
                data=e.data,
                source=LifeEventSource.QUESTIONNAIRE.value,
            )
        )
    await db.flush()
    return effective


@router.get("/questionnaire", response_model=QuestionnaireState)
async def get_questionnaire(user: CurrentUser, db: DbSession, today: Today) -> QuestionnaireState:
    rows = await _answers(db, user)
    return _state({q: r.value for q, r in rows.items()}, today)


@router.post("/questionnaire/answers", response_model=QuestionnaireState)
async def answer(body: AnswerIn, user: CurrentUser, db: DbSession, today: Today) -> QuestionnaireState:
    question = QUESTIONS_BY_ID.get(body.question_id)
    rows = await _answers(db, user)
    current = effective_answers({q: r.value for q, r in rows.items()})
    if question is None or not question.ask_if(current):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail="unknown_question")
    try:
        value = validate(question, body.value, today)
    except InvalidAnswerError:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail="invalid_answer") from None

    row = rows.get(question.id)
    if row is None:
        row = QuestionnaireAnswer(
            user_id=user.id, question_id=question.id, value=value, answered_at=datetime.now(UTC)
        )
        db.add(row)
        rows[question.id] = row
    else:
        row.value = value
        row.answered_at = datetime.now(UTC)
    await db.flush()
    effective = await _sync(db, user, rows)
    # No answer values in the audit log: they are personal data.
    await audit.record(db, "questionnaire.answer", actor_id=user.id, target=f"question:{question.id}")
    return _state(effective, today)


@router.post("/questionnaire/undo", response_model=QuestionnaireState)
async def undo(user: CurrentUser, db: DbSession, today: Today) -> QuestionnaireState:
    rows = await _answers(db, user)
    effective = effective_answers({q: r.value for q, r in rows.items()})
    if effective:
        last = max((rows[q] for q in effective), key=lambda r: r.answered_at)
        await db.delete(last)
        del rows[last.question_id]
        await db.flush()
        effective = await _sync(db, user, rows)
        await audit.record(db, "questionnaire.undo", actor_id=user.id, target=f"question:{last.question_id}")
    return _state(effective, today)


class ProfileOut(BaseModel):
    resident: bool | None
    sex: str | None
    marital_status: str | None
    single_parent: bool
    disability: bool


class LifeEventOut(BaseModel):
    type: str
    date_from: date
    date_to: date | None
    data: dict[str, Any]
    source: str


class TimelineOut(BaseModel):
    profile: ProfileOut | None
    events: list[LifeEventOut]


async def _events(db: AsyncSession, user: User) -> list[LifeEvent]:
    rows = await db.scalars(
        select(LifeEvent).where(LifeEvent.user_id == user.id).order_by(LifeEvent.date_from, LifeEvent.type)
    )
    return list(rows)


@router.get("/timeline", response_model=TimelineOut)
async def timeline(user: CurrentUser, db: DbSession) -> TimelineOut:
    profile = await db.get(Profile, user.id)
    events = await _events(db, user)
    await audit.record(db, "profile.read", actor_id=user.id, target=f"user:{user.id}")
    return TimelineOut(
        profile=ProfileOut.model_validate(profile, from_attributes=True) if profile else None,
        events=[LifeEventOut.model_validate(e, from_attributes=True) for e in events],
    )


class EstimateOut(ScreeningResult):
    engine_version: str


@router.get("/estimate", response_model=EstimateOut)
async def estimate(user: CurrentUser, db: DbSession, today: Today) -> EstimateOut:
    """Which benefits may apply, per year. Relevance only, no amounts until tables are verified (ADR 0003)."""
    rows = await _answers(db, user)
    if next_question({q: r.value for q, r in rows.items()}) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="questionnaire_incomplete")
    profile = await db.get(Profile, user.id)
    events = [
        EventSpec(LifeEventType(e.type), e.date_from, e.date_to, e.data) for e in await _events(db, user)
    ]
    facts = to_screening_input(
        resident=profile.resident if profile else None,
        sex=profile.sex if profile else None,
        marital_status=profile.marital_status if profile else None,
        single_parent=profile.single_parent if profile else False,
        disability=profile.disability if profile else False,
        events=events,
    )
    result = screen(facts, today)
    await audit.record(
        db,
        "estimate.run",
        actor_id=user.id,
        details={"findings": len(result.findings), "engine": ENGINE_VERSION},
    )
    return EstimateOut(**result.model_dump(), engine_version=ENGINE_VERSION)
