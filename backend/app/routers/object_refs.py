"""Generische Rückverweise je Objektnummer («Wer zeigt auf mich?»).

Ein Reiter «Verwendung» für JEDEN ERP-Objekttyp (analog zum generischen
``GET /erp/objects/{id}/documents``): was aktuell an dieser Objektnummer verortet ist
(gehalten/gelagert/enthalten) und welche Prozessschritte sie als Ziel referenzieren.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..core.auth import require_employee
from ..core.database import get_db
from ..models import UserProfile
from ..schemas.instance import ObjectReference
from ..services.references import object_references

router = APIRouter(prefix="/api/v1/erp/objects", tags=["objects"])


@router.get("/{object_id}/references", response_model=list[ObjectReference])
async def list_object_references(
    object_id: int,
    db: Session = Depends(get_db),
    _: UserProfile = Depends(require_employee),
):
    """Verwendung einer Objektnummer: verortete Instanzen + referenzierende Prozessschritte."""
    return [ObjectReference(**r) for r in object_references(db, object_id)]
