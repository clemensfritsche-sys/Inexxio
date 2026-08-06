"""Datenerfassung – erfasst wird an der **Einzelinstanz**, sonst nirgends.

Die Maske steht am Artikel (``articles.capture_fields``), die Werte an der Einzelinstanz.
Eine Erfassung hat heute keine Folgen: sie hält fest, was gemessen wurde. Was daraus
folgt, entscheidet die neue Prozesslogik – die gibt es noch nicht.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..core.auth import require_employee
from ..core.database import get_db
from ..models import Article, Instance, InstanceUnit, UserProfile
from ..schemas.instance import CaptureCreate, CaptureResponse
from ..services import capture as capture_svc
from ..services import instances as inst_svc

router = APIRouter(prefix="/api/v1/erp/captures", tags=["captures"])


def _resolve(db: Session, number: str) -> tuple[Instance, InstanceUnit, Article]:
    """``100000123-7`` → (Instanz, Einzelinstanz, Artikel). Jeder Fehlschlag nennt seinen Grund."""
    parsed = inst_svc.parse_unit_number(number)
    if not parsed:
        raise HTTPException(
            status_code=400,
            detail=(f"«{number}» ist keine Einzelinstanz-Nummer. "
                    f"Erwartet wird <Instanznummer>-<Suffix>, z. B. 100000123-7."),
        )
    object_id, suffix = parsed
    instance = db.query(Instance).filter(Instance.object_id == object_id).first()
    if instance is None:
        raise HTTPException(status_code=404, detail=f"Instanz {object_id} nicht gefunden.")
    unit = (
        db.query(InstanceUnit)
        .filter(InstanceUnit.instance_id == instance.id, InstanceUnit.suffix == suffix)
        .first()
    )
    if unit is None:
        raise HTTPException(status_code=404, detail=f"Einzelinstanz {number} nicht gefunden.")
    article = db.query(Article).filter(Article.id == instance.article_id).first()
    if article is None:
        raise HTTPException(
            status_code=404,
            detail=f"Artikel der Instanz {object_id} nicht gefunden (Datensatz {instance.article_id}).",
        )
    return instance, unit, article


@router.get("/{number}/fields")
def capture_fields(
    number: str,
    db: Session = Depends(get_db),
    _: UserProfile = Depends(require_employee),
):
    """Die Erfassungsmaske für diese Einzelinstanz (kommt vom Artikel)."""
    _, _unit, article = _resolve(db, number)
    return {"article_object_id": article.object_id, "fields": capture_svc.fields_of(article)}


@router.get("/{number}", response_model=list[CaptureResponse])
def list_captures(
    number: str,
    db: Session = Depends(get_db),
    _: UserProfile = Depends(require_employee),
):
    _, unit, _article = _resolve(db, number)
    return capture_svc.history(db, unit)


@router.post("/{number}", response_model=CaptureResponse, status_code=201)
def record_capture(
    number: str,
    data: CaptureCreate,
    db: Session = Depends(get_db),
    user: UserProfile = Depends(require_employee),
):
    _, unit, article = _resolve(db, number)
    entry = capture_svc.record(
        db, unit=unit, article=article, values=data.values,
        actor_id=user.id, note=data.note,
    )
    db.commit()
    db.refresh(entry)
    return entry
