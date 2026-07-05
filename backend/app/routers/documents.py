"""Dokumente: Web-Ansicht (JSON) + PDF-Download (WeasyPrint, Inexxio-Design).

- ``GET /documents/{object_id}``        – eingefrorenes Dokument (Meta + Inhalt) für die Ansicht.
- ``GET /documents/{object_id}/pdf``    – das eingefrorene Dokument als A4-PDF.
- ``GET /steps/{step_id}/document/pdf`` – **Entwurfs-Vorschau**: die Vorlage eines Prozessschritts
  als PDF, bevor sie bei der Freigabe eingefroren wird (Layout prüfen).
"""

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from ..core.auth import require_employee
from ..core.database import get_db
from ..models import ArticleProcessStep, CompanySettings, UserProfile
from ..schemas.document import DocumentResponse
from ..services import document as document_svc
from ..services.document_render import render_pdf

router = APIRouter(prefix="/api/v1/erp", tags=["documents"])


def _company(db: Session) -> dict:
    s = db.query(CompanySettings).filter(CompanySettings.id == 1).first()
    if not s:
        return {"company_name": "Inexxio"}
    return {
        "company_name": s.company_name or "Inexxio",
        "email": s.email,
        "street": s.street,
        "zip_code": s.zip_code,
        "city": s.city,
    }


def _pdf_response(pdf: bytes, filename: str) -> Response:
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )


@router.get("/documents/{object_id}", response_model=DocumentResponse)
async def get_document(
    object_id: int,
    db: Session = Depends(get_db),
    _: UserProfile = Depends(require_employee),
):
    doc = document_svc.get_by_object_id(db, object_id)
    resp = DocumentResponse.model_validate(doc)
    resp.order_object_id = document_svc.order_object_id(db, doc)
    resp.article_object_id = document_svc.article_object_id(db, doc)
    return resp


@router.get("/documents/{object_id}/pdf")
async def get_document_pdf(
    object_id: int,
    db: Session = Depends(get_db),
    _: UserProfile = Depends(require_employee),
):
    doc = document_svc.get_by_object_id(db, object_id)
    pdf = render_pdf(
        document_svc.normalize_content(doc.content),
        company=_company(db), object_id=doc.object_id,
        issued_at=doc.issued_at, version=doc.version,
    )
    return _pdf_response(pdf, f"Dokument-{str(doc.object_id).zfill(9)}.pdf")


@router.get("/steps/{step_id}/document/pdf")
async def get_step_document_pdf(
    step_id: int,
    db: Session = Depends(get_db),
    _: UserProfile = Depends(require_employee),
):
    """Entwurfs-Vorschau der Dokument-Vorlage eines Prozessschritts (noch nicht eingefroren)."""
    step = db.query(ArticleProcessStep).filter(
        ArticleProcessStep.id == step_id, ArticleProcessStep.is_active == True).first()
    if not step or step.step_type != "document":
        raise HTTPException(404, detail="Dokument-Schritt nicht gefunden")
    pdf = render_pdf(
        document_svc.normalize_content(step.document_content),
        company=_company(db), object_id=None, issued_at=None, version=1,
    )
    return _pdf_response(pdf, "Dokument-Entwurf.pdf")
