from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import fakeredis
import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from hazar_api.config import Settings
from hazar_api.documents import RecordingQueue, run_extraction
from hazar_api.extraction import ExtractionError, MockExtractor, make_mock_png
from hazar_api.main import create_app
from hazar_api.models import AuditLog, Document, IncomeSource
from hazar_api.storage import InMemoryObjectStorage

from .conftest import ALL_NO, TODAY, login

H = {"X-Hazar-Upload": "1"}
FIXTURE = make_mock_png(
    {
        "tax_year": ("2023", 0.98),
        "employer_name": ('חברת הדגמה בע"מ', 0.95),
        "employer_file_number": ("912345678", 0.93),
        "months_worked": ("12", 0.97),
        "gross_taxable_income": ("184500", 0.71),
        "tax_withheld": ("21340", 0.92),
        "credit_points": ("2.25", 0.6),
        "pension_employee_deposit": (None, 0.0),
    }
)


class Env:
    def __init__(self, client: httpx.AsyncClient, app: object, queue: RecordingQueue) -> None:
        self.client, self.app, self.queue = client, app, queue

    async def run_jobs(
        self, sessionmaker: async_sessionmaker[AsyncSession], extractor: object = None
    ) -> None:
        for _, (doc_id,) in self.queue.jobs:
            await run_extraction(
                sessionmaker,
                self.app.state.vault,  # type: ignore[attr-defined]
                extractor or MockExtractor(),  # type: ignore[arg-type]
                uuid.UUID(doc_id),
            )
        self.queue.jobs.clear()


@pytest.fixture
async def env(sessionmaker: async_sessionmaker[AsyncSession]) -> AsyncIterator[Env]:
    queue = RecordingQueue()
    app = create_app(
        Settings(env="test", cookie_secure=False, otp_resend_cooldown_seconds=0, max_upload_bytes=50_000),
        redis=fakeredis.FakeAsyncRedis(),
        sessionmaker=sessionmaker,
        storage=InMemoryObjectStorage(),
        jobs=queue,
    )
    app.state.today = lambda: TODAY
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
        await login(c)
        yield Env(c, app, queue)


async def upload(
    c: httpx.AsyncClient, data: bytes, doc_type: str = "form_106", **extra: str
) -> httpx.Response:
    return await c.post(
        "/api/documents",
        files={"file": ("photo.png", data, "image/png")},
        data={"type": doc_type, **extra},
        headers=H,
    )


async def test_upload_extract_review_confirm(
    env: Env, sessionmaker: async_sessionmaker[AsyncSession], db: AsyncSession
) -> None:
    r = await upload(env.client, FIXTURE)
    assert r.status_code == 201, r.text
    doc = r.json()
    assert doc["status"] == "extracting"
    assert env.queue.jobs == [("extract_document", (doc["id"],))]

    await env.run_jobs(sessionmaker)
    detail = (await env.client.get(f"/api/documents/{doc['id']}")).json()
    assert detail["status"] == "needs_review"
    assert detail["tax_year"] == 2023
    fields = {f["name"]: f for f in detail["fields"]}
    assert fields["gross_taxable_income"]["needs_attention"] is True  # 0.71 < 0.9
    assert fields["tax_withheld"]["needs_attention"] is False
    assert fields["pension_employee_deposit"]["needs_attention"] is True  # missing
    assert detail["file_url"].startswith("/api/files/")
    # The signed URL serves the original (decrypted) bytes to the owner.
    assert (await env.client.get(detail["file_url"])).content == FIXTURE

    confirmed = {name: f["value"] for name, f in fields.items()}
    confirmed["gross_taxable_income"] = "185500"  # user corrects a low-confidence value
    r = await env.client.post(f"/api/documents/{doc['id']}/confirm", json={"fields": confirmed})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "confirmed"

    source = await db.scalar(select(IncomeSource))
    assert source is not None
    assert source.tax_year == 2023
    assert source.employer_file_number == "912345678"
    assert source.values["gross_taxable_income"] == 185500
    assert source.values["credit_points"] == 2.25

    actions = list(await db.scalars(select(AuditLog.action)))
    for action in ("document.upload", "document.read", "document.confirm"):
        assert action in actions
    # Field values are not in the audit log.
    assert "185500" not in str(list(await db.scalars(select(AuditLog.details))))


async def test_reconfirm_updates_income_source(
    env: Env, sessionmaker: async_sessionmaker[AsyncSession], db: AsyncSession
) -> None:
    doc_id = (await upload(env.client, FIXTURE)).json()["id"]
    await env.run_jobs(sessionmaker)
    base = {"tax_year": "2023", "tax_withheld": "100"}
    await env.client.post(f"/api/documents/{doc_id}/confirm", json={"fields": base})
    await env.client.post(
        f"/api/documents/{doc_id}/confirm", json={"fields": {**base, "tax_withheld": "200"}}
    )
    rows = list(await db.scalars(select(IncomeSource)))
    assert len(rows) == 1
    assert rows[0].values["tax_withheld"] == 200


