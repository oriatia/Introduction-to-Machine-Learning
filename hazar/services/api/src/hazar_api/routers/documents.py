from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from hazar_api import audit
from hazar_api.deps import CurrentUser, DbSession
from hazar_api.documents import (
    EXTRACT_JOB,
    UPLOADABLE_TYPES,
    JobQueue,
    build_checklist,
    sha256,
    sniff_content_type,
    upsert_income_source,
)
from hazar_api.extraction import CONFIDENCE_THRESHOLD, FIELDS_BY_DOC_TYPE, normalize_confirmed
from hazar_api.models import Document, DocumentStatus, User
from hazar_api.routers.questionnaire import Today, compute_estimate
from hazar_api.vault import DocumentVault
from hazar_tax_engine import refund_window

router = APIRouter(prefix="/api/documents", tags=["documents"])
UPLOAD_HEADER = "x-hazar-upload"


class FieldOut(BaseModel):
    name: str
    kind: str
    form_code: str | None
    value: str | None
    confidence: float
    needs_attention: bool


class DocumentOut(BaseModel):
    id: uuid.UUID
    type: str
    tax_year: int | None
    status: str
    content_type: str
    size_bytes: int
    created_at: datetime
    error: str | None
    extractor: str | None = None
    fields: list[FieldOut] = Field(default_factory=list)
    confirmed: dict[str, Any] | None = None
    file_url: str | None = None


def _out(doc: Document, *, detail: bool = False, file_url: str | None = None) -> DocumentOut:
    out = DocumentOut(
        id=doc.id,
        type=doc.type,
        tax_year=doc.tax_year,
        status=doc.status,
        content_type=doc.content_type,
        size_bytes=doc.size_bytes,
        created_at=doc.created_at,
        error=doc.error,
        extractor=doc.extractor,
        confirmed=doc.confirmed,
        file_url=file_url,
    )
    if detail:
        extracted = (doc.extraction or {}).get("fields", {})
        for spec in FIELDS_BY_DOC_TYPE.get(doc.type, ()):
            item = extracted.get(spec.name, {})
            confidence = float(item.get("confidence", 0.0))
            value = item.get("value")
            out.fields.append(
                FieldOut(
                    name=spec.name,
                    kind=spec.kind,
                    form_code=spec.form_code,
                    value=value,
                    confidence=confidence,
                    needs_attention=value is None or confidence < CONFIDENCE_THRESHOLD,
                )
            )
    return out


async def _own(db: DbSession, user: User, document_id: uuid.UUID) -> Document:
    doc = await db.get(Document, document_id)
    if doc is None or doc.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="not_found")
    return doc


@router.post("", status_code=status.HTTP_201_CREATED, response_model=DocumentOut)
async def upload(
    request: Request,
    user: CurrentUser,
    db: DbSession,
    today: Today,
    file: Annotated[UploadFile, File()],
    type: Annotated[str, Form(max_length=32)],
    tax_year: Annotated[int | None, Form()] = None,
) -> DocumentOut:
    if request.headers.get(UPLOAD_HEADER) != "1":
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="missing_upload_header")
    if type not in UPLOADABLE_TYPES:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail="bad_type")
    if tax_year is not None and tax_year not in refund_window(today):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail="bad_year")
    limit: int = request.app.state.settings.max_upload_bytes
    data = await file.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, detail="too_large")
    content_type = sniff_content_type(data)
    if content_type is None:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="unsupported_file")

    vault: DocumentVault = request.app.state.vault
    object_key = await vault.put(db, user.id, data, content_type)
    extractable = type in FIELDS_BY_DOC_TYPE
    doc = Document(
        user_id=user.id,
        type=type,
        tax_year=tax_year,
        object_key=object_key,
        content_type=content_type,
        size_bytes=len(data),
        sha256=sha256(data),
        status=(DocumentStatus.EXTRACTING if extractable else DocumentStatus.NEEDS_REVIEW).value,
        created_at=datetime.now(UTC),
    )
    db.add(doc)
    await db.flush()
    await audit.record(
        db, "document.upload", actor_id=user.id, target=f"document:{doc.id}", details={"type": type}
    )
    # Commit before enqueueing so the worker can see the row.
    await db.commit()
    if extractable:
        queue: JobQueue = request.app.state.jobs
        await queue.enqueue(EXTRACT_JOB, str(doc.id))
    return _out(doc)


