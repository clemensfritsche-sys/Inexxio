"""Auftrag – Anlage (= Freigabe) und Lesen.

**Ein Auftrag entsteht erst bei der Freigabe.** Bis dahin lebt der Entwurf im Browser:
keine Zeile, keine reservierte Objektnummer, kein Autosave. Es gibt darum keinen
gespeicherten Zustand «Entwurf» und keinen «Speichern»-Pfad neben der Freigabe.

Die Fachlogik steht in ``services/release.py``; hier stehen die Freigabebedingungen –
**die eine Stelle**, die Router und Oberfläche gemeinsam lesen.
"""

from typing import Any

from sqlalchemy.orm import Session

from ..models import Order
from ..models.order_line import LAGER
from .release import (
    _checked, assert_releasable, release, resolve_lines, steps_for, unpickable,
)
from ..domain.errors import Invalid, NotFound, Rejected


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

    Sie beantwortet die Frage mit **derselben** Prüfung, die die Freigabe abbricht
    (``release._checked``): was dort als Fehler herauskäme, ist hier die fehlende Angabe,
    im selben Satz. Vorher sammelt sie, was sich **alles** nennen lässt – die fehlenden
    Grundbedingungen, jedes Stück, das kein Auftrag greifen darf, jede Zeile mit der
    falschen Zahl Stücke –, damit der Entwurf nicht Fehler für Fehler aufdeckt.

    Angelegt wird dabei nichts, gesperrt nichts und keine Objektnummer gezogen: die
    Prüfung liegt im Freigabe-Ablauf ausdrücklich **vor** der ersten Nummer (§6.3).
    """
    raw_lines = list(draft.get("lines") or [])
    raw_steps = list(draft.get("steps") or [])
    try:
        lines = resolve_lines(db, raw_lines)
        steps = steps_for(db, lines, raw_steps)
    except Rejected as e:
        return [_said(e)]

    missing = assert_releasable(sum(ln.quantity for ln in lines), steps)
    missing.extend(unpickable(db, lines))
    for ln in lines:
        if ln.origin == LAGER and len(ln.picks) != ln.quantity:
            missing.append(
                f"{ln.label}: {ln.quantity} Einzelinstanzen, gewählt sind "
                f"{len(ln.picks)}"
            )
    # **Die Schlaufe** (Wiederkehr): ihre Einstellung und «nur an einem regulären Auftrag».
    if db is not None:
        from . import loop
        missing.extend(loop.draft_problems(db, draft))
    if missing:
        return missing
    try:
        _checked(db, raw_lines, raw_steps)
    except Rejected as e:
        return [_said(e)]
    return []


def _said(e: Rejected) -> str:
    """Der Satz eines Fehlers."""
    return e.detail


def create_order(db: Session, draft: dict[str, Any], *, actor_id: int | None,
                 actor: Any = None) -> Order:
    """Aus einem Entwurf einen freigegebenen Auftrag machen.

    Alles in **einer** Transaktion (der Aufrufer committet): Bedingungen, Anlage,
    Exklusivität, Erzeugung, Start-Übergang, Log. Bricht ein Schritt ab, bleibt nichts
    Halbfertiges zurück – kein Auftrag ohne Prozess, keine Einzelinstanz im
    Zwischenzustand, keine herrenlose Instanz.
    """
    from . import loop
    if draft.get("loop"):
        # Vor der ersten Nummer: eine unmögliche Schlaufe verbrennt keine Objektnummer (§6.3).
        problems = loop.draft_problems(db, draft)
        if problems:
            raise Invalid(problems[0])
    order = release(
        db,
        lines=[dict(ln) for ln in (draft.get("lines") or [])],
        steps=[dict(s) for s in (draft.get("steps") or [])],
        actor_id=actor_id,
    )
    # **Die Schlaufe friert mit der Freigabe ein** – dieselbe Transaktion (Wiederkehr O15).
    loop.freeze(db, order, draft, actor)
    return order


def get(db: Session, object_id: int) -> Order:
    order = db.query(Order).filter(Order.object_id == object_id).first()
    if order is None:
        raise NotFound(f"Auftrag {object_id} nicht gefunden.")
    return order