async def test_confirm_validation(env: Env, sessionmaker: async_sessionmaker[AsyncSession]) -> None:
    doc_id = (await upload(env.client, FIXTURE)).json()["id"]
    r = await env.client.post(f"/api/documents/{doc_id}/confirm", json={"fields": {"tax_year": "2023"}})
    assert r.status_code == 409  # still extracting
    await env.run_jobs(sessionmaker)
    r = await env.client.post(
        f"/api/documents/{doc_id}/confirm", json={"fields": {"tax_year": "2023", "months_worked": "14"}}
    )
    assert r.status_code == 422
    assert r.json() == {"error": "invalid_field:months_worked"}


async def test_upload_rejections(env: Env) -> None:
    assert (await upload(env.client, b"<html>evil</html>")).json() == {"error": "unsupported_file"}
    assert (await upload(env.client, FIXTURE, doc_type="passport")).json() == {"error": "bad_type"}
    assert (await upload(env.client, FIXTURE, tax_year="2019")).json() == {"error": "bad_year"}
    big = b"\x89PNG\r\n\x1a\n" + b"0" * 60_000
    r = await upload(env.client, big)
    assert r.status_code == 413
    # Without the custom header (e.g. a cross-site form post) the upload is refused.
    r = await env.client.post(
        "/api/documents", files={"file": ("a.png", FIXTURE, "image/png")}, data={"type": "form_106"}
    )
    assert r.status_code == 403
    assert env.queue.jobs == []


async def test_non_extractable_document_needs_year(env: Env) -> None:
    r = await upload(env.client, FIXTURE, doc_type="donation_receipt")
    doc = r.json()
    assert doc["status"] == "needs_review"
    assert env.queue.jobs == []
    r = await env.client.post(f"/api/documents/{doc['id']}/confirm", json={})
    assert r.status_code == 422
    r = await env.client.post(f"/api/documents/{doc['id']}/confirm", json={"tax_year": 2024})
    assert r.json()["status"] == "confirmed"
    assert r.json()["tax_year"] == 2024


async def test_failed_extraction_can_retry(env: Env, sessionmaker: async_sessionmaker[AsyncSession]) -> None:
    class Broken:
        name = "broken"

        async def extract(self, *_: object) -> None:
            raise ExtractionError("rate_limited")

    doc_id = (await upload(env.client, FIXTURE)).json()["id"]
    await env.run_jobs(sessionmaker, Broken())
    detail = (await env.client.get(f"/api/documents/{doc_id}")).json()
    assert detail["status"] == "failed"
    assert detail["error"] == "rate_limited"
    r = await env.client.post(f"/api/documents/{doc_id}/retry", json={})
    assert r.json()["status"] == "extracting"
    await env.run_jobs(sessionmaker)
    assert (await env.client.get(f"/api/documents/{doc_id}")).json()["status"] == "needs_review"


async def test_documents_are_private(env: Env, sessionmaker: async_sessionmaker[AsyncSession]) -> None:
    doc_id = (await upload(env.client, FIXTURE)).json()["id"]
    await env.client.post("/api/auth/logout", json={})
    await login(env.client, "0509999999")
    assert (await env.client.get(f"/api/documents/{doc_id}")).status_code == 404
    assert (await env.client.post(f"/api/documents/{doc_id}/delete", json={})).status_code == 404
    assert (await env.client.get("/api/documents")).json() == []


async def test_delete(env: Env, sessionmaker: async_sessionmaker[AsyncSession], db: AsyncSession) -> None:
    doc_id = (await upload(env.client, FIXTURE)).json()["id"]
    await env.run_jobs(sessionmaker)
    await env.client.post(f"/api/documents/{doc_id}/confirm", json={"fields": {"tax_year": "2023"}})
    storage: InMemoryObjectStorage = env.app.state.storage  # type: ignore[attr-defined]
    assert len(storage.objects) == 1
    assert (await env.client.post(f"/api/documents/{doc_id}/delete", json={})).status_code == 204
    assert storage.objects == {}
    assert await db.scalar(select(Document)) is None
    assert await db.scalar(select(IncomeSource)) is None


async def test_checklist(env: Env, sessionmaker: async_sessionmaker[AsyncSession]) -> None:
    items = (await env.client.get("/api/documents/checklist")).json()
    # Questionnaire not done yet: Form 106 for every window year.
    assert [(i["doc_type"], i["year"]) for i in items] == [("form_106", y) for y in range(2020, 2026)]

    answers = dict(ALL_NO, donations=True, donation_years=[2023])
    state = (await env.client.get("/api/questionnaire")).json()
    while state["next"]:
        qid = state["next"]["id"]
        state = (
            await env.client.post(
                "/api/questionnaire/answers", json={"question_id": qid, "value": answers[qid]}
            )
        ).json()

    doc_id = (await upload(env.client, FIXTURE)).json()["id"]
    await env.run_jobs(sessionmaker)
    await env.client.post(f"/api/documents/{doc_id}/confirm", json={"fields": {"tax_year": "2023"}})

    items = {(i["doc_type"], i["year"]): i for i in (await env.client.get("/api/documents/checklist")).json()}
    assert items[("form_106", 2023)]["status"] == "confirmed"
    assert items[("form_106", 2022)]["status"] == "missing"
    assert items[("donation_receipt", 2023)]["reasons"] == ["deduction.donations"]
    assert items[("donation_receipt", 2023)]["status"] == "missing"
