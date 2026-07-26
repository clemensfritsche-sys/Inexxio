"""Standorte für Instanzen (Prozessschritt «Bewegung»).

Eine Instanz **kann** einen Standort haben (sie darf auch standortlos sein, ``NULL`` =
«noch nicht festgelegt»); ist einer gesetzt, ist er stets ein **Halter** – ein
Datensatzobjekt mit 9-stelliger Nummer:

    user     → UserProfile (Mitarbeiter, Lieferant, Kunde)
    instance → andere Instanz (Behälter, Palette, Maschine, LKW)
    company  → das Unternehmen selbst («im Betrieb»)

Der frühere Typ **lagerplatz** ist ersatzlos entfallen (siehe ``schemas/movement.py``).
Ein unbekannter/veralteter Typ ist hier bewusst **kein Fehler**: er löst zu ``None`` auf
und wird als «kein Standort» angezeigt. Geprüft wird nur beim **Schreiben**
(``validate_location``) – so kann ein Altbestand nie eine Ansicht zerlegen.

Bei der Auftragsfreigabe startet eine Instanz beim **Lieferanten** (Lieferanten-
Beschaffung als erster Schritt) oder **ohne Standort** (siehe
``services/serialization.py``). Den realen Ort setzt der erste Bewegungs-Schritt.
"""

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..models import Instance, UserProfile
from . import people
from .objects import obj_nr as _obj_nr
from ..schemas.movement import LOCATION_TYPES


def location_label(db: Session, ltype: str | None, lid: int | None) -> str | None:
    """Anzeige eines Standorts: Instanz → Objektnummer, User → Name, Unternehmen → Firma.

    Ein unbekannter Typ (Altbestand) ergibt ``None`` = «kein Standort» – nie ein Fehler."""
    if not ltype or lid is None:
        return None
    if ltype == "user":
        u = (
            db.query(UserProfile)
            .filter(UserProfile.object_id == lid, UserProfile.is_active == True)
            .first()
        )
        return people.name(u)
    if ltype == "instance":
        inst = (
            db.query(Instance)
            .filter(Instance.object_id == lid, Instance.is_active == True)
            .first()
        )
        return _obj_nr(lid) if inst else None
    if ltype == "company":
        from ..models import CompanySettings
        c = db.query(CompanySettings).filter(CompanySettings.object_id == lid).first()
        return (c.company_name or _obj_nr(lid)) if c else _obj_nr(lid)
    return None


LocKey = tuple[str | None, int | None]


def location_labels(db: Session, pairs: list[LocKey]) -> dict[LocKey, str | None]:
    """**Batch**-Variante von ``location_label``: EIN Query je Standort-Typ statt einem je
    Zeile (N+1) – für Feeds/Listen (Instanz-Feed, Artikel-Bestand, Auftrags-Instanzen)."""
    ids: dict[str, set[int]] = {"user": set(), "instance": set(), "company": set()}
    for ltype, lid in pairs:
        if ltype in ids and lid is not None:
            ids[ltype].add(lid)
    from ..models import CompanySettings
    companies = {
        c.object_id: (c.company_name or _obj_nr(c.object_id))
        for c in db.query(CompanySettings).filter(CompanySettings.object_id.in_(ids["company"]))
    } if ids["company"] else {}
    users = {
        u.object_id: people.name(u) for u in db.query(UserProfile).filter(
            UserProfile.object_id.in_(ids["user"]), UserProfile.is_active == True)
    } if ids["user"] else {}
    existing_inst = {
        oid for (oid,) in db.query(Instance.object_id).filter(
            Instance.object_id.in_(ids["instance"]), Instance.is_active == True)
    } if ids["instance"] else set()

    out: dict[LocKey, str | None] = {}
    for key in pairs:
        ltype, lid = key
        if not ltype or lid is None:
            out[key] = None
        elif ltype == "user":
            out[key] = users.get(lid)
        elif ltype == "instance":
            out[key] = _obj_nr(lid) if lid in existing_inst else None
        elif ltype == "company":
            out[key] = companies.get(lid, _obj_nr(lid))
        else:
            out[key] = None
    return out


