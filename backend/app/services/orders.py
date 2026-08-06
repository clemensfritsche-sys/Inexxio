"""Auftrag – Anlage (= Freigabe) und Lesen.

**Ein Auftrag entsteht erst bei der Freigabe.** Bis dahin lebt der Entwurf im Browser:
keine Zeile, keine reservierte Objektnummer, kein Autosave. Es gibt darum keinen
gespeicherten Zustand «Entwurf» und keinen «Speichern»-Pfad neben der Freigabe.

Die Fachlogik steht in ``services/process.py``; hier stehen die Freigabebedingungen –
**die eine Stelle**, die Router und Oberfläche gemeinsam lesen.
"""

from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..models import Order
from .process import assert_releasable, release


# ---------------------------------------------------------------------------
# ►► FREIGABEBEDINGUNGEN DES AUFTRAGS – DIE EINE STELLE ◄◄
# ---------------------------------------------------------------------------
#
# Sie gibt die **Namen** der fehlenden Angaben zurück, nicht True/False: nur so kann
# die Oberfläche sagen, *was* fehlt, statt den Nutzer suchen zu lassen. Das Frontend
# fragt sie über ``POST /erp/orders/validate`` ab, statt sie nachzuformulieren – sonst
# gäbe es zwei Massstäbe für dieselbe Frage.
#
# Weitere Bedingungen kommen hierher, nicht in den Router und nicht ins Formular.
# ---------------------------------------------------------------------------

def validate_draft(draft: dict[str, Any]) -> list[str]:
    """Was fehlt diesem Entwurf noch zur Freigabe? Leere Liste heisst «freigebbar»."""
    return assert_releasable(
        list(draft.get("unit_numbers") or []),
        list(draft.get("steps") or []),
    )


def create_order(db: Session, draft: dict[str, Any], *, actor_id: int | None) -> Order:
    """Aus einem Entwurf einen freigegebenen Auftrag machen.

    Alles in **einer** Transaktion (der Aufrufer committet): Bedingungen, Anlage,
    Exklusivität, Start-Übergang, Log. Bricht ein Schritt ab, bleibt nichts
    Halbfertiges zurück – kein Auftrag ohne Prozess, keine Einzelinstanz im
    Zwischenzustand.
    """
    return release(
        db,
        unit_numbers=[str(n) for n in (draft.get("unit_numbers") or [])],
        steps=[dict(s) for s in (draft.get("steps") or [])],
        actor_id=actor_id,
    )


def get(db: Session, object_id: int) -> Order:
    order = db.query(Order).filter(Order.object_id == object_id).first()
    if order is None:
        raise HTTPException(status_code=404, detail=f"Auftrag {object_id} nicht gefunden.")
    return order
