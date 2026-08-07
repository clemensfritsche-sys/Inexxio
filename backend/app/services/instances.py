"""Instanzen und Einzelinstanzen – die EINE Schreibstelle.

Hier und nur hier entstehen Einzelinstanzen und ihre Nummern. Wer eine Menge wissen
will, fragt hier; niemand liest sie aus einer Spalte, weil es keine gibt.

**Erzeugt wird ausschliesslich mit der Instanz**, und die entsteht ausschliesslich mit
einem Auftrag (``services/materialize``). Es gibt darum kein Nachträglich-Hinzufügen und
kein Einzeln-Anlegen mehr: beides waren zweite Türen, durch die eine Einzelinstanz ohne
Auftrag in die Welt kam – ohne Prozess, an dem sie hängt, und ohne Ereignis, das ihre
Entstehung festhält (Testnotiz #678).

**Einen Zustand hat die Instanz nicht.** Sie ist eine Gruppe; gearbeitet wird an der
Einzelinstanz, und deren Zustand ist der einzige, den es gibt. Ihn auf die Gruppe zu
projizieren geht nur, solange genau ein Stück darunter liegt – bei einer Charge mit
gemischten Zuständen gibt es keine richtige Antwort, und jede gewählte wäre eine
Behauptung (Testnotiz #675).

Die Nummer einer Einzelinstanz ist ``<Objektnummer der Instanz>-<suffix>``. Sie kommt
NICHT aus ``object_id_seq``: eine 1000er-Charge würde sonst 1000 Nummern des gemeinsamen
Kreises verbrauchen – genau dafür gibt es die Instanz-Ebene.
"""

from typing import Iterable, Optional

from fastapi import HTTPException
from sqlalchemy import func, insert
from sqlalchemy.orm import Session

from ..models import Article, Instance, InstanceUnit
from ..models.instance import KINDS
from .objects import next_object_ids, obj_nr

# Trennzeichen zwischen Instanz-Nummer und Suffix. Eine Stelle, damit Erzeugen und
# Lesen (``parse_unit_number``) nicht auseinanderlaufen können.
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


def find_unit(db: Session, text: str) -> Optional[InstanceUnit]:
    """Einzelinstanz zu einer Nummer ``<instanznr>-<suffix>`` (oder ``None``)."""
    parsed = parse_unit_number(text)
    if not parsed:
        return None
    object_id, suffix = parsed
    instance = db.query(Instance).filter(Instance.object_id == object_id).first()
    if instance is None:
        return None
    return (
        db.query(InstanceUnit)
        .filter(InstanceUnit.instance_id == instance.id, InstanceUnit.suffix == suffix)
        .first()
    )


# ---------------------------------------------------------------------------
# Mengen – immer gezählt, nie gespeichert
# ---------------------------------------------------------------------------

def quantity(db: Session, instance: Instance) -> int:
    """Menge der Instanz = Anzahl ihrer aktiven Einzelinstanzen."""
    return int(
        db.query(func.count(InstanceUnit.id))
        .filter(InstanceUnit.instance_id == instance.id, InstanceUnit.is_active.is_(True))
        .scalar() or 0
    )


def quantities(db: Session, instance_ids: Iterable[int]) -> dict[int, int]:
    """Mengen für viele Instanzen in EINER Abfrage (Feed/Listen, kein N+1)."""
    ids = list(instance_ids)
    if not ids:
        return {}
    rows = (
        db.query(InstanceUnit.instance_id, func.count(InstanceUnit.id))
        .filter(InstanceUnit.instance_id.in_(ids), InstanceUnit.is_active.is_(True))
        .group_by(InstanceUnit.instance_id)
        .all()
    )
    counts = {int(iid): int(n) for iid, n in rows}
    # Eine Instanz ohne Einzelinstanzen hat die Menge 0 – das ist eine Antwort, kein Loch.
    return {int(i): counts.get(int(i), 0) for i in ids}


def units_of(db: Session, instance: Instance) -> list[InstanceUnit]:
    """Die aktiven Einzelinstanzen einer Instanz, aufsteigend nach Suffix."""
    return (
        db.query(InstanceUnit)
        .filter(InstanceUnit.instance_id == instance.id, InstanceUnit.is_active.is_(True))
        .order_by(InstanceUnit.suffix)
        .all()
    )


# ---------------------------------------------------------------------------
# Anlegen
# ---------------------------------------------------------------------------

def create_instances(db: Session, *, article: Article, kind: str,
                     instance_count: int, units_each: int,
                     label: Optional[str] = None) -> list[Instance]:
    """``instance_count`` Instanzen mit je ``units_each`` Einzelinstanzen.

    **Die eine Erzeugungsstelle.** Einzelserialisierung und Charge sind hier keine zwei
    Codepfade, sondern zwei Parameterwerte (``services/materialize.plan`` rechnet sie
    aus): 3 Stück einzeln = 3 × 1, eine Charge über 3 = 1 × 3.

    Drei Anweisungen, unabhängig von der Menge – bei 5000 Stück wären 5000 einzelne
    ``INSERT`` der Grund, warum «flüssig» nicht mehr stimmt. Die Objektnummern kommen
    als **Block aus der Sequence** (ein Roundtrip, race-sicher); die Suffixe beginnen bei
    1, weil diese Instanzen in diesem Augenblick entstehen und noch keine tragen können.
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
            {"object_id": oid, "article_id": article.id, "kind": kind, "label": label}
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
