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
from ..models.order_line import LAGER
from .process import (
    assert_releasable, release, resolve_lines, steps_for, unpickable,
)


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

def validate_draft(db: Session | None, draft: dict[str, Any]) -> list[str]:
    """Was fehlt diesem Entwurf noch zur Freigabe? Leere Liste heisst «freigebbar».

    Sie beantwortet die Frage mit **derselben** Prüfung, die die Freigabe abbricht: die
    Zeilen laufen durch ``resolve_lines`` und ``steps_for``, und was dabei als Fehler
    herauskäme, ist hier die fehlende Angabe. Eine zweite, mildere Prüfung daneben wäre
    ein zweiter Massstab – und der wäre irgendwann grosszügiger als die Freigabe selbst,
    also stünde ein Knopf bereit, der beim Klick scheitert.

    Angelegt wird dabei nichts und keine Objektnummer gezogen: alle diese Schritte
    liegen im Freigabe-Ablauf ausdrücklich **vor** der ersten Nummer (§6.3).
    """
    try:
        lines = resolve_lines(db, list(draft.get("lines") or []))
        steps = steps_for(db, lines, list(draft.get("steps") or []))
    except HTTPException as e:
        # Der Grund, warum die Freigabe scheitern würde, IST die fehlende Angabe.
        return [str(e.detail)]

    total = sum(ln.quantity for ln in lines)
    missing = assert_releasable(total, steps)

    # **Ein Stück in einem Endzustand ist keine gültige Auswahl** – und das muss der
    # Entwurf sagen, nicht erst der Klick. Dieselbe Regel wie in der Freigabe, aus
    # derselben Funktion (``process.pick_problem``); eine zweite, mildere Prüfung hier
    # wäre ein Knopf, der bereitsteht und dann scheitert.
    missing.extend(unpickable(db, lines))

    # Eine ``Lager``-Zeile muss so viele Stücke benennen, wie sie verlangt – sonst
    # stimmt die Mengen-Invariante nicht, und das merkt man besser jetzt als beim Klick.
    for ln in lines:
        if ln.origin == LAGER and len(ln.picks) != ln.quantity:
            missing.append(
                f"{ln.label}: {ln.quantity} Einzelinstanzen, gewählt sind "
                f"{len(ln.picks)}"
            )
    return missing


def create_order(db: Session, draft: dict[str, Any], *, actor_id: int | None) -> Order:
    """Aus einem Entwurf einen freigegebenen Auftrag machen.

    Alles in **einer** Transaktion (der Aufrufer committet): Bedingungen, Anlage,
    Exklusivität, Erzeugung, Start-Übergang, Log. Bricht ein Schritt ab, bleibt nichts
    Halbfertiges zurück – kein Auftrag ohne Prozess, keine Einzelinstanz im
    Zwischenzustand, keine herrenlose Instanz.
    """
    return release(
        db,
        lines=[dict(ln) for ln in (draft.get("lines") or [])],
        steps=[dict(s) for s in (draft.get("steps") or [])],
        actor_id=actor_id,
    )


def get(db: Session, object_id: int) -> Order:
    order = db.query(Order).filter(Order.object_id == object_id).first()
    if order is None:
        raise HTTPException(status_code=404, detail=f"Auftrag {object_id} nicht gefunden.")
    return order
