"""**Der Ort** – die eine Stelle (PROCESS_CORE §15, SYSTEM_LOGIC §7, ADR 009).

Der Ort eines Stücks ist eine **Beobachtung**, kein Zustand: die letzte Zeile in
``unit_places``. Dieses Modul schreibt sie und liest sie in beide Richtungen –
«wo ist X?» (die Kette) und «was liegt hier?» (die Liste). Beide lesen dieselbe
Tabelle; eine zweite für die Gegenrichtung wäre eine zweite Wahrheit (§15.9).

**Was dieses Modul ausdrücklich NICHT tut** (§15.6, O3): es ändert keinen Status, keine
Zugehörigkeit und schreibt nichts in den Ereignis-Log. Das ist die Robustheitsgarantie,
konstruktiv statt geprüft – weil eine Ablage nichts anfasst ausser dem Ort, muss keine
andere Regel im System von ihr wissen.

**Tolerant lesen, streng schreiben.** Geschrieben wird nur auf einen Halter, den es
wirklich gibt (sonst 400 mit Nummer). Gelesen wird auch eine Nummer, die inzwischen ins
Leere zeigt – sie wird als solche **gemeldet** und nicht zu «kein Ort» aufgelöst (O2.4);
ein stiller Rückfall verbärge genau den Fehler, den man sehen müsste (G3.3).
"""

from dataclasses import dataclass
from typing import Iterable, Optional

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models import CompanySettings, Instance, InstanceUnit, UnitPlace
from ..models.unit_place import SOURCES, SOURCE_SCAN
from . import address as addr
from . import objects as obj
from . import people

#: Wie tief eine Kette höchstens verfolgt wird. Sie ist fachlich kurz (Behälter →
#: Regal → Halle → Werk); die Schranke schützt gegen einen Zyklus, den ein Mensch
#: gebaut hat, und ist **kein** stiller Deckel: wird sie erreicht, sagt die Antwort es.
MAX_HOPS = 10


@dataclass
class Holder:
    """Ein Halter, aufgelöst. ``type``/``name`` sind ``None``, wenn die Objektnummer
    ins Leere zeigt – dann ist genau das die Aussage (O2.4)."""

    object_id: int
    type: Optional[str] = None
    name: Optional[str] = None

    @property
    def known(self) -> bool:
        return self.type is not None


@dataclass
class Hop:
    """Eine Station der Kette. Die **Anschrift** am Ende trägt keine Objektnummer –
    sie ist kein Datensatz, also auch nicht anklickbar."""

    object_id: Optional[int]
    type: Optional[str]
    name: Optional[str]


@dataclass
class Chain:
    """Die Kette von innen nach aussen. ``truncated``/``cycle`` sind Befunde, keine
    Kosmetik: eine stumm gekappte Kette läse sich wie die ganze Wahrheit."""

    hops: list[Hop]
    truncated: bool = False
    cycle: bool = False


# ─── Schreiben ───────────────────────────────────────────────────────────────────