@router.get("", response_model=list[DocumentOut])
async def list_documents(user: CurrentUser, db: DbSession) -> list[DocumentOut]:
    rows = await db.scalars(
        select(Document).where(Document.user_id == user.id).order_by(Document.created_at.desc())
    )
    return [_out(d) for d in rows]


class ChecklistItemOut(BaseModel):
    doc_type: str
    year: int
    reasons: list[str]
    status: str


@router.get("/checklist", response_model=list[ChecklistItemOut])
async def checklist(user: CurrentUser, db: DbSession, today: Today) -> list[ChecklistItemOut]:
    estimate = await compute_estimate(db, user, today, audit_run=False)
    docs = list(await db.scalars(select(Document).where(Document.user_id == user.id)))
    return [ChecklistItemOut(**vars(i)) for i in build_checklist(estimate, docs, today)]


@router.get("/{document_id}", response_model=DocumentOut)
async def get_document(
    document_id: uuid.UUID, request: Request, user: CurrentUser, db: DbSession
) -> DocumentOut:
    doc = await _own(db, user, document_id)
    vault: DocumentVault = request.app.state.vault
    ttl: int = request.app.state.settings.file_url_ttl_seconds
    await audit.record(db, "document.read", actor_id=user.id, target=f"document:{doc.id}")
    return _out(doc, detail=True, file_url=f"/api/files/{vault.signed_token(user.id, doc.object_key, ttl)}")


class ConfirmIn(BaseModel):
    tax_year: int | None = None
    fields: dict[str, str | int | float | None] = Field(default_factory=dict)


@router.post("/{document_id}/confirm", response_model=DocumentOut)
async def confirm(
    document_id: uuid.UUID, body: ConfirmIn, user: CurrentUser, db: DbSession, today: Today
) -> DocumentOut:
    doc = await _own(db, user, document_id)
    if doc.status not in (DocumentStatus.NEEDS_REVIEW, DocumentStatus.CONFIRMED, DocumentStatus.FAILED):
        raise HTTPException(status.HTTP_409_CONFLICT, detail="not_ready")
    window = refund_window(today)
    if doc.type in FIELDS_BY_DOC_TYPE:
        try:
            values = normalize_confirmed(doc.type, dict(body.fields), window)
        except ValueError as err:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT, detail=f"invalid_field:{err}"
            ) from None
        doc.tax_year = int(values["tax_year"])  # type: ignore[call-overload]
    else:
        if body.tax_year not in window:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail="invalid_field:tax_year")
        values = {"tax_year": body.tax_year}
        doc.tax_year = body.tax_year
    doc.confirmed = values
    doc.confirmed_at = datetime.now(UTC)
    doc.status = DocumentStatus.CONFIRMED.value
    if doc.type == "form_106":
        await upsert_income_source(db, doc, values)
    await audit.record(db, "document.confirm", actor_id=user.id, target=f"document:{doc.id}")
    return _out(doc, detail=True)


@router.post("/{document_id}/retry", response_model=DocumentOut)
async def retry(document_id: uuid.UUID, request: Request, user: CurrentUser, db: DbSession) -> DocumentOut:
    doc = await _own(db, user, document_id)
    if doc.status != DocumentStatus.FAILED or doc.type not in FIELDS_BY_DOC_TYPE:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="not_failed")
    doc.status, doc.error = DocumentStatus.EXTRACTING.value, None
    await db.commit()
    queue: JobQueue = request.app.state.jobs
    await queue.enqueue(EXTRACT_JOB, str(doc.id))
    return _out(doc)


@router.post("/{document_id}/delete", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(document_id: uuid.UUID, request: Request, user: CurrentUser, db: DbSession) -> None:
    doc = await _own(db, user, document_id)
    vault: DocumentVault = request.app.state.vault
    await vault.delete(user.id, doc.object_key)
    await db.delete(doc)  # its IncomeSource goes with it (ON DELETE CASCADE)
    await audit.record(db, "document.delete", actor_id=user.id, target=f"document:{document_id}")
