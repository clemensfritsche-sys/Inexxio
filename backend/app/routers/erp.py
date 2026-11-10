from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from pydantic import BaseModel

from ..core.auth import require_employee
from ..core.database import DB
from ..models import UserProfile, WebAuthnCredential
from ..schemas.admin import (
    AddressIn, CompanyRef, ErpAdminUpdate, PersonCreate, UserProfileResponse,
)
from ..schemas.voucher import VoucherParty
from ..services import address_book, people
from ..services import sites
from ..services.objects import resolve_object_type
from ..domain import policy
from ..domain.errors import NotFound

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


def _record(user: UserProfile, passkeys: int = 0,
            viewer: UserProfile | None = None) -> UserProfileResponse:
    resp = UserProfileResponse.model_validate(user)
    resp.passkey_count = passkeys
    resp.may_edit = viewer is not None and policy.may(
        viewer, "person.staff" if policy.is_staff(user) else "person.edit")
    resp.may_access = viewer is not None and policy.may(viewer, "person.access", user.object_id)
    return resp


class ObjectResolution(BaseModel):
    """Auflösung einer universellen Objektnummer auf ihren Typ (für Scan/Quer-Refs)."""

    object_id: int
    object_type: str


@router.get("/objects/{object_id}", response_model=ObjectResolution)
def resolve_object(
    object_id: int,
    db: Session = DB,
    _: UserProfile = Depends(require_employee),
):
    """Typ einer Objektnummer in O(1) auflösen (zentrale Registry, Fallback Scan)."""
    otype = resolve_object_type(db, object_id)
    if not otype:
        raise NotFound("Objekt nicht gefunden")
    return ObjectResolution(object_id=object_id, object_type=otype)


@router.get("/records", response_model=list[UserProfileResponse])
def list_erp_records(
    db: Session = DB,
    viewer: UserProfile = Depends(require_employee),
):
    """Alle Personen für den Feed."""
    # **Alle Personen**, auch eine alte deaktivierte Zeile: «inaktiv» ist ein Zustand,
    # kein Verschwinden – sie bleibt ansehbar.
    users = (db.query(UserProfile)
             .options(selectinload(UserProfile.addresses), selectinload(UserProfile.company))
             .order_by(UserProfile.object_id).all())
    counts = _passkey_counts(db, [u.id for u in users])
    return [_record(u, counts.get(u.id, 0), viewer) for u in users]


@router.post("/records", response_model=UserProfileResponse, status_code=201)
def create_erp_record(
    data: PersonCreate,
    db: Session = DB,
    current_user: UserProfile = Depends(require_employee),
):
    """►►► **Eine Person anlegen** – ohne dass sie sich je angemeldet hat. ◄◄◄
    Vorname, Nachname, E-Mail, Rolle; Objektnummer und Anmeldekonto entstehen sofort
    (``people.create_person``). Personal-Rollen vergibt nur ein Admin."""
    return _record(people.create_person(db, data, current_user), viewer=current_user)


@router.get("/people", response_model=list[VoucherParty])
def search_people(
    search: str = Query("", max_length=80),
    limit: int = Query(20, ge=1, le=50),
    staff: bool = Query(False),
    db: Session = DB,
    _: UserProfile = Depends(require_employee),
):
    """**Welche Person ist gemeint?** – Nummer, Firma, Name oder E-Mail
    (``people.search``), gesucht statt als Liste geladen. Gegenpartei eines Belegs,
    Partner im Editor, Empfänger einer Nachricht; ``staff`` engt auf das Personal ein."""
    return [VoucherParty(object_id=u.object_id or 0, name=u.display_name)
            for u in people.search(db, search, staff=staff, limit=limit)]


@router.get("/companies", response_model=list[CompanyRef])
def search_companies(
    search: str = "",
    db: Session = DB,
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
def get_erp_record(
    object_id: int,
    db: Session = DB,
    viewer: UserProfile = Depends(require_employee),
):
    """Eine Person mit ihren Angaben."""
    user = db.query(UserProfile).filter(UserProfile.object_id == object_id).first()
    if not user:
        raise NotFound(f"Person «{object_id}» gibt es nicht.")
    return _record(user, _passkey_counts(db, [user.id]).get(user.id, 0), viewer)


@router.patch("/records/{object_id}", response_model=UserProfileResponse)
def update_erp_record(
    object_id: int,
    data: ErpAdminUpdate,
    db: Session = DB,
    current_user: UserProfile = Depends(require_employee),
):
    """Angaben einer Person ändern (Name, Kontakt, Firma, Rolle, Anstellung) – jede Person mit
    ERP-Zugang; Rollen und Mitarbeitende nur der Admin (``domain/policy``)."""
    user = _person(db, object_id)
    _may_edit(current_user, user, "role" in data.model_fields_set)
    people.apply_profile_update(db, user, data, current_user.id, staff=True)
    db.flush()
    db.refresh(user)
    return _record(user, _passkey_counts(db, [user.id]).get(user.id, 0), current_user)


# ─── Das Adressbuch am Datensatz – dieselben Funktionen wie im Konto ─────────────────

def _person(db: Session, object_id: int) -> UserProfile:
    user = db.query(UserProfile).filter(UserProfile.object_id == object_id).first()
    if not user:
        raise NotFound(f"Person «{object_id}» gibt es nicht.")
    return user


def _may_edit(actor: UserProfile, person: UserProfile, role: bool = False) -> None:
    """Kundendaten ändert jedes Personal; eine Rolle oder die Angaben von Mitarbeitenden nur der
    Admin."""
    policy.require(actor, "person.staff" if role or policy.is_staff(person) else "person.edit")


def _done(db: Session, user: UserProfile, viewer: UserProfile) -> UserProfileResponse:
    db.flush()
    db.refresh(user)
    return _record(user, _passkey_counts(db, [user.id]).get(user.id, 0), viewer)


@router.post("/records/{object_id}/addresses", response_model=UserProfileResponse)
def add_record_address(
    object_id: int,
    data: AddressIn,
    db: Session = DB,
    current_user: UserProfile = Depends(require_employee),
):
    """Eine Anschrift ins Adressbuch einer Person aufnehmen."""
    user = _person(db, object_id)
    _may_edit(current_user, user)
    address_book.add(db, user, data.model_dump(exclude_unset=True), current_user.id)
    return _done(db, user, current_user)


@router.patch("/records/{object_id}/addresses/{address_id}",
              response_model=UserProfileResponse)
def change_record_address(
    object_id: int,
    address_id: int,
    data: AddressIn,
    db: Session = DB,
    current_user: UserProfile = Depends(require_employee),
):
    """Eine Anschrift im Adressbuch einer Person ändern."""
    user = _person(db, object_id)
    _may_edit(current_user, user)
    address_book.change(db, user, address_id, data.model_dump(exclude_unset=True),
                        current_user.id)
    return _done(db, user, current_user)


@router.delete("/records/{object_id}/addresses/{address_id}",
               response_model=UserProfileResponse)
def remove_record_address(
    object_id: int,
    address_id: int,
    db: Session = DB,
    current_user: UserProfile = Depends(require_employee),
):
    """Eine Anschrift aus dem Adressbuch einer Person entfernen."""
    user = _person(db, object_id)
    _may_edit(current_user, user)
    address_book.remove(db, user, address_id, current_user.id)
    return _done(db, user, current_user)