def physical_location_labels(db: Session, pairs: list[LocKey]) -> dict[LocKey, str | None]:
    """**Batch**-Variante von ``physical_location_label``: löst ``instance``→``instance``-
    Ketten ebenenweise auf (EIN Query je Kettentiefe statt einem je Zeile) und labelt die
    physischen Endpunkte gesammelt."""
    resolved: dict[LocKey, LocKey] = {key: key for key in pairs}
    for _ in range(10):   # Tiefenschutz analog resolve_physical_location
        open_ids = {cur[1] for cur in resolved.values()
                    if cur[0] == "instance" and cur[1] is not None}
        if not open_ids:
            break
        hosts = {
            i.object_id: (i.location_type, i.location_id)
            for i in db.query(Instance).filter(
                Instance.object_id.in_(open_ids), Instance.is_active == True)
        }
        progressed = False
        for key, cur in resolved.items():
            if cur[0] == "instance" and cur[1] in hosts:
                resolved[key] = hosts[cur[1]]
                progressed = True
        if not progressed:
            break
    labels = location_labels(db, list(set(resolved.values())))
    return {key: labels.get(cur) for key, cur in resolved.items()}


def validate_location(db: Session, ltype: str, lid: int) -> None:
    """Stellt sicher, dass der Zielstandort gültig ist und existiert."""
    if ltype not in LOCATION_TYPES:
        raise HTTPException(400, detail="Ungültiger Standort-Typ")
    if location_label(db, ltype, lid) is None:
        raise HTTPException(400, detail="Zielstandort nicht gefunden")


def location_chain(db: Session, ltype: str | None, lid: int | None,
                   max_depth: int = 10) -> list[dict]:
    """Die **volle Standort-Kette** von innen nach aussen – die Antwort auf «wo genau?».

    Beispiel für eine Schraube in einem Behälter in einer Halle::

        [{instance 100000007 · Behälter},
         {instance 100000003 · Halle Nord},
         {address  —         · Musterstrasse 1, 8000 Zürich}]

    Jeder Eintrag: ``{location_type, location_id, label, address}``. Die Kette folgt
    ``instance``→``instance``-Verschachtelungen bis zu einem physischen Halter und hängt –
    falls dieser eine Adresse trägt (Person, Unternehmen) – einen abschliessenden
    ``address``-Eintrag an. Sie endet ausserdem bei einem Zyklus oder ``max_depth``.

    Bewusst nur für **Detail**-Ansichten gedacht (ein Datensatz, ≤ 10 Auflösungen); Feeds
    nutzen weiterhin die Batch-Labels."""
    from . import address as addr_mod

    out: list[dict] = []
    seen: set[tuple[str, int]] = set()
    cur_type, cur_id = ltype, lid

    while cur_type and cur_id is not None and len(out) < max_depth:
        if (cur_type, cur_id) in seen:
            break                        # Zyklus-Schutz (A liegt in B, B liegt in A)
        seen.add((cur_type, cur_id))
        out.append({
            "location_type": cur_type,
            "location_id": cur_id,
            "label": location_label(db, cur_type, cur_id),
            "address": None,
        })
        if cur_type != "instance":
            break                        # physischer Halter erreicht
        host = (
            db.query(Instance)
            .filter(Instance.object_id == cur_id, Instance.is_active == True)
            .first()
        )
        if not host:
            break
        cur_type, cur_id = host.location_type, host.location_id

    # Abschluss: die Adresse des äussersten Halters (das geografische «Blatt»).
    if out:
        last = out[-1]
        a = _holder_address(db, last["location_type"], last["location_id"])
        line = addr_mod.one_line(a) if a else None
        if line and addr_mod.has_content(a):
            out.append({"location_type": "address", "location_id": None,
                        "label": line, "address": a})
    return out


def _holder_address(db: Session, ltype: str | None, lid: int | None) -> dict | None:
    """Adresse eines Halters (Person/Unternehmen) in kanonischer Form."""
    from . import address as addr_mod
    from ..models import CompanySettings as _CS
    if not ltype or lid is None:
        return None
    if ltype == "user":
        u = db.query(UserProfile).filter(UserProfile.object_id == lid).first()
        return addr_mod.of_user(u, "ship") if u else None
    if ltype == "company":
        c = db.query(_CS).filter(_CS.object_id == lid).first()
        return addr_mod.of_company(c) if c else None
    return None


def resolve_physical_location(
    db: Session, ltype: str | None, lid: int | None, _depth: int = 0
) -> tuple[str | None, int | None]:
    """Folgt ``instance``→``instance``-Ketten bis zum **physischen** Standort
    (Person/Unternehmen). So «wandert» eine verbaute Komponente mit ihrer Produkt-
    Instanz: ihr Standort ist die Produkt-Instanz, der physische Ort ergibt sich
    aus deren Standort. Endet bei einem Nicht-Instanz-Standort (Tiefenschutz)."""
    if ltype != "instance" or lid is None or _depth > 10:
        return ltype, lid
    host = (
        db.query(Instance)
        .filter(Instance.object_id == lid, Instance.is_active == True)
        .first()
    )
    if not host:
        return ltype, lid
    return resolve_physical_location(db, host.location_type, host.location_id, _depth + 1)
