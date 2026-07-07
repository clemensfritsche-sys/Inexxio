"""Standorte für Instanzen (Prozessschritt «Bewegung»).

Eine Instanz **kann** einen Standort haben (sie darf auch standortlos sein, ``NULL`` =
«noch nicht festgelegt»); ist einer gesetzt, ist er stets ein Datensatzobjekt mit
9-stelliger Nummer:

    lagerplatz → StorageLocation
    user       → UserProfile (Mitarbeiter, Lieferant, Kunde)
    instance   → andere Instanz (z. B. eingebaut in Maschine/Behälter ODER ein
                 Lagerplatz-als-Instanz, ``articles.is_location``)

Bei der Auftragsfreigabe startet eine Instanz beim **Lieferanten** (Lieferanten-
Beschaffung als erster Schritt) oder **ohne Standort** (siehe
``services/serialization.py``). Den realen Ort setzt der erste Bewegungs-Schritt; die
Vorgabe-Lieferadresse steht in ``company_settings.default_receiving_location_id``.
"""

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..models import Article, Instance, StorageLocation, UserProfile
from ..schemas.movement import LOCATION_TYPES


def _user_label(u: UserProfile) -> str:
    return u.display_name


def create_location_instance(
    db: Session, article: Article, parent_type: str | None, parent_id: int | None, actor_id: int | None
) -> Instance:
    """Eine **Lagerplatz-Instanz** anlegen (F): eine Instanz eines ``is_location``-Artikels,
    die ein **Ort** ist statt Bestand. Sie trägt ``disposition='location'`` (und ist damit
    über ``inventory.in_stock_clauses`` automatisch aus Bestand/FIFO/Reservierung ausgeschlossen)
    und **keinen** Auftrag (``order_id=None``) – ein Ort wird deklariert, nicht produziert.

    Optionaler Eltern-Standort (``parent_type``/``parent_id``) = die Hierarchie (Gebäude→Fach):
    eine Orts-Instanz kann in einem Lagerplatz/bei einer Person/in einer anderen Orts-Instanz
    liegen. Leer = oberste Ebene (standortlos). Committet NICHT – der Aufrufer schliesst ab."""
    from ..models.base import utcnow
    from .admin import log_audit
    from .events import emit
    from .objects import next_object_id

    if not article.is_location:
        raise HTTPException(400, detail="Artikel ist kein Standort-Typ (is_location=false)")
    if parent_type is not None or parent_id is not None:
        if parent_type is None or parent_id is None:
            raise HTTPException(400, detail="Eltern-Standort braucht Typ UND Objektnummer")
        validate_location(db, parent_type, parent_id)   # muss existieren
    inst = Instance(
        object_id=next_object_id(db, "instance"),
        article_id=article.id, order_id=None,
        kind="unit", quantity=1,
        quality="passed", disposition="location", released_at=utcnow(),
        location_type=parent_type, location_id=parent_id,
    )
    db.add(inst)
    db.flush()
    log_audit(db, "instances", None, f"Lagerplatz-Instanz «{article.name}» angelegt",
              actor_id, object_id=inst.object_id)
    emit(db, "location.created", object_type="instance", object_id=inst.object_id,
         payload={"article_id": article.id}, actor_id=actor_id)
    return inst


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
    if ltype == "company":
        from ..models import CompanySettings
        c = db.query(CompanySettings).filter(CompanySettings.object_id == lid).first()
        return (c.company_name or _obj_nr(lid)) if c else _obj_nr(lid)
    return None


LocKey = tuple[str | None, int | None]


def location_labels(db: Session, pairs: list[LocKey]) -> dict[LocKey, str | None]:
    """**Batch**-Variante von ``location_label``: EIN Query je Standort-Typ statt einem je
    Zeile (N+1) – für Feeds/Listen (Instanz-Feed, Artikel-Bestand, Auftrags-Instanzen)."""
    ids: dict[str, set[int]] = {"lagerplatz": set(), "user": set(), "instance": set(), "company": set()}
    for ltype, lid in pairs:
        if ltype in ids and lid is not None:
            ids[ltype].add(lid)
    from ..models import CompanySettings
    companies = {
        c.object_id: (c.company_name or _obj_nr(c.object_id))
        for c in db.query(CompanySettings).filter(CompanySettings.object_id.in_(ids["company"]))
    } if ids["company"] else {}
    existing_loc = {
        oid for (oid,) in db.query(StorageLocation.object_id).filter(
            StorageLocation.object_id.in_(ids["lagerplatz"]), StorageLocation.is_active == True)
    } if ids["lagerplatz"] else set()
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
        elif ltype == "lagerplatz":
            out[key] = _obj_nr(lid) if lid in existing_loc else None
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


def resolve_physical_location(
    db: Session, ltype: str | None, lid: int | None, _depth: int = 0
) -> tuple[str | None, int | None]:
    """Folgt ``instance``→``instance``-Ketten bis zum **physischen** Standort
    (Lagerplatz/Person). So «wandert» eine verbaute Komponente mit ihrer Produkt-
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
