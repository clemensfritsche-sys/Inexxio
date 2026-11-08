"""Instanzen und Einzelinstanzen – die EINE Schreibstelle.

Hier und nur hier entstehen Einzelinstanzen und ihre Nummern; Mengen werden hier gezählt,
nie aus einer Spalte gelesen. **Erzeugt wird nur mit der Instanz**, und die nur mit einem
Auftrag (``services/materialize``) – keine Einzelinstanz ohne Prozess und Ereignis.

**Die Instanz hat keinen Zustand** – sie ist eine Gruppe; Zustand haben nur ihre Stücke.

Die Nummer einer Einzelinstanz ist ``<Objektnummer der Instanz>-<suffix>``, nicht aus
``object_id_seq`` – eine Charge verbraucht keine Nummern des gemeinsamen Kreises.
"""

from typing import Iterable, Optional

from fastapi import HTTPException
from sqlalchemy import func, insert, tuple_
from sqlalchemy.orm import Session

from ..models import Article, Instance, InstanceUnit
from ..models.instance import KINDS
from .objects import next_object_ids, obj_nr

# Trennzeichen zwischen Instanz-Nummer und Suffix – eine Stelle für Erzeugen und Lesen
# (``parse_unit_number``).
SEP = "-"


# ---------------------------------------------------------------------------
# Nummern
# ---------------------------------------------------------------------------

def unit_number(instance: Instance, unit: InstanceUnit) -> str:
    """Die Nummer einer Einzelinstanz, z. B. ``100000123-7``."""
    return f"{obj_nr(instance.object_id)}{SEP}{unit.suffix}"


def parse_unit_number(text: str) -> Optional[tuple[int, int]]:
    """``"100000123-7"`` → ``(100000123, 7)``. ``None``, wenn es keine Einzelinstanz-Nummer
    ist – das ist eine Auskunft, kein Fehler: der Aufrufer prüft damit die Form."""
    if not text or SEP not in text:
        return None
    head, _, tail = text.partition(SEP)
    if not head.strip().isdigit() or not tail.strip().isdigit():
        return None
    return int(head), int(tail)


def unit_number_matches(query: str, instance_object_id, suffix):
    """SQL-Bedingung «diese Stücknummer passt zur Eingabe» — ``<instanznr>-<suffix>``.

    **Die Trennung IST die Aussage** – wer einen Teil tippt, meint nur ihn:

    ``100000123-7``  beide Teile – die Instanz enthält «100000123», der Suffix ist 7
    ``-7``           nur der Suffix: «das siebte Stück»
    ``00123``        die Instanz – oder, wenn die Zahl klein genug ist, ein Suffix
    """
    from sqlalchemy import String, and_, func, or_

    q = (query or "").strip()
    if not q:
        return True
    head, sep, tail = q.partition(SEP)
    head, tail = head.strip(), tail.strip()
    if sep:
        # Ausdrücklich getrennt: der Suffix ist gemeint, die Instanz nur, wenn genannt.
        by_suffix = func.cast(suffix, String) == tail if tail.isdigit() else False
        if not head:
            return by_suffix
        by_head = func.cast(instance_object_id, String).like(f"%{head}%")
        return and_(by_head, by_suffix) if tail.isdigit() else by_head
    tests = [func.cast(instance_object_id, String).like(f"%{q}%")]
    if q.isdigit():
        tests.append(func.cast(suffix, String) == q)
    return or_(*tests)


def find_unit(db: Session, text: str) -> Optional[InstanceUnit]:
    """Einzelinstanz zu einer Nummer ``<instanznr>-<suffix>`` (oder ``None``)."""
    return find_units(db, [text]).get(text)


def find_units(db: Session, numbers: Iterable[str]) -> dict[str, InstanceUnit]:
    """Nummern → Einzelinstanzen, **eine** Abfrage für alle. Was nicht auflöst, fehlt."""
    wanted: dict[tuple[int, int], str] = {}
    for text in numbers:
        parsed = parse_unit_number(text)
        if parsed:
            wanted[parsed] = text
    if not wanted:
        return {}
    rows = (
        db.query(InstanceUnit, Instance.object_id)
        .join(Instance, Instance.id == InstanceUnit.instance_id)
        .filter(tuple_(Instance.object_id, InstanceUnit.suffix).in_(list(wanted)))
        .all()
    )
    return {wanted[(int(oid), unit.suffix)]: unit for unit, oid in rows}


def unit_numbers(db: Session, units: Iterable[InstanceUnit]) -> dict[int, str]:
    """Nummern zu Einzelinstanzen — **eine** Abfrage, kein N+1.

    Jede Einzelinstanz hat ihre Instanz (Fremdschlüssel), also fehlt hier nie eine.
    """
    ids = {u.instance_id for u in units}
    if not ids:
        return {}
    heads = dict(db.query(Instance.id, Instance.object_id).filter(Instance.id.in_(ids)).all())
    return {u.id: f"{obj_nr(heads[u.instance_id])}{SEP}{u.suffix}" for u in units}


