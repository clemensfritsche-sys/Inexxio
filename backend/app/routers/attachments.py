"""Foto-/Bild-Uploads. Upload nur für Personal; Auslieferung öffentlich über einen
unerratbaren Token – eine Aufnahme hängt an keinem Datensatz, ihre URL IST der Zugriffsweg
(die Sensitivität ist gering, und der Token ist nicht aufzählbar)."""

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..core.auth import require_employee
from ..core.database import get_db
from ..models import UserProfile
from ..services import attachments as attachments_svc

router = APIRouter(tags=["attachments"])


class UploadResult(BaseModel):
    url: str
    width: int | None = None
    height: int | None = None


@router.post("/api/v1/erp/attachments", response_model=UploadResult, status_code=201)
async def upload_attachment(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: UserProfile = Depends(require_employee),
):
    raw = await file.read()
    att = attachments_svc.store_image(db, raw, file.filename, user.id)
    db.commit()
    return UploadResult(url=attachments_svc.public_url(att), width=att.width, height=att.height)


@router.get("/api/v1/attachments/{token}")
async def serve_attachment(token: str, db: Session = Depends(get_db)):
    att = attachments_svc.get_by_token(db, token)
    return Response(
        content=att.data,
        media_type=att.mime,
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )
