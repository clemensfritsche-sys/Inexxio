"""Standorte für Instanzen (Prozessschritt «Bewegung»).

**Ein Standort ist ein Halter.** Vier Arten – drei davon Datensatzobjekte mit 9-stelliger
Objektnummer, die vierte eine Adresse direkt am Objekt:

    place    → Adresse/GPS **inline** (``instances.place``, KEINE Objektnummer) ← das «Blatt»
    user     → UserProfile (Mitarbeiter, Lieferant, Kunde)
    instance → andere Instanz (Behälter, Palette, Maschine, LKW)
    company  → das Unternehmen selbst (Betriebsadresse)

Ein **benannter Platz** (Regal A, Wareneingang, LKW 1) ist damit einfach eine **Instanz**,
die andere Instanzen hält – kein eigener Datensatztyp mehr (der frühere `lagerplatz` ist
entfallen). Standortlos (``NULL``) bleibt erlaubt – «noch nicht festgelegt» bzw. verschrottet.

Bei der Auftragsfreigabe startet eine Instanz beim **Lieferanten** (Lieferanten-Beschaffung
als erster Schritt) oder **ohne Standort** (siehe ``services/serialization.py``); den realen
Ort setzt der erste Bewegungs-Schritt.
"""

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..models import CompanySettings, Instance, UserProfile
from ..schemas.movement import LOCATION_TYPES


def _user_label(u: UserProfile) -> str:
    return u.display_name


def _obj_nr(lid: int) -> str:
    """9-stellige Objektnummer (analog Frontend fmtObjId)."""
    return str(lid).zfill(9)


def place_label(place: dict | None) -> str | None:
    """Anzeige eines **Orts** aus seinem Adress-Snapshot: «Name · Strasse · PLZ Ort».

    Reine Funktion (kein DB-Zugriff) – ein Ort trägt keine Objektnummer, seine Wahrheit
    steht am Objekt selbst. Fällt auf die Koordinaten zurück, wenn nur GPS bekannt ist."""
    if not place:
        return None
    bits = [
        (place.get("name") or "").strip(),
        (place.get("street1") or "").strip(),
        " ".join(x for x in [(place.get("zip") or "").strip(), (place.get("city") or "").strip()] if x),
    ]
    label = " · ".join(b for b in bits if b)
    if label:
        return label
    lat, lng = place.get("lat"), place.get("lng")
    return f"{lat:.5f}, {lng:.5f}" if lat is not None and lng is not None else None


def location_label(db: Session, ltype: str | None, lid: int | None,
                   place: dict | None = None) -> str | None:
    """Anzeige eines Standorts: Instanz → Objektnummer, Person/Unternehmen → Name,
    Ort → Adress-Label (aus ``place``, dafür braucht es keine Nummer)."""
    if ltype == "place":
        return place_label(place)
    if not ltype or lid is None:
        return None
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
    if ltype == "company":
        c = db.query(CompanySettings).filter(CompanySettings.object_id == lid).first()
        return (c.company_name or _obj_nr(lid)) if c else _obj_nr(lid)
    return None


LocKey = tuple[str | None, int | None]


def location_labels(db: Session, pairs: list[LocKey]) -> dict[LocKey, str | None]:
    """**Batch**-Variante von ``location_label``: EIN Query je Standort-Typ statt einem je
    Zeile (N+1) – für Feeds/Listen (Instanz-Feed, Artikel-Bestand, Auftrags-Instanzen).

    Deckt nur die **objektbasierten** Halter ab; ein ``place`` trägt keine Objektnummer und
    wird von der aufrufenden Zeile über ``resolve_label``/``place_label`` gelabelt."""
    ids: dict[str, set[int]] = {"user": set(), "instance": set(), "company": set()}
    for ltype, lid in pairs:
        if ltype in ids and lid is not None:
            ids[ltype].add(lid)
    companies = {
        c.object_id: (c.company_name or _obj_nr(c.object_id))
        for c in db.query(CompanySettings).filter(CompanySettings.object_id.in_(ids["company"]))
    } if ids["company"] else {}
    users = {
        u.object_id: _user_label(u) for u in db.query(UserProfile).filter(
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


def resolve_label(ltype: str | None, lid: int | None, place: dict | None,
                  batch: dict[LocKey, str | None]) -> str | None:
    """Label einer Zeile aus einem vorberechneten Batch – berücksichtigt den **Ort**
    (dessen Wahrheit an der Zeile selbst hängt). Die EINE Stelle, an der Feeds/Embeds
    beide Fälle zusammenführen."""
    if ltype == "place":
        return place_label(place)
    return batch.get((ltype, lid))


def physical_location_labels(db: Session, pairs: list[LocKey]) -> dict[LocKey, str | None]:
    """**Batch**-Variante von ``physical_location_label``: löst ``instance``→``instance``-
    Ketten ebenenweise auf (EIN Query je Kettentiefe statt einem je Zeile) und labelt die
    physischen Endpunkte gesammelt. Endet die Kette an einem **Ort**, wird dessen
    Adress-Label geliefert."""
    resolved: dict[LocKey, LocKey] = {key: key for key in pairs}
    places: dict[LocKey, dict | None] = {}
    for _ in range(10):   # Tiefenschutz analog resolve_physical_location
        open_ids = {cur[1] for cur in resolved.values()
                    if cur[0] == "instance" and cur[1] is not None}
        if not open_ids:
            break
        hosts = {
            i.object_id: (i.location_type, i.location_id, i.place)
            for i in db.query(Instance).filter(
                Instance.object_id.in_(open_ids), Instance.is_active == True)
        }
        progressed = False
        for key, cur in resolved.items():
            if cur[0] == "instance" and cur[1] in hosts:
                htype, hid, hplace = hosts[cur[1]]
                resolved[key] = (htype, hid)
                places[key] = hplace
                progressed = True
        if not progressed:
            break
    labels = location_labels(db, list(set(resolved.values())))
    return {
        key: (place_label(places.get(key)) if cur[0] == "place" else labels.get(cur))
        for key, cur in resolved.items()
    }


def validate_location(db: Session, ltype: str, lid: int | None,
                      place: dict | None = None) -> None:
    """Stellt sicher, dass der Zielstandort gültig ist und existiert.

    Ein **Ort** braucht keine Existenzprüfung (er ist die Adresse selbst) – nur einen Inhalt."""
    if ltype not in LOCATION_TYPES:
        raise HTTPException(400, detail="Ungültiger Standort-Typ")
    if ltype == "place":
        if not place_label(place):
            raise HTTPException(400, detail="Ort braucht eine Bezeichnung, Adresse oder Koordinaten")
        return
    if lid is None or location_label(db, ltype, lid) is None:
        raise HTTPException(400, detail="Zielstandort nicht gefunden")


def resolve_physical_location(
    db: Session, ltype: str | None, lid: int | None, _depth: int = 0
) -> tuple[str | None, int | None]:
    """Folgt ``instance``→``instance``-Ketten bis zum **physischen** Standort
    (Ort/Person/Unternehmen). So «wandert» eine verbaute Komponente mit ihrer Produkt-
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


def resolve_physical_place(
    db: Session, ltype: str | None, lid: int | None, _depth: int = 0
) -> dict | None:
    """Wie ``resolve_physical_location``, liefert aber den **Adress-Snapshot** des physischen
    Endpunkts, wenn die Kette an einem Ort endet (sonst ``None``). Für die Logistik
    (Versandadresse/Adressvergleich) über verschachtelte Behälter hinweg."""
    if ltype == "place":
        return None      # der Aufrufer kennt seinen eigenen place bereits
    if ltype != "instance" or lid is None or _depth > 10:
        return None
    host = (
        db.query(Instance)
        .filter(Instance.object_id == lid, Instance.is_active == True)
        .first()
    )
    if not host:
        return None
    if host.location_type == "place":
        return host.place
    return resolve_physical_place(db, host.location_type, host.location_id, _depth + 1)
