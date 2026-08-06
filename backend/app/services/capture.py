"""Datenerfassung – Werte an einer **Einzelinstanz**.

Was erfasst wird, sagt der Artikel (``articles.capture_fields``); erfasst wird immer am
Stück. Die Bewertung ist eine Aussage über die Messung, nicht über den Prozess: sie hält
fest, ob die bewertbaren Felder in Ordnung waren – sie sperrt nichts, stuft nichts hoch
und löst nichts aus. Das war Prozesslogik und ist entfallen.

Die Feldform ist unverändert die bisherige (das Frontend-Vokabular bleibt gültig):

    {"key": "laenge", "label": "Länge", "type": "measure", "target": 40, "tolerance": 0.5}
    {"key": "grat",   "label": "Gratfrei", "type": "bool"}
    {"key": "notiz",  "label": "Bemerkung", "type": "text"}
    {"key": "foto",   "label": "Foto", "type": "photo"}      # informativ
    {"key": "sig",    "label": "Unterschrift", "type": "signature"}
"""

from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..models import Article, Capture, InstanceUnit

# Feldtypen, die ein Urteil erzeugen können. Alles andere wird erfasst, aber nicht bewertet.
EVALUABLE = ("measure", "bool")
# Feldtypen, die eine Datei tragen – erfasst werden muss trotzdem (Präsenz), bewertet nicht.
MEDIA = ("photo", "signature")


def fields_of(article: Article) -> list[dict]:
    """Die Erfassungsmaske des Artikels. Leer heisst: hier wird nichts erfasst."""
    return list(article.capture_fields or [])


def field_ok(field: dict, value) -> bool:
    """Bewertet ein einzelnes Feld. Nicht bewertbare Typen sind immer in Ordnung."""
    ftype = field.get("type")
    if ftype == "measure":
        if value is None or value == "":
            return False
        try:
            v = float(value)
        except (TypeError, ValueError):
            return False
        target = field.get("target")
        if target is None:
            return True  # nur erfasst, kein Soll → informativ
        tol = field.get("tolerance") or 0
        return abs(v - float(target)) <= float(tol)
    if ftype == "bool":
        return value is True or value == "true" or value == 1
    return True  # text/photo/signature → informativ


def evaluate(fields: list[dict], values: dict) -> Optional[str]:
    """``"passed"`` | ``"failed"`` | ``None``.

    ``None`` heisst «nichts Bewertbares dabei» – eine reine Text-/Foto-Erfassung hat kein
    Urteil. Ein erfundenes «bestanden» wäre eine Aussage, die niemand getroffen hat.
    Ein ``measure``-Feld **ohne Soll** ist ebenfalls kein Urteil, nur eine Ablesung.
    """
    judged = [f for f in (fields or [])
              if f.get("type") in EVALUABLE
              and not (f.get("type") == "measure" and f.get("target") is None)]
    if not judged:
        return None
    return "passed" if all(field_ok(f, (values or {}).get(f.get("key"))) for f in judged) else "failed"


def record(db: Session, *, unit: InstanceUnit, article: Article, values: dict,
           actor_id: int, note: Optional[str] = None) -> Capture:
    """Eine Erfassung an genau einer Einzelinstanz festhalten.

    Fehlt die Maske oder ein Pflichtwert, ist das ein Fehler mit Ursache – kein
    Platzhalter, kein leerer Wert, keine Teilaufnahme.
    """
    fields = fields_of(article)
    if not fields:
        raise HTTPException(
            status_code=400,
            detail=(f"Für den Artikel «{article.name}» ist keine Erfassungsmaske "
                    f"hinterlegt. Ohne Felder gibt es nichts zu erfassen."),
        )

    values = values or {}
    missing = [f.get("label") or f.get("key")
               for f in fields
               if f.get("type") in EVALUABLE + MEDIA
               and values.get(f.get("key")) in (None, "")]
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Nicht erfasst: {', '.join(str(m) for m in missing)}.",
        )

    unknown = [k for k in values if k not in {f.get("key") for f in fields}]
    if unknown:
        raise HTTPException(
            status_code=400,
            detail=(f"Unbekannte Erfassungsfelder: {', '.join(sorted(unknown))}. "
                    f"Die Maske des Artikels kennt sie nicht."),
        )

    entry = Capture(
        instance_unit_id=unit.id,
        values=values,
        result=evaluate(fields, values),
        captured_by=actor_id,
        note=note,
    )
    db.add(entry)
    db.flush()
    return entry


def history(db: Session, unit: InstanceUnit) -> list[Capture]:
    """Alle Erfassungen dieser Einzelinstanz, neueste zuerst."""
    return (
        db.query(Capture)
        .filter(Capture.instance_unit_id == unit.id, Capture.is_active.is_(True))
        .order_by(Capture.created_at.desc(), Capture.id.desc())
        .all()
    )
