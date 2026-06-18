"""Standorte für Instanzen (Prozessschritt «Bewegung»).

Eine Instanz hat IMMER einen Standort, und ein Standort ist stets ein
Datensatzobjekt mit 9-stelliger Nummer:

    lagerplatz → StorageLocation
    user       → UserProfile (Mitarbeiter, Lieferant, Kunde)
    instance   → andere Instanz (z. B. eingebaut in Maschine/Behälter)

Bei der Auftragsfreigabe erhält jede neue Instanz einen Startstandort (Lieferant
bzw. Wareneingang); spätestens mit dem Wareneingang («received») liegt sie im
Wareneingang. Welcher Lagerplatz das ist, steht in den Systemkonfigurationen
(``company_settings.default_receiving_location_id``); fehlt der Eintrag, wird
automatisch ein Lagerplatz «Wareneingang» angelegt – so ist die Regel
„nie ohne Standort" garantiert, ohne dass vorab etwas konfiguriert sein muss.
"""

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..models import Instance, StorageLocation, UserProfile
from ..schemas.movement import LOCATION_TYPES
from .admin import get_or_create_settings
from .objects import next_object_id

RECEIVING_NAME = "Wareneingang"


def _user_label(u: UserProfile) -> str:
    name = " ".join(p for p in [u.first_name, u.last_name] if p).strip()
    return u.company_name or name or u.email


def _obj_nr(lid: int) -> str:
    """9-stellige Objektnummer (analog Frontend fmtObjId)."""
    return str(lid).zfill(9)


def location_label(db: Session, ltype: str | None, lid: int | None) -> str | None:
    """Anzeige eines Standorts: Lagerplatz/Instanz → Objektnummer, User → Name.

    Lagerplätze werden über die Objektnummer angesprochen (kein Name mehr)."""
    if not ltype or lid is None:
        return None
    if ltype == "lagerplatz":
        loc = (
            db.query(StorageLocation)
            .filter(StorageLocation.object_id == lid, StorageLocation.is_active == True)
            .first()
        )
        return _obj_nr(lid) if loc else None
    if ltype == "user":
        u = (
            db.query(UserProfile)
            .filter(UserProfile.object_id == lid, UserProfile.is_active == True)
            .first()
        )
        return _user_label(u) if u else None
    if ltype == "instance":
        inst = (
            db.query(Instance)
            .filter(Instance.object_id == lid, Instance.is_active == True)
            .first()
        )
        return _obj_nr(lid) if inst else None
    return None


def validate_location(db: Session, ltype: str, lid: int) -> None:
    """Stellt sicher, dass der Zielstandort gültig ist und existiert."""
    if ltype not in LOCATION_TYPES:
        raise HTTPException(400, detail="Ungültiger Standort-Typ")
    if location_label(db, ltype, lid) is None:
        raise HTTPException(400, detail="Zielstandort nicht gefunden")


def ensure_receiving_location(db: Session) -> int:
    """Objektnummer des Wareneingangs; legt ihn bei Bedarf automatisch an."""
    settings = get_or_create_settings(db)
    lid = settings.default_receiving_location_id
    if lid:
        loc = (
            db.query(StorageLocation)
            .filter(StorageLocation.object_id == lid, StorageLocation.is_active == True)
            .first()
        )
        if loc:
            return lid
    loc = StorageLocation(
        object_id=next_object_id(db),
        status="released",
        name=RECEIVING_NAME,
    )
    db.add(loc)
    db.flush()
    settings.default_receiving_location_id = loc.object_id
    return loc.object_id


def resolve_receiving_location(db: Session, po) -> int:
    """Wareneingang/Lieferadresse einer Bestellung: bevorzugt der im Beschaffungs-
    schritt definierte Lagerplatz (``po.receiving_location_id``); sonst der
    automatische Wareneingang. So ist „nie ohne Standort" garantiert."""
    lid = getattr(po, "receiving_location_id", None) if po else None
    if lid:
        loc = (
            db.query(StorageLocation)
            .filter(StorageLocation.object_id == lid, StorageLocation.is_active == True)
            .first()
        )
        if loc:
            return lid
    return ensure_receiving_location(db)