def record(db: Session, unit_ids: Iterable[int], holder_object_id: int,
           actor_id: Optional[int], source: str = SOURCE_SCAN) -> list[UnitPlace]:
    """Ablage: je Stück **eine** Zeile. Append-only – es gibt keinen Update-Pfad.

    Bewusst **ohne** Auftrag, ohne Modul, ohne offenen Prozess (O1.5): freier Bestand
    ist der Normalzustand, und genau dort war die Frage «wo ist es» bisher leer.
    """
    ids = [int(u) for u in dict.fromkeys(unit_ids)]   # Reihenfolge stabil, ohne Dubletten
    if not ids:
        raise HTTPException(400, "Keine Einzelinstanz angegeben.")
    if source not in SOURCES:
        raise HTTPException(400, f"Unbekannte Herkunft '{source}'. Erlaubt: {', '.join(SOURCES)}.")

    holder = resolve_holder(db, holder_object_id)
    if not holder.known:
        # Streng schreiben: ein Halter, den es nicht gibt, ist ein Tippfehler – und ein
        # Ort, der auf nichts zeigt, ist schlimmer als kein Ort.
        raise HTTPException(400, f"Halter {obj.obj_nr(holder_object_id)} gibt es nicht.")

    units = db.query(InstanceUnit).filter(InstanceUnit.id.in_(ids)).all()
    found = {u.id for u in units}
    missing = [i for i in ids if i not in found]
    if missing:
        raise HTTPException(404, f"Einzelinstanz {missing[0]} gibt es nicht.")

    # Ein Stück kann nicht in seiner eigenen Instanz liegen – das wäre der kürzeste
    # denkbare Zyklus, und er entstünde durch einen Scan auf das eigene Etikett.
    own = {u.instance_id for u in units}
    inst_ids = {i.id for i in db.query(Instance.id)
                .filter(Instance.object_id == holder_object_id).all()}
    if own & inst_ids:
        raise HTTPException(400,
                            f"Ein Stück kann nicht in seiner eigenen Instanz "
                            f"{obj.obj_nr(holder_object_id)} liegen.")

    rows = [UnitPlace(instance_unit_id=u.id, holder_object_id=holder_object_id,
                      actor_id=actor_id, source=source) for u in units]
    db.add_all(rows)
    db.flush()
    return rows


# ─── Lesen: wo ist X ─────────────────────────────────────────────────────────────

def _latest_ids(db: Session, unit_ids: Optional[Iterable[int]] = None):
    """Die ``id`` der jeweils **letzten** Beobachtung je Stück, als Unterabfrage.

    Massgeblich ist die höchste ``id``, nicht der jüngste Zeitstempel: zwei Ablagen
    können dieselbe Sekunde tragen (G5.2).
    """
    q = db.query(func.max(UnitPlace.id).label("id")).group_by(UnitPlace.instance_unit_id)
    if unit_ids is not None:
        q = q.filter(UnitPlace.instance_unit_id.in_(list(unit_ids)))
    return q.subquery()


def current(db: Session, unit_ids: Iterable[int]) -> dict[int, int]:
    """``{Einzelinstanz-id: Halter-Objektnummer}`` – eine Abfrage, kein N+1.

    Stücke ohne jede Beobachtung fehlen im Ergebnis. Das ist die ehrliche Antwort
    «nicht bekannt»; ein geratener Ort wäre die Alternative (G3.1).
    """
    ids = [int(u) for u in unit_ids]
    if not ids:
        return {}
    latest = _latest_ids(db, ids)
    rows = (db.query(UnitPlace.instance_unit_id, UnitPlace.holder_object_id)
            .join(latest, UnitPlace.id == latest.c.id).all())
    return {int(u): int(h) for u, h in rows}


def current_of(db: Session, unit_id: int) -> Optional[int]:
    return current(db, [unit_id]).get(int(unit_id))


def history(db: Session, unit_id: int, limit: int = 200) -> list[UnitPlace]:
    """Die Beobachtungen eines Stücks, neueste zuerst. Gekappt **und ausgewiesen**
    durch den Aufrufer – ein stiller Deckel läse sich wie Vollständigkeit."""
    return (db.query(UnitPlace)
            .filter(UnitPlace.instance_unit_id == int(unit_id))
            .order_by(UnitPlace.id.desc()).limit(limit).all())


# ─── Lesen: wer ist das ──────────────────────────────────────────────────────────

def resolve_holders(db: Session, object_ids: Iterable[int]) -> dict[int, Holder]:
    """Halter-Objektnummern auflösen – **batch**, ein Treffer je Typ.

    Es gibt **keine Whitelist**: Halter ist alles, was eine Objektnummer hat (O2.2).
    Was sich nicht auflösen lässt, kommt als ``Holder`` **ohne** Typ zurück und wird
    damit gemeldet statt verschwiegen.
    """
    ids = [int(o) for o in dict.fromkeys(object_ids)]
    if not ids:
        return {}
    out: dict[int, Holder] = {i: Holder(object_id=i) for i in ids}

    for oid, label in db.query(Instance.object_id, Instance.label).filter(
            Instance.object_id.in_(ids)).all():
        out[int(oid)] = Holder(int(oid), "instance", label or None)

    for oid, name in db.query(CompanySettings.object_id, CompanySettings.company_name).filter(
            CompanySettings.object_id.in_(ids)).all():
        out[int(oid)] = Holder(int(oid), "organization", name or None)

    for oid in ids:
        if out[oid].known:
            continue
        name = people.name_by_object_id(db, oid)
        if name:
            out[oid] = Holder(oid, "user", name)
    return out


