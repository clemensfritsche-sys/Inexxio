"""Schemas des **Systemprotokolls** (Diagnose eines Auftrags, `services/diagnostics.py`)."""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel


class DiagnosticEntry(BaseModel):
    """**Eine Zeile des Systemprotokolls** – aus einem der drei bestehenden Ströme.

    ``source`` sagt, WELCHER Mechanismus gesprochen hat, und das ist bei der Fehlersuche
    die halbe Antwort: ``audit`` = jemand hat ein Feld geändert (Absicht) · ``event`` = ein
    fachliches Ereignis wurde ausgelöst (Wirkung) · ``journal`` = Material hat den Topf
    gewechselt (Bestand). ``detail`` trägt die Rohwerte, damit ein Bericht nichts
    nachschlagen muss."""

    at: Optional[datetime] = None
    source: str                      # audit | event | journal
    kind: str                        # Feld, Ereignistyp oder Buchungsart
    summary: str
    actor: Optional[str] = None
    object_id: Optional[int] = None
    detail: Optional[dict[str, Any]] = None


class OrderDiagnostics(BaseModel):
    """**Befund + Protokoll** eines Auftrags – die Grundlage eines Fehlerberichts.

    ``snapshot`` ist der abgeleitete Zustand zum Abfragezeitpunkt (Schritte, Fehlmenge,
    Unter-Aufträge, Instanzen samt Kontostand und **Drift-Prüfung**), ``entries`` die
    Chronologie. Ein Bug zeigt sich fast immer als Widerspruch zwischen beidem.

    Bewusst frei typisiert (`dict`): eine Diagnose ist eine **Sicht** für Menschen und
    ändert sich mit den Fragen, die man gerade stellt – ein starrer Vertrag würde hier
    Aussagekraft gegen Formtreue tauschen."""

    order_object_id: int
    generated_at: datetime
    snapshot: dict[str, Any]
    # Wem gehört welche Menge – je Instanz-Objektnummer die Anteils-Aufteilung.
    share_map: dict[str, list[dict[str, Any]]] = {}
    entries: list[DiagnosticEntry] = []
    truncated: bool = False
