"""Der Korb nach aussen. Hochladen (nur Personal) gibt es nur noch für ein Bild, das kein
Dokument ist – die gezeichnete Unterschrift; jede andere Datei wird ein Dokument
(``routers/documents``). Ausgeliefert wird über einen unerratbaren Token."""

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
    #: Die Nummer des Bildes; die ``url`` ist, wie man es zeigt.
    id: int
    url: str
    width: int | None = None
    height: int | None = None


@router.post("/api/v1/erp/attachments", response_model=UploadResult, status_code=201)
def upload_attachment(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: UserProfile = Depends(require_employee),
):
    raw = file.file.read()
    att = attachments_svc.store_image(db, raw, file.filename, user.id)
    db.commit()
    return UploadResult(id=att.id, url=attachments_svc.public_url(att), width=att.width, height=att.height)


@router.get("/api/v1/attachments/{token}")
def serve_attachment(token: str, db: Session = Depends(get_db)):
    att = attachments_svc.get_by_token(db, token)
    return Response(content=attachments_svc.bytes_of(att), media_type=att.mime,
                    headers=attachments_svc.serve_headers(att))


@router.get("/api/v1/attachments/{token}/preview")
def serve_preview(token: str, db: Session = Depends(get_db)):
    """**Das Vorschaubild** – abgeleitet aus der Datei, bei jedem Abruf neu (der Browser hält
    es fest, die Datei ändert sich nie). Gibt es keins, 404 – die Kachel zeigt die Sorte."""
    from ..services import documents as docs
    att = attachments_svc.get_by_token(db, token)
    png = docs.preview_png(attachments_svc.bytes_of(att), att.mime)
    if png is None:
        from fastapi import HTTPException
        raise HTTPException(404, detail="Kein Vorschaubild")
    return Response(content=png, media_type="image/png",
                    headers={"Cache-Control": "public, max-age=31536000, immutable",
                             "X-Content-Type-Options": "nosniff"})