def resolve_holder(db: Session, object_id: int) -> Holder:
    return resolve_holders(db, [object_id])[int(object_id)]


# ─── Lesen: die Kette ────────────────────────────────────────────────────────────

def _instance_place(db: Session, instance_object_id: int) -> Optional[int]:
    """Wo liegt dieser Behälter selbst? Ein Behälter ist eine **Instanz**; sein Ort ist
    der seiner Einzelinstanzen.

    Stehen sie an verschiedenen Orten, gibt es **keine** einzelne richtige Antwort – dann
    endet die Kette hier, statt einen der Orte zu behaupten (G3.1).
    """
    unit_ids = [u.id for u in db.query(InstanceUnit.id)
                .join(Instance, Instance.id == InstanceUnit.instance_id)
                .filter(Instance.object_id == int(instance_object_id)).all()]
    if not unit_ids:
        return None
    holders = set(current(db, unit_ids).values())
    return holders.pop() if len(holders) == 1 else None


def chain(db: Session, holder_object_id: int) -> Chain:
    """Die Kette von innen nach aussen: Behälter → Halle → Werk → **Anschrift**.

    Zyklensicher und begrenzt (``MAX_HOPS``). Beides wird **gemeldet**, nicht
    stillschweigend abgeschnitten.
    """
    hops: list[Hop] = []
    seen: set[int] = set()
    cur: Optional[int] = int(holder_object_id)
    cycle = False

    while cur is not None and len(hops) < MAX_HOPS:
        if cur in seen:
            cycle = True
            break
        seen.add(cur)
        h = resolve_holders(db, [cur])[cur]
        hops.append(Hop(object_id=h.object_id, type=h.type, name=h.name))

        if h.type == "instance":
            cur = _instance_place(db, cur)          # der Behälter liegt seinerseits …
        elif h.type == "organization":
            _append_address(db, cur, hops)          # … das Werk endet in seiner Anschrift
            cur = None
        else:
            cur = None                              # Person / unbekannt: die Kette endet
    return Chain(hops=hops, truncated=cur is not None and not cycle, cycle=cycle)


def _append_address(db: Session, company_object_id: int, hops: list[Hop]) -> None:
    """Die Anschrift als letzte Station – **ohne** Objektnummer, denn sie ist kein
    Datensatz. Gelesen über die eine Adressdarstellung (``services/address``)."""
    company = (db.query(CompanySettings)
               .filter(CompanySettings.object_id == int(company_object_id)).first())
    if not company:
        return
    line = addr.one_line(addr.of_company(company))
    if line:
        hops.append(Hop(object_id=None, type="address", name=line))


# ─── Lesen: was liegt hier ───────────────────────────────────────────────────────

def contents(db: Session, holder_object_id: int, limit: int = 60,
             offset: int = 0) -> tuple[list[InstanceUnit], int]:
    """Die Stücke, deren **letzte** Beobachtung auf diese Objektnummer zeigt.

    Nie alles auf einmal: seitenweise, mit Gesamtzahl daneben – bei einer 5000er-Charge
    wäre die volle Liste ein Vielfaches des Datensatzes, an dem sie hängt.
    """
    latest = _latest_ids(db)
    q = (db.query(InstanceUnit)
         .join(UnitPlace, UnitPlace.instance_unit_id == InstanceUnit.id)
         .join(latest, UnitPlace.id == latest.c.id)
         .filter(UnitPlace.holder_object_id == int(holder_object_id)))
    total = q.count()
    rows = q.order_by(InstanceUnit.instance_id, InstanceUnit.suffix).offset(offset).limit(limit).all()
    return rows, total
