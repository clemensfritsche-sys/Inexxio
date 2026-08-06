"""Instanzen und Einzelinstanzen – die EINE Schreibstelle.

Hier und nur hier entstehen Einzelinstanzen und ihre Nummern. Wer eine Menge wissen
will, fragt hier; niemand liest sie aus einer Spalte, weil es keine gibt.

Die Nummer einer Einzelinstanz ist ``<Objektnummer der Instanz>-<suffix>``. Sie kommt
NICHT aus ``object_id_seq``: eine 1000er-Charge würde sonst 1000 Nummern des gemeinsamen
Kreises verbrauchen – genau dafür gibt es die Instanz-Ebene.
"""

from typing import Iterable, Optional

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models import Article, Instance, InstanceUnit
from ..models.instance import KINDS
from .objects import next_object_id, obj_nr

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

def create_instance(db: Session, *, article: Article, kind: str, count: int,
                    label: Optional[str] = None) -> Instance:
    """Neue Instanz mit ``count`` Einzelinstanzen.

    ``kind`` und ``count`` werden ausdrücklich verlangt – kein Erraten aus dem Artikel.
    """
    if kind not in KINDS:
        raise HTTPException(
            status_code=400,
            detail=f"Unbekannter Instanz-Typ «{kind}». Erlaubt: {', '.join(KINDS)}.",
        )
    if count < 1:
        raise HTTPException(
            status_code=400,
            detail="Eine Instanz braucht mindestens eine Einzelinstanz.",
        )

    instance = Instance(
        object_id=next_object_id(db, "instance"),
        article_id=article.id,
        kind=kind,
        label=label,
    )
    db.add(instance)
    db.flush()  # id für die Einzelinstanzen
    add_units(db, instance, count)
    return instance


def add_units(db: Session, instance: Instance, count: int) -> list[InstanceUnit]:
    """``count`` weitere Einzelinstanzen – die EINZIGE Stelle, die Suffixe vergibt.

    Der Suffix ist **kumulierend**: ``MAX(suffix)+1``, ermittelt unter Zeilensperre auf
    der Instanz, damit zwei gleichzeitige Anlagen nicht dieselbe Nummer ziehen. Da nur
    soft gelöscht wird, bleibt eine vergebene Nummer in ``MAX`` sichtbar und kommt nie
    zurück – ein gespeicherter Zähler wäre eine zweite Wahrheit neben den Zeilen.
    """
    if count < 1:
        raise HTTPException(status_code=400, detail="Anzahl muss mindestens 1 sein.")

    # Zeilensperre auf der Instanz: sie serialisiert die Suffix-Vergabe dieser Gruppe.
    locked = (
        db.query(Instance)
        .filter(Instance.id == instance.id)
        .with_for_update()
        .first()
    )
    if locked is None:
        raise HTTPException(status_code=404, detail="Instanz nicht gefunden.")

    highest = (
        db.query(func.max(InstanceUnit.suffix))
        .filter(InstanceUnit.instance_id == instance.id)
        .scalar()
    )
    start = int(highest or 0) + 1

    created = [InstanceUnit(instance_id=instance.id, suffix=s)
               for s in range(start, start + count)]
    db.add_all(created)
    db.flush()
    return created
