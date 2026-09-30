from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response, status

from hazar_api import audit
from hazar_api.deps import CurrentUser, DbSession
from hazar_api.storage import ObjectNotFoundError
from hazar_api.vault import DocumentVault, InvalidFileTokenError

router = APIRouter(prefix="/api/files", tags=["files"])


@router.get("/{token}")
async def download(token: str, request: Request, user: CurrentUser, db: DbSession) -> Response:
    """Serve a decrypted file for a valid, unexpired token. The token must belong to the caller.

    Advisor access to users' files is added with the back office (Sprint 6), with its own audit.
    """
    vault: DocumentVault = request.app.state.vault
    try:
        grant = vault.verify_token(token)
    except InvalidFileTokenError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="not_found") from None
    if grant.user_id != user.id:
        await audit.record(db, "document.denied", actor_id=user.id, target=grant.object_key)
        await db.commit()
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="not_found")
    try:
        obj = await vault.get(db, user.id, grant.object_key)
    except ObjectNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="not_found") from None
    await audit.record(db, "document.read", actor_id=user.id, target=grant.object_key)
    return Response(
        obj.data,
        media_type=obj.content_type,
        headers={"Content-Disposition": "attachment", "Cache-Control": "private, no-store"},
    )