def number_of(db: Session, unit: InstanceUnit) -> str:
    """Die Nummer **eines** Stücks – für Meldungen, die es nennen."""
    return unit_numbers(db, [unit])[unit.id]


# ---------------------------------------------------------------------------
# Mengen – immer gezählt, nie gespeichert
# ---------------------------------------------------------------------------

def quantity(db: Session, instance: Instance) -> int:
    """Menge der Instanz = Anzahl ihrer aktiven Einzelinstanzen."""
    return int(
        db.query(func.count(InstanceUnit.id))
        .filter(InstanceUnit.instance_id == instance.id)
        .scalar() or 0
    )


def states(db: Session, instance_ids: Iterable[int]) -> dict[int, dict[str, int]]:
    """Je Instanz: **Zustand → Anzahl Stücke**, in EINER Abfrage.

    Die vollständige Auskunft über eine Instanz (``quantities`` summiert sie) – eine
    Aufstellung, kein Zustand der Gruppe.
    """
    ids = list(instance_ids)
    if not ids:
        return {}
    rows = (
        db.query(InstanceUnit.instance_id, InstanceUnit.status, func.count(InstanceUnit.id))
        .filter(InstanceUnit.instance_id.in_(ids))
        .group_by(InstanceUnit.instance_id, InstanceUnit.status)
        .all()
    )
    out: dict[int, dict[str, int]] = {int(i): {} for i in ids}
    for iid, status, n in rows:
        out[int(iid)][status] = int(n)
    # Eine Instanz ohne Einzelinstanzen bekommt ein leeres Bild.
    return out


def quantities(db: Session, instance_ids: Iterable[int]) -> dict[int, int]:
    """Mengen für viele Instanzen in EINER Abfrage (Feed/Listen, kein N+1)."""
    return {i: sum(by_status.values()) for i, by_status in states(db, instance_ids).items()}


def article_states(db: Session, *, article_id: int) -> dict[str, int]:
    """Über **alle** Instanzen eines Artikels: Zustand → Anzahl Stücke. EINE Abfrage – nicht
    die Summe der angezeigten Seite."""
    rows = (
        db.query(InstanceUnit.status, func.count(InstanceUnit.id))
        .join(Instance, Instance.id == InstanceUnit.instance_id)
        .filter(Instance.article_id == article_id)
        .group_by(InstanceUnit.status)
        .all()
    )
    return {status: int(n) for status, n in rows}


def units_page(db: Session, instance: Instance, *, statuses: Optional[list[str]] = None,
               limit: int, offset: int) -> tuple[list[InstanceUnit], int]:
    """Eine **Seite** Einzelinstanzen, aufsteigend nach Suffix – plus wie viele es sind.

    Gefiltert nach einer **Menge von Zuständen** (ein Segment oder ein ganzer Block der
    Aufstellung). Die **einzige** Stelle, die Nummern herausgibt – nie alle auf einmal.
    """
    q = db.query(InstanceUnit).filter(
        InstanceUnit.instance_id == instance.id)
    if statuses:
        q = q.filter(InstanceUnit.status.in_(statuses))
    total = int(q.with_entities(func.count(InstanceUnit.id)).scalar() or 0)
    rows = q.order_by(InstanceUnit.suffix).limit(limit).offset(offset).all()
    return rows, total


# ---------------------------------------------------------------------------
# Anlegen
# ---------------------------------------------------------------------------

def create_instances(db: Session, *, article: Article, kind: str,
                     instance_count: int, units_each: int) -> list[Instance]:
    """``instance_count`` Instanzen mit je ``units_each`` Einzelinstanzen.

    **Die eine Erzeugungsstelle**: Einzelserialisierung (3 × 1) und Charge (1 × 3) sind
    zwei Parameterwerte (``services/materialize.plan``). Drei Anweisungen unabhängig von der
    Menge; die Objektnummern als Block aus der Sequence, Suffixe ab 1.
    """
    if kind not in KINDS:
        raise HTTPException(
            status_code=400,
            detail=f"Unbekannter Instanz-Typ «{kind}». Erlaubt: {', '.join(KINDS)}.",
        )
    if instance_count < 1 or units_each < 1:
        raise HTTPException(
            status_code=400,
            detail="Eine Instanz braucht mindestens eine Einzelinstanz.",
        )

    object_ids = next_object_ids(db, instance_count, "instance")
    db.execute(
        insert(Instance),
        [
            {"object_id": oid, "article_id": article.id, "kind": kind}
            for oid in object_ids
        ],
    )
    created = (
        db.query(Instance)
        .filter(Instance.object_id.in_(object_ids))
        .order_by(Instance.object_id)
        .all()
    )
    if len(created) != instance_count:
        raise HTTPException(
            status_code=500,
            detail="Instanzen konnten nicht angelegt werden – die Freigabe wird abgebrochen.",
        )
    db.execute(
        insert(InstanceUnit),
        [
            {"instance_id": inst.id, "suffix": s}
            for inst in created
            for s in range(1, units_each + 1)
        ],
    )
    return created
