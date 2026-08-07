"""Was ein Erfassungspunkt-Typ können muss — das ganze Protokoll.

Vier Fragen, mehr nicht. Wer einen sechsten Typ baut, beantwortet sie in **einer neuen
Datei** und ändert an den bestehenden nichts:

===================== =======================================================
``clean``             Was braucht dieser Typ in der **Definition** über
                      Bezeichnung/Pflicht hinaus? (Nur ``measure`` braucht etwas.)
``missing``           Ist der Wert zur **Laufzeit** erfasst worden?
``verdict``           Sagt der Wert etwas über gut/schlecht — oder hält er nur fest?
===================== =======================================================

Die Alternative wäre eine ``if type == …``-Kette an drei Stellen (Definition prüfen,
Pflichtfeld prüfen, bewerten). Sie hätte den sechsten Typ zu einer Änderung an fünf
Stellen gemacht, von denen man die dritte vergisst.
"""

from typing import Any, Optional

from fastapi import HTTPException


class CaptureType:
    """Ein Erfassungspunkt-Typ. Unterklassen setzen die drei Attribute und überschreiben,
    was bei ihnen anders ist — die Vorgaben hier sind die des einfachen Falls (Freitext)."""

    #: Der gespeicherte Wert. Er steht in ``process_steps.config`` und in keinem Enum
    #: daneben: die Registry IST die Liste.
    key: str = ""
    #: Beschriftung in der Auswahl. Das Frontend spiegelt sie (``lib/capture-types.ts``)
    #: und wird dagegen getestet.
    label: str = ""
    #: Anzeige-Reihenfolge. Ohne sie entschiede die Dateisortierung, wie das Menü aussieht.
    order: int = 100

    # ── Definition ──────────────────────────────────────────────────────────
    def clean(self, point: dict[str, Any]) -> dict[str, Any]:
        """Die **zusätzlichen** Definitionsfelder dieses Typs, geprüft und normalisiert.

        Rückgabe ist das, was über ``key``/``label``/``type``/``required`` hinaus
        gespeichert wird. Fehlt etwas Notwendiges, ist das ein Fehler mit Grund – kein
        stiller Default, der später als Messwert durchgeht.
        """
        return {}

    # ── Laufzeit ────────────────────────────────────────────────────────────
    def missing(self, point: dict[str, Any], value: Any) -> bool:
        """Ist dieser Punkt **nicht** erfasst? Entscheidet, ob ein Pflichtpunkt blockiert."""
        return value is None or value == ""

    def verdict(self, point: dict[str, Any], value: Any) -> Optional[bool]:
        """Gut/schlecht — oder ``None``, wenn dieser Typ nichts zu urteilen hat.

        ``None`` ist kein «bestanden». Ein Foto ist ein Beleg, kein Urteil, und ein
        erfundenes «in Ordnung» wäre eine Aussage, die niemand getroffen hat.
        """
        return None


def bad(detail: str) -> HTTPException:
    """Ein Definitionsfehler. Immer mit Grund – ein Typ, der stumm scheitert, ist schlimmer
    als keiner."""
    return HTTPException(status_code=400, detail=detail)
