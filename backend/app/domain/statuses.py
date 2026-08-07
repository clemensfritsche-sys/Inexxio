"""**Die geschlossene Statusliste — die eine Stelle, für alles.**

Ein Status ist ein Zustand: einer **Einzelinstanz**, eines **Auftrags** oder eines
**Artikels**. Die Werte stehen hier, einmal, mit Beschriftung und Ampelton — und die drei
Achsen **teilen sie sich, wo sie dasselbe meinen**. Das ist der Grundsatz: so wenige
Status wie möglich, so viele gemeinsame wie möglich.

Konkret geteilt wird ``im_prozess``: ein Stück, das gerade durch einen Auftrag läuft, und
ein Auftrag, der gerade läuft, sind dasselbe Wort, dieselbe Farbe, derselbe Eintrag.
Vorher stand «Im Prozess» in drei Dateien mit drei Beschriftungen — und beim Auftrag
sogar als «Freigegeben», was gar kein Zustand ist, sondern eine Aktion.

**Warum geschlossen** (PROCESS_CORE.md §5.1): wäre der Wert Freitext, bedeutete
«Status X» in zwei Aufträgen womöglich Verschiedenes, und weder Farbe noch Bestand
liessen sich systemweit ableiten. Die Liste zu erweitern ist darum ein bewusster
Eingriff an genau dieser Stelle.

**Nicht angelegt, weil erfunden:** ``gebunden`` (Reservierung entfällt ersatzlos) und
``verbraucht`` (wäre ein zweiter Endzustand — heute gibt es genau einen, §4.2).
"""

from fastapi import HTTPException

# ---------------------------------------------------------------------------
# Die Werte — fünf Wörter für drei Achsen
# ---------------------------------------------------------------------------

#: Einsatzbereit. An der **Einzelinstanz**: sie steckt in keinem Auftrag. Am **Artikel**:
#: er ist freigegeben und auftragsfähig. Dasselbe Wort, weil es dasselbe meint.
FREIGEGEBEN = "freigegeben"

#: Läuft gerade. An der **Einzelinstanz** wie am **Auftrag** — der Auftrag ist im Prozess,
#: solange seine Stücke es sind.
IM_PROZESS = "im_prozess"

#: Ziel erreicht (**Auftrag**).
ABGESCHLOSSEN = "abgeschlossen"

#: Das Ziel ist nicht mehr erreichbar (**Auftrag**). Der erste Wert mit dem **roten** Ton –
#: bis hierher hatte er keinen, und ein erfundener wäre schlimmer gewesen als keiner.
ABGEBROCHEN = "abgebrochen"

#: Ausser Betrieb (**Artikel**). Endgültig – kein Reaktivieren.
INAKTIV = "inaktiv"

#: Wert → Beschriftung. Die Reihenfolge ist die Anzeige-Reihenfolge.
STATUS_LABELS: dict[str, str] = {
    FREIGEGEBEN: "Freigegeben",
    IM_PROZESS: "Im Prozess",
    ABGESCHLOSSEN: "Abgeschlossen",
    ABGEBROCHEN: "Abgebrochen",
    INAKTIV: "Inaktiv",
}

#: Wert → Ampelton. **Farbe hängt am Status, nie an der Position im Fluss** (§5.3).
#: Die Töne sind die drei des Design-Systems; das Frontend spiegelt diese Zuordnung
#: (``lib/process-status.ts``) und wird dagegen getestet.
STATUS_TONES: dict[str, str] = {
    FREIGEGEBEN: "done",         # grün — einsatzbereit
    IM_PROZESS: "pending",       # orange — unterwegs
    ABGESCHLOSSEN: "done",       # grün — angekommen
    ABGEBROCHEN: "danger",       # rot — kommt nicht mehr an
    INAKTIV: "danger",           # rot — nicht mehr verwendbar
}

STATUSES: tuple[str, ...] = tuple(STATUS_LABELS)

# ---------------------------------------------------------------------------
# Wer welche Werte tragen kann
# ---------------------------------------------------------------------------
#
# Drei Teilmengen einer Liste — nicht drei Listen. Ein Wert, der in zwei Achsen
# vorkommt, steht genau einmal da und hat überall dieselbe Farbe und dasselbe Wort.

#: Einzelinstanz: einsatzbereit oder unterwegs. Mehr Zustände hat ein Stück heute nicht.
UNIT_STATUSES: tuple[str, ...] = (FREIGEGEBEN, IM_PROZESS)

#: Auftrag: **genau drei**, und alle drei sind **abgeleitet** (``process.order_status``).
#: «Freigegeben» ist bewusst nicht dabei — Freigeben ist eine Aktion, kein Zustand.
ORDER_STATUSES: tuple[str, ...] = (IM_PROZESS, ABGESCHLOSSEN, ABGEBROCHEN)

#: Artikel: freigegeben (er entsteht erst damit) oder ausser Betrieb.
ARTICLE_STATUSES: tuple[str, ...] = (FREIGEGEBEN, INAKTIV)

# ---------------------------------------------------------------------------
# Die festen Rand-Übergänge (§4.1)
# ---------------------------------------------------------------------------

#: Start: das Stück tritt in den Prozess ein. **Nicht je Auftrag einstellbar.**
#: Dieser Übergang IST die Aktion «Auftrag freigeben».
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
