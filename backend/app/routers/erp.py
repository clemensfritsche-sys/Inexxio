from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from pydantic import BaseModel

from ..core.auth import require_admin, require_employee
from ..core.database import get_db
from ..models import UserProfile, WebAuthnCredential
from ..schemas.admin import ErpAdminUpdate, UserProfileResponse
from ..services import people
from ..services.objects import next_object_ids, resolve_object_type

router = APIRouter(prefix="/api/v1/erp", tags=["erp"])


def _passkey_counts(db: Session, user_ids: list[int]) -> dict[int, int]:
    """{UserProfile.id → Anzahl aktiver Passkeys} – EINE gruppierte Abfrage (kein N+1)."""
    if not user_ids:
        return {}
    rows = (
        db.query(WebAuthnCredential.user_id, func.count(WebAuthnCredential.id))
        .filter(
            WebAuthnCredential.user_id.in_(user_ids),
            WebAuthnCredential.is_active == True,   # noqa: E712
        )
        .group_by(WebAuthnCredential.user_id)
        .all()
    )
    return dict(rows)


def _record(user: UserProfile, passkeys: int = 0) -> UserProfileResponse:
    resp = UserProfileResponse.model_validate(user)
    resp.passkey_count = passkeys
    return resp


class ObjectResolution(BaseModel):
    """Auflösung einer universellen Objektnummer auf ihren Typ (für Scan/Quer-Refs)."""

    object_id: int
    object_type: str


@router.get("/objects/{object_id}", response_model=ObjectResolution)
async def resolve_object(
    object_id: int,
    db: Session = Depends(get_db),
    _: UserProfile = Depends(require_employee),
):
    """Typ einer Objektnummer in O(1) auflösen (zentrale Registry, Fallback Scan)."""
    otype = resolve_object_type(db, object_id)
    if not otype:
        raise HTTPException(404, detail="Objekt nicht gefunden")
    return ObjectResolution(object_id=object_id, object_type=otype)


def _assign_object_ids(db: Session) -> None:
    pending = (
        db.query(UserProfile)
        .filter(UserProfile.object_id.is_(None))
        .order_by(UserProfile.id)
        .all()
    )
    if not pending:
        return
    # Aus der gemeinsamen Sequence vergeben (atomar, über alle Objekttypen hinweg).
    ids = next_object_ids(db, len(pending), "user")
    for u, oid in zip(pending, ids):
        u.object_id = oid
    db.commit()


@router.get("/records", response_model=list[UserProfileResponse])
async def list_erp_records(
    db: Session = Depends(get_db),
    _: UserProfile = Depends(require_employee),
):
    _assign_object_ids(db)
    # **Auch deaktivierte Personen** – «inaktiv» ist ein **Zustand**, kein Verschwinden.
    # Genau wie ein inaktiver Artikel im Feed stehen bleibt (rote Badge «Inaktiv»), bleibt
    # eine ausser Betrieb genommene Person sichtbar: sonst liesse sie sich weder ansehen
    # noch reaktivieren, und genau dafür brauchte es früher eine **zweite**, nicht
    # verlinkte Benutzerverwaltung (`/admin/benutzer`, jetzt entfallen).
    users = db.query(UserProfile).order_by(UserProfile.object_id).all()
    counts = _passkey_counts(db, [u.id for u in users])
    return [_record(u, counts.get(u.id, 0)) for u in users]


@router.get("/records/{object_id}", response_model=UserProfileResponse)
async def get_erp_record(
    object_id: int,
    db: Session = Depends(get_db),
    _: UserProfile = Depends(require_employee),
):
    user = db.query(UserProfile).filter(UserProfile.object_id == object_id).first()
    if not user:
        raise HTTPException(404, detail="Record not found")
    return _record(user, _passkey_counts(db, [user.id]).get(user.id, 0))


@router.patch("/records/{object_id}", response_model=UserProfileResponse)
async def update_erp_record(
    object_id: int,
    data: ErpAdminUpdate,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_admin),
):
    user = db.query(UserProfile).filter(UserProfile.object_id == object_id).first()
    if not user:
        raise HTTPException(404, detail="Record not found")
    # Eine System-Identität behält ihre Rolle. Das KI-Modul ist entfernt (docs/attic.md),
    # aber eine so angelegte Zeile kann in gewachsenen Datenbanken stehen – ihr eine
    # menschliche Rolle zu geben hiesse, ihre Historie einer Person zuzuschreiben.
    if user.role == "ai" and data.model_dump(exclude_unset=True).get("role") not in (None, "ai"):
        raise HTTPException(409, detail="Die System-KI-Identität kann keine andere Rolle erhalten")
    people.apply_profile_update(db, user, data, current_user.id)
    db.commit()
    db.refresh(user)
    return _record(user, _passkey_counts(db, [user.id]).get(user.id, 0))
