"""Document service: upload sniffing, extraction runs, confirmation, and the personal checklist (ADR 0004)."""

from __future__ import annotations

import hashlib
import logging
import uuid
from dataclasses import dataclass
from datetime import date
from typing import Any, Literal, Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from hazar_api.extraction import ExtractionError, Extractor
from hazar_api.models import Document, DocumentStatus, IncomeSource
from hazar_api.vault import DocumentVault
from hazar_tax_engine import DocumentType, ScreeningResult, refund_window

logger = logging.getLogger(__name__)

UPLOADABLE_TYPES = {t.value for t in DocumentType}
EXTRACT_JOB = "extract_document"


class JobQueue(Protocol):
    async def enqueue(self, job: str, *args: Any) -> None: ...


class ArqQueue:
    def __init__(self, pool: Any) -> None:
        self._pool = pool

    async def enqueue(self, job: str, *args: Any) -> None:
        await self._pool.enqueue_job(job, *args)


class RecordingQueue:
    """For tests: remembers jobs instead of running them."""

    def __init__(self) -> None:
        self.jobs: list[tuple[str, tuple[Any, ...]]] = []

    async def enqueue(self, job: str, *args: Any) -> None:
        self.jobs.append((job, args))


def sniff_content_type(data: bytes) -> str | None:
    """Decide the type from magic bytes, never from what the client claims."""
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if data.startswith(b"%PDF-"):
        return "application/pdf"
    return None


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


async def run_extraction(
    sessionmaker: async_sessionmaker[AsyncSession],
    vault: DocumentVault,
    extractor: Extractor,
    document_id: uuid.UUID,
) -> str:
    """Worker body: decrypt, extract, store suggestions, mark for review. Idempotent; returns the status."""
    async with sessionmaker() as db:
        doc = await db.get(Document, document_id)
        if doc is None or doc.status not in (DocumentStatus.EXTRACTING, DocumentStatus.FAILED):
            return doc.status if doc else "missing"
        stored = await vault.get(db, doc.user_id, doc.object_key)
        try:
            result = await extractor.extract(stored.data, stored.content_type, doc.type)
        except ExtractionError as err:
            # Code only: never log document content.
            logger.warning("extraction failed for document %s: %s", doc.id, err.code)
            doc.status, doc.error = DocumentStatus.FAILED.value, err.code
        else:
            doc.extraction = result.model_dump()
            doc.extractor = extractor.name
            doc.status, doc.error = DocumentStatus.NEEDS_REVIEW.value, None
            year = result.fields.get("tax_year")
            if doc.tax_year is None and year and year.value and year.value.isdigit():
                doc.tax_year = int(year.value)
        await db.commit()
        return doc.status


async def upsert_income_source(db: AsyncSession, doc: Document, values: dict[str, Any]) -> None:
    source = await db.scalar(select(IncomeSource).where(IncomeSource.document_id == doc.id))
    if source is None:
        source = IncomeSource(user_id=doc.user_id, document_id=doc.id, tax_year=values["tax_year"])
        db.add(source)
    source.tax_year = values["tax_year"]
    source.employer_name = values.get("employer_name")
    source.employer_file_number = values.get("employer_file_number")
    source.values = {
        k: v for k, v in values.items() if k not in ("tax_year", "employer_name", "employer_file_number")
    }
    await db.flush()


# --- checklist ----------------------------------------------------------------------------------------------

ItemStatus = Literal["missing", "uploaded", "confirmed"]


@dataclass(frozen=True)
class ChecklistItem:
    doc_type: str
    year: int
    reasons: list[str]
    status: ItemStatus


def build_checklist(
    estimate: ScreeningResult | None, documents: list[Document], today: date
) -> list[ChecklistItem]:
    """Documents needed per year: Form 106 for every window year (if you worked), plus what findings need."""
    needed: dict[tuple[str, int], list[str]] = {
        (DocumentType.FORM_106.value, y): ["income"] for y in refund_window(today)
    }
    for finding in estimate.findings if estimate else []:
        for doc_type in finding.documents:
            for year in finding.years:
                needed.setdefault((doc_type.value, year), []).append(finding.rule_id)

    def status(doc_type: str, year: int) -> ItemStatus:
        matching = [d for d in documents if d.type == doc_type and d.tax_year == year]
        if any(d.status == DocumentStatus.CONFIRMED for d in matching):
            return "confirmed"
        return "uploaded" if matching else "missing"

    return [
        ChecklistItem(doc_type=t, year=y, reasons=sorted(set(r)), status=status(t, y))
        for (t, y), r in sorted(needed.items(), key=lambda kv: (kv[0][1], kv[0][0]))
    ]
