from __future__ import annotations

from typing import Any, get_args

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from hazar_api.deps import DbSession
from hazar_api.models import AuditLog, LifeEvent, Profile, QuestionnaireAnswer

from .conftest import ALL_NO, login


async def answer(client: httpx.AsyncClient, qid: str, value: object) -> httpx.Response:
    return await client.post("/api/questionnaire/answers", json={"question_id": qid, "value": value})


async def answer_all(client: httpx.AsyncClient, overrides: dict[str, object]) -> dict[str, Any]:
    """Answer whatever the API asks next, from ALL_NO + overrides, until complete."""
    answers = dict(ALL_NO, **overrides)
    state: dict[str, Any] = (await client.get("/api/questionnaire")).json()
    while state["next"] is not None:
        qid = state["next"]["id"]
        r = await answer(client, qid, answers[qid])
        assert r.status_code == 200, (qid, r.text)
        state = r.json()
    return state


async def test_requires_login(client: httpx.AsyncClient) -> None:
    assert (await client.get("/api/questionnaire")).status_code == 401
    assert (await client.get("/api/estimate")).status_code == 401
    assert (await client.get("/api/timeline")).status_code == 401


async def test_full_flow_to_estimate(client: httpx.AsyncClient, db: AsyncSession) -> None:
    await login(client)
    state = (await client.get("/api/questionnaire")).json()
    assert state["next"]["id"] == "resident"
    assert state["answered"] == []
    assert (await client.get("/api/estimate")).json() == {"error": "questionnaire_incomplete"}

    state = await answer_all(
        client,
        {
            "has_children": True,
            "children_birth_dates": ["2022-06-01"],
            "donations": True,
            "donation_years": [2023, 2024],
        },
    )
    assert state["complete"] is True
    assert state["total"] == len(state["answered"])

    r = await client.get("/api/estimate")
    assert r.status_code == 200
    body = r.json()
    assert body["is_estimate"] is True
    assert body["window"] == [2020, 2021, 2022, 2023, 2024, 2025]
    rules = {f["rule_id"]: f for f in body["findings"]}
    assert rules["credit.children"]["years"] == [2022, 2023, 2024, 2025]
    assert rules["deduction.donations"]["documents"] == ["donation_receipt"]
    assert all("amount" not in f for f in body["findings"])

    timeline = (await client.get("/api/timeline")).json()
    assert timeline["profile"]["sex"] == "female"
    assert [e["type"] for e in timeline["events"]].count("donation") == 2

    actions = list(await db.scalars(select(AuditLog.action)))
    assert "questionnaire.answer" in actions
    assert "estimate.run" in actions
    # Answer values never reach the audit log.
    for row in await db.scalars(select(AuditLog)):
        assert "2022-06-01" not in str(row.details)


async def test_changing_a_gate_answer_removes_stale_data(client: httpx.AsyncClient, db: AsyncSession) -> None:
    await login(client)
    await answer_all(client, {"has_children": True, "children_birth_dates": ["2022-06-01"]})
    assert await db.scalar(select(LifeEvent).where(LifeEvent.type == "child_birth")) is not None

    state = (await answer(client, "has_children", False)).json()
    assert state["complete"] is True
    assert "children_birth_dates" not in [a["id"] for a in state["answered"]]
    db.expire_all()
    assert await db.scalar(select(LifeEvent).where(LifeEvent.type == "child_birth")) is None


async def test_undo_reopens_last_question(client: httpx.AsyncClient) -> None:
    await login(client)
    await answer(client, "resident", True)
    await answer(client, "sex", "male")
    state = (await client.post("/api/questionnaire/undo", json={})).json()
    assert state["next"]["id"] == "sex"
    assert [a["id"] for a in state["answered"]] == ["resident"]


async def test_rejects_bad_answers(client: httpx.AsyncClient) -> None:
    await login(client)
    r = await answer(client, "resident", "maybe")
    assert r.status_code == 422
    assert r.json() == {"error": "invalid_answer"}
    r = await answer(client, "no_such_question", True)
    assert r.json() == {"error": "unknown_question"}
    # A follow-up whose gate isn't open can't be answered.
    r = await answer(client, "children_birth_dates", ["2022-01-01"])
    assert r.json() == {"error": "unknown_question"}


async def test_users_are_isolated(client: httpx.AsyncClient, db: AsyncSession) -> None:
    await login(client, "0501111111")
    await answer(client, "resident", True)
    await client.post("/api/auth/logout", json={})
    await login(client, "0502222222")
    state = (await client.get("/api/questionnaire")).json()
    assert state["answered"] == []
    assert len(list(await db.scalars(select(Profile)))) == 1


async def test_window_question_lists_window_years(client: httpx.AsyncClient) -> None:
    await login(client)
    state = await answer_all(client, {})
    assert state["complete"]
    r = await answer(client, "donations", True)
    nxt = r.json()["next"]
    assert nxt["id"] == "donation_years"
    assert nxt["kind"] == "window_years"
    assert nxt["window"] == [2020, 2021, 2022, 2023, 2024, 2025]


async def test_writes_are_committed_before_the_response(
    client: httpx.AsyncClient, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    """Regression: the commit ran after the response, so a fast follow-up request (undo → answer) could read
    pre-commit data and fail with StaleDataError. The client must be able to rely on read-your-writes.
    (The in-process test transport waits for the app either way; the scope check below pins the fix.)"""
    assert get_args(DbSession)[1].scope == "function"
    await login(client)
    await answer(client, "resident", True)
    # A brand-new session, opened right after the response, must already see the answer.
    async with sessionmaker() as s:
        assert await s.scalar(
            select(QuestionnaireAnswer.value).where(QuestionnaireAnswer.question_id == "resident")
        )
    await client.post("/api/questionnaire/undo", json={})
    async with sessionmaker() as s:
        assert (
            await s.scalar(select(QuestionnaireAnswer).where(QuestionnaireAnswer.question_id == "resident"))
            is None
        )
    # The exact failing sequence from CI: undo, then immediately answer the same question again.
    r = await answer(client, "resident", False)
    assert r.status_code == 200
