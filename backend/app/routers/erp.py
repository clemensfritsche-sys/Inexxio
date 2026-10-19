from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from pydantic import BaseModel

from ..core.auth import require_admin, require_employee
from ..core.database import get_db
from ..models import UserProfile, WebAuthnCredential
from ..schemas.admin import (
    AddressIn, CompanyRef, ErpAdminUpdate, PersonCreate, UserProfileResponse,
)
from ..schemas.voucher import VoucherParty
from ..services import address_book, people
from ..services import sites
from ..services.objects import resolve_object_type

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


@router.get("/records", response_model=list[UserProfileResponse])
async def list_erp_records(
    db: Session = Depends(get_db),
    _: UserProfile = Depends(require_employee),
):
    # **Alle Personen**, auch eine alte deaktivierte Zeile: «inaktiv» ist ein Zustand,
    # kein Verschwinden – sie bleibt ansehbar.
    users = db.query(UserProfile).order_by(UserProfile.object_id).all()
    counts = _passkey_counts(db, [u.id for u in users])
    return [_record(u, counts.get(u.id, 0)) for u in users]


@router.post("/records", response_model=UserProfileResponse, status_code=201)
async def create_erp_record(
    data: PersonCreate,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_employee),
):
    """►►► **Eine Person anlegen** – ohne dass sie sich je angemeldet hat. ◄◄◄
    Vorname, Nachname, E-Mail, Rolle; Objektnummer und Anmeldekonto entstehen sofort
    (``people.create_person``). Personal-Rollen vergibt nur ein Admin."""
    return _record(people.create_person(db, data, current_user))


@router.get("/people", response_model=list[VoucherParty])
def search_people(
    search: str = Query("", max_length=80),
    limit: int = Query(20, ge=1, le=50),
    staff: bool = Query(False),
    db: Session = Depends(get_db),
    _: UserProfile = Depends(require_employee),
):
    """**Welche Person ist gemeint?** – Nummer, Firma, Name oder E-Mail
    (``people.search``), gesucht statt als Liste geladen. Gegenpartei eines Belegs,
    Partner im Editor, Empfänger einer Nachricht; ``staff`` engt auf das Personal ein."""
    return [VoucherParty(object_id=u.object_id or 0, name=u.display_name)
            for u in people.search(db, search, staff=staff, limit=limit)]


@router.get("/companies", response_model=list[CompanyRef])
async def search_companies(
    search: str = "",
    db: Session = Depends(get_db),
    _: UserProfile = Depends(require_employee),
):
    """**Welche Firma ist gemeint?** – die Vorschläge, während das **Personal** einer
    Person ihre Firma zuordnet. Ab zwei Zeichen, höchstens acht.

    ►►► **Nur für das Personal.** ◄◄◄ Die Kundenliste ist nichts, was ein Kunde
    durchblättern darf – auch nicht über Teilwörter («Ag», «Gm»). Eine Person **nennt**
    ihre Firma (UID, sonst Name und Rechtsform), sie sucht sie nicht."""
    if len(search.strip()) < 2:
        return []
    return [CompanyRef.model_validate(c) for c in sites.search(db, search)]


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
    people.apply_profile_update(db, user, data, current_user.id, staff=True)
    db.commit()
    db.refresh(user)
    return _record(user, _passkey_counts(db, [user.id]).get(user.id, 0))


# ─── Das Adressbuch am Datensatz – dieselben Funktionen wie im Konto ─────────────────

def _person(db: Session, object_id: int) -> UserProfile:
    user = db.query(UserProfile).filter(UserProfile.object_id == object_id).first()
    if not user:
        raise HTTPException(404, detail="Record not found")
    return user


def _done(db: Session, user: UserProfile) -> UserProfileResponse:
    db.commit()
    db.refresh(user)
    return _record(user, _passkey_counts(db, [user.id]).get(user.id, 0))


@router.post("/records/{object_id}/addresses", response_model=UserProfileResponse)
async def add_record_address(
    object_id: int,
    data: AddressIn,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_admin),
):
    user = _person(db, object_id)
    address_book.add(db, user, data.model_dump(exclude_unset=True), current_user.id)
    return _done(db, user)


@router.patch("/records/{object_id}/addresses/{address_id}",
              response_model=UserProfileResponse)
async def change_record_address(
    object_id: int,
    address_id: int,
    data: AddressIn,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_admin),
):
    user = _person(db, object_id)
    address_book.change(db, user, address_id, data.model_dump(exclude_unset=True),
                        current_user.id)
    return _done(db, user)


@router.delete("/records/{object_id}/addresses/{address_id}",
               response_model=UserProfileResponse)
async def remove_record_address(
    object_id: int,
    address_id: int,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_admin),
):
    user = _person(db, object_id)
    address_book.remove(db, user, address_id, current_user.id)
    return _done(db, user)
