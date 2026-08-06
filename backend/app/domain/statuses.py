"""**Die geschlossene Statusliste — die eine Stelle.**

Ein Status ist ein Zustand einer **Einzelinstanz**. Module wählen aus dieser Liste aus;
sie erfinden nie eigene Werte. Ein Modul mit unbekanntem Status ist nicht anlegbar
(``assert_known``) — der Fehler kommt beim Anlegen, nicht erst bei der Ausführung.

**Warum geschlossen** (PROCESS_CORE.md §5.1): wäre der Wert Freitext, bedeutete
«Status X» in zwei Aufträgen womöglich Verschiedenes, und weder Farbe noch Bestand
liessen sich systemweit ableiten. Die Liste zu erweitern ist darum ein bewusster
Eingriff an genau dieser Stelle — nicht etwas, das beim Anlegen eines Moduls nebenbei
passiert.

**Heute gibt es genau zwei Werte.** Alles Weitere wäre erfunden:

- ``gebunden`` wäre der Reservierungsbegriff — Reservierung entfällt ersatzlos (§3).
- ``gesperrt`` wäre ein Problemzustand — die Fehlerbehandlung im Modul ist nicht
  entschieden (§11.5). **Der rote Ton hat darum heute keinen Wert**, und das ist
  ehrlicher als ein erfundener.
- ``verbraucht`` wäre ein zweiter Endzustand — heute gibt es genau einen (§4.2).
"""

from fastapi import HTTPException

# ---------------------------------------------------------------------------
# Die Werte
# ---------------------------------------------------------------------------

FREIGEGEBEN = "freigegeben"
IM_PROZESS = "im_prozess"

#: Wert → Beschriftung. Die Reihenfolge ist die Anzeige-Reihenfolge.
STATUS_LABELS: dict[str, str] = {
    FREIGEGEBEN: "Freigegeben",
    IM_PROZESS: "Im Prozess",
}

#: Wert → Ampelton. **Farbe hängt am Status, nie an der Position im Fluss** (§5.3).
#: Die Töne sind die drei des Design-Systems; das Frontend spiegelt diese Zuordnung
#: (``lib/process-status.ts``) und wird dagegen getestet.
STATUS_TONES: dict[str, str] = {
    FREIGEGEBEN: "done",     # grün — Anfang und Ende
    IM_PROZESS: "pending",   # orange — unterwegs
}

STATUSES: tuple[str, ...] = tuple(STATUS_LABELS)

# ---------------------------------------------------------------------------
# Die festen Rand-Übergänge (§4.1)
# ---------------------------------------------------------------------------

#: Start: das Stück tritt in den Prozess ein. **Nicht je Auftrag einstellbar.**
START_BEFORE = FREIGEGEBEN
START_AFTER = IM_PROZESS

#: Ende: Vorher ist fest. Das **Nachher** ist der konfigurierbare Wert des
#: Ende-Objekts (``orders.end_status``) — heute immer ``FREIGEGEBEN``, aber genau
#: einmal im System hinterlegt, damit die spätere Erweiterung eine Änderung ist und
#: kein Umbau (§4.2).
END_BEFORE = IM_PROZESS
DEFAULT_END_STATUS = FREIGEGEBEN

#: Womit eine frisch angelegte Einzelinstanz startet. Sie ist einsatzbereit und in
#: keinem Auftrag — genau das heisst ``freigegeben``.
INITIAL_UNIT_STATUS = FREIGEGEBEN


def label(status: str) -> str:
    """Beschriftung eines Status. Unbekannt → der rohe Wert, damit eine Anzeige nie
    lügt: ein Wert, den es nicht geben dürfte, wird sichtbar, nicht versteckt."""
    return STATUS_LABELS.get(status, status)


def assert_known(status: str, *, field: str) -> str:
    """Wächter für jede Schreibstelle. Wirft, statt einen unbekannten Wert zu speichern."""
    if status not in STATUS_LABELS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"«{status}» ist kein bekannter Status ({field}). "
                f"Erlaubt: {', '.join(STATUS_LABELS.values())}."
            ),
        )
    return status
