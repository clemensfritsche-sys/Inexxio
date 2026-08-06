"""Auftrag – Anlage und Lesen.

**Hier steht die zentrale Stelle für die Pflichteingaben** (``validate_draft``). Sie ist
heute leer, weil die Pflichtfelder noch nicht definiert sind; sie ist trotzdem schon
verdrahtet, damit sie später an EINEM Ort eingetragen werden und nicht an dreien.
"""

from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..models import Order
from .objects import next_object_id


# ---------------------------------------------------------------------------
# ►► PFLICHTEINGABEN DES AUFTRAGS – DIE EINE STELLE ◄◄
# ---------------------------------------------------------------------------
#
# Ein Auftragsentwurf lebt nur im Browser. Gespeichert wird er erst, wenn er hier
# durchkommt – und erst dann bekommt er seine Objektnummer.
#
# Die Regeln sind NOCH NICHT DEFINIERT. Sie kommen mit der Prozesslogik. Bis dahin
# lässt diese Funktion jeden Entwurf durch; sie ist bewusst schon da, damit die
# Bedingungen später an genau einer Stelle landen statt verteilt in Router, Schema
# und Oberfläche.
#
# EINTRAGEN NACH DIESEM MUSTER – ein Fehler nennt Feld und Grund, kein Sammel-«ungültig»:
#
#     if not draft.get("article_object_id"):
#         missing.append("Artikel")
#     if not draft.get("quantity"):
#         missing.append("Menge")
#
# Das Frontend fragt dieselbe Regel über ``POST /erp/orders/validate`` ab, damit der
# Speichern-Knopf denselben Massstab anlegt wie der Server – EINE Regel, zwei Leser.
# ---------------------------------------------------------------------------

def validate_draft(draft: dict[str, Any]) -> list[str]:
    """Fehlende Pflichteingaben eines Auftragsentwurfs – leere Liste heisst «speicherbar».

    Gibt die **Namen** der fehlenden Angaben zurück, nicht True/False: nur so kann die
    Oberfläche sagen, was fehlt, statt den Nutzer suchen zu lassen.
    """
    missing: list[str] = []

    # ── Pflichteingaben hier eintragen (siehe Kommentar oben). ──
    # Heute keine: die Regeln sind noch nicht definiert.

    return missing


def assert_saveable(draft: dict[str, Any]) -> None:
    """Wächter vor dem Speichern. Wirft, statt still einen halben Auftrag anzulegen."""
    missing = validate_draft(draft)
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Der Auftrag ist unvollständig – es fehlt: {', '.join(missing)}.",
        )


# ---------------------------------------------------------------------------
# Anlage
# ---------------------------------------------------------------------------

def create_order(db: Session, draft: dict[str, Any]) -> Order:
    """Aus einem Entwurf einen Auftrag machen.

    Die Objektnummer wird **hier** gezogen und nirgends sonst – vorher existiert der
    Auftrag nicht, auch nicht als reservierte Nummer.
    """
    assert_saveable(draft)
    order = Order(object_id=next_object_id(db, "order"))
    db.add(order)
    db.flush()
    return order


def get(db: Session, object_id: int) -> Order:
    order = db.query(Order).filter(Order.object_id == object_id).first()
    if order is None:
        raise HTTPException(status_code=404, detail=f"Auftrag {object_id} nicht gefunden.")
    return order
