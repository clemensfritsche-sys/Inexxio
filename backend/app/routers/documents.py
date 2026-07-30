"""Dokumente: PDF-Download (WeasyPrint, Inexxio-Design).

``GET /documents/{doc_id}/pdf`` rendert die Dokument-Fachzeile eines Auftrags als A4-PDF.
Nummer (= Instanz-Objektnummer) und Datum (= Instanz-Freigabe) kommen aus der vom Auftrag
erzeugten Instanz; funktioniert für den Entwurf (noch nicht ausgestellt) und das ausgestellte
Dokument gleichermassen (Layout-Vorschau während des Verfassens).
"""

import base64

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from ..core.auth import require_employee
from ..core.database import get_db
from ..models import Order, UserProfile
from ..services import attachments as attachments_svc
from ..services import document as document_svc
from ..services import people
from ..services.objects import obj_nr as format_obj_nr
from ..services.document_render import render_pdf

router = APIRouter(prefix="/api/v1/erp", tags=["documents"])


def _signature_data_uri(db: Session, url: str | None) -> str | None:
    """Eine Unterschrift-Attachment-URL (``/api/v1/attachments/{token}``) in eine data-URI
    auflösen, damit WeasyPrint das Bild ohne Netzwerk/Auth einbetten kann."""
    if not url:
        return None
    token = url.rstrip("/").split("/")[-1]
    try:
        att = attachments_svc.get_by_token(db, token)
    except Exception:
        return None
    return f"data:{att.mime};base64,{base64.b64encode(att.data).decode('ascii')}"


def _signoff_render_data(db: Session, doc) -> list[dict]:
    """Freigabe-Parteien eines Dokuments für den PDF-Freigabe-Block (mit Bild als data-URI)."""
    out: list[dict] = []
    for s in document_svc.signoffs_for(db, doc):
        out.append({
            "name": people.name_by_object_id(db, s.signer_object_id) or f"Objekt {s.signer_object_id}",
            "action": s.action,
            "status": s.status,
            "acted_at": s.acted_at,
            "image": _signature_data_uri(db, s.signature_url) if s.status == "signed" else None,
        })
    return out


def _company(db: Session, order=None) -> dict:
    """Firmen-Briefkopf für das PDF (saubere Anschrift + Logo). Nur Nicht-Geheimes.

    Der Briefkopf ist der der **fakturierenden Gesellschaft** (Seller of Record, ADR 006):
    sie trägt die Rechtsidentität (UID, MWST, Handelsregister), die ein Dokument ausweisen
    muss. Sie wird aus dem Auftrag abgeleitet (``sale.seller_company_for_order``: eingefrorener
    Snapshot ≻ Kundenland ≻ Betreiber). Ohne Auftrag (globaler/entwurfsloser Fall) fällt es auf
    den Betreiber."""
    if order is not None:
        from ..services.sale import seller_company_for_order
        s = seller_company_for_order(db, order)
    else:
        from ..services.sites import find_operator
        s = find_operator(db)
    if not s:
        return {"company_name": "Inexxio"}
    return {
        "company_name": s.company_name or "Inexxio",
        "legal_form": s.legal_form,
        "street": s.street,
        "street_nr": s.street_nr,
        "zip_code": s.zip_code,
        "city": s.city,
        "country": s.country,
        "email": s.email,
        "phone": s.phone,
        "website": s.website,
        "uid_number": s.uid_number,
        "vat_number": s.vat_number,
    }


def _pdf_response(pdf: bytes, filename: str) -> Response:
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )


@router.get("/documents/{doc_id}/pdf")
async def get_document_pdf(
    doc_id: int,
    db: Session = Depends(get_db),
    _: UserProfile = Depends(require_employee),
):
    doc = document_svc.get_by_id(db, doc_id)
    order = db.query(Order).filter(Order.id == doc.order_id).first()
    obj_nr, doc_date = document_svc.render_meta(db, order) if order else (None, None)
    pdf = render_pdf(
        document_svc.normalize_content(doc.content),
        company=_company(db, order), object_id=obj_nr, issued_at=doc_date,
        signoffs=_signoff_render_data(db, doc),
        image_resolver=lambda url: _signature_data_uri(db, url),
    )
    fname = f"Dokument-{format_obj_nr(obj_nr)}.pdf" if obj_nr else "Dokument-Entwurf.pdf"
    return _pdf_response(pdf, fname)
