"""Datenerfassung – **lesen**. Geschrieben wird ausschliesslich im Prozess.

Erfasst wird, wenn ein Stück vor einem Modul steht und jemand bestätigt
(``POST /erp/orders/{id}/steps/{step_id}/confirm``). Es gibt hier bewusst **keinen**
Schreib-Endpunkt mehr: der frühere legte Werte an einer beliebigen Einzelinstanz an,
ohne dass sie irgendwo davorstand – eine Erfassung ohne Anlass, und eine zweite Tür zu
derselben Sache.

Was bleibt, ist die **Historie am Stück**: was an dieser Einzelinstanz erfasst wurde,
wann, von wem und mit welchem Ergebnis. Eingefroren – eine Korrektur wäre eine neue
Erfassung, kein Update.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..core.auth import require_employee
from ..core.database import get_db
from ..models import Instance, InstanceUnit, ProcessStep, UserProfile
from ..schemas.instance import CaptureResponse
from ..services import capture as capture_svc
from ..services import instances as inst_svc

router = APIRouter(prefix="/api/v1/erp/captures", tags=["captures"])


def _unit(db: Session, number: str) -> InstanceUnit:
    """``100000123-7`` → Einzelinstanz. Jeder Fehlschlag nennt seinen Grund."""
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
    return unit


@router.get("/{number}", response_model=list[CaptureResponse])
def list_captures(
    number: str,
    db: Session = Depends(get_db),
    _: UserProfile = Depends(require_employee),
):
    """Was an dieser Einzelinstanz erfasst wurde – neueste zuerst.

    Die **Punkte** kommen aus dem Modul, das sie erfasst hat: ohne sie stünden nur
    Schlüssel und Rohwerte da, und ein Messwert ohne seine Bezeichnung ist eine Zahl.
    """
    unit = _unit(db, number)
    rows = capture_svc.history(db, unit)
    steps = {
        s.id: s
        for s in db.query(ProcessStep).filter(ProcessStep.id.in_({c.step_id for c in rows})).all()
    } if rows else {}
    return [
        CaptureResponse(
            id=c.id,
            values=c.values,
            result=c.result,
            note=c.note,
            created_at=c.created_at,
            step_name=steps[c.step_id].name if c.step_id in steps else None,
            points=capture_svc.points_of(steps[c.step_id]) if c.step_id in steps else [],
        )
        for c in rows
    ]
