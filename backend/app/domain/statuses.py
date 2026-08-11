"""**Die geschlossene Statusliste — die eine Stelle, für alles.**

Ein Status ist ein Zustand: einer **Einzelinstanz**, eines **Auftrags** oder eines
**Artikels**. Jeder steht hier **genau einmal**, mit allem, was über ihn zu wissen ist –
Beschriftung, Ampelton, welche Achsen ihn tragen, und (für Stücke) ob er zum aktuellen
**Bestand** oder zur **Historie** zählt. Die drei Achsen teilen sich die Werte, wo sie
dasselbe meinen. Das ist der Grundsatz: so wenige Status wie möglich, so viele
gemeinsame wie möglich.

**Alles Weitere ist abgeleitet.** Die Achsen-Listen, die Ampeltöne, die Anzeige-
Reihenfolge, die Trennung Bestand/Historie – keine davon ist eine zweite Liste, die
jemand nachziehen müsste. Ein neuer Status ist **eine Zeile in** ``CATALOG``; Bestands-
Leiste, Gruppierung, Farbe und Frontend-Spiegel folgen ohne weiteres Zutun.

Vorher war das nicht so: ``LIVE_UNIT_STATUSES`` war eine eigene Liste neben
``UNIT_STATUSES``. Ein neuer Stück-Zustand wäre stillschweigend als **lebender Bestand**
gezählt worden – ein terminaler Zustand hätte den Lagerbestand erhöht, und niemand hätte
es gemerkt. Genau darum ist die Zugehörigkeit jetzt eine **Eigenschaft des Status** und
ihr Fehlen ein Fehler beim Start, kein stiller Standardwert.

**Warum geschlossen** (PROCESS_CORE.md §5.1): wäre der Wert Freitext, bedeutete
«Status X» in zwei Aufträgen womöglich Verschiedenes, und weder Farbe noch Bestand
liessen sich systemweit ableiten.

**Nicht angelegt, weil erfunden:** ``gebunden`` (Reservierung entfällt ersatzlos) und
``verbraucht`` (wäre ein zweiter Endzustand — heute gibt es genau einen, §4.2).
"""

from dataclasses import dataclass

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

#: Aus dem Verkehr gezogen und **physisch weg** (**Einzelinstanz**). Endgültig: es gibt
#: das Ding nicht mehr, also kann es in keinem Auftrag mehr vorkommen.
VERSCHROTTET = "verschrottet"

#: Aus dem Verkehr gezogen, aber **physisch noch da** (**Einzelinstanz**). Nicht mehr
#: einplanbar, solange die Sperre gilt – aufhebbar, indem ein Auftrag das Stück greift.
GESPERRT = "gesperrt"

# ---------------------------------------------------------------------------
# Die Eigenschaften, die ein Status trägt
# ---------------------------------------------------------------------------

#: Achsen. Wer kann diesen Status tragen?
UNIT, ORDER, ARTICLE = "unit", "order", "article"

#: Bestands-Zugehörigkeit eines **Stück**-Zustands. Nur diese beiden Werte gibt es:
#: ``live`` = zählt zum aktuellen Bestand · ``history`` = existiert noch als Datensatz,
#: aber nicht mehr als Material (verbraucht, ausgesondert, verkauft).
LIVE, HISTORY = "live", "history"


@dataclass(frozen=True)
class Status:
    """Ein Zustand mit allem, was über ihn zu wissen ist."""

    value: str
    label: str
    #: Ampelton – die drei des Design-Systems. **Farbe hängt am Status, nie an der
    #: Position im Fluss** (§5.3); die konkreten Farbwerte stehen in den Design-Tokens.
    tone: str
    #: Welche Achsen ihn tragen können.
    axes: tuple[str, ...]
    #: **Bestand oder Historie?** Pflicht für jeden Zustand, den ein Stück tragen kann;
    #: für alle anderen sinnlos und darum verboten (siehe ``_check``).
    stock: str | None = None
    #: **Darf ein Auftrag ein Stück in diesem Zustand aufnehmen?**
    #:
    #: Das ist die Frage «gibt es einen Weg zurück?» – und sie gehört an den Status, nicht
    #: an eine Liste in der Freigabe. Die **Farbe folgt daraus**, nicht umgekehrt: was
    #: endgültig ist, ist rot; was aufhebbar ist, ist gelb.
    #:
    #: ``Verschrottet`` ist der einzige Zustand, der es verneint: das Ding gibt es
    #: physisch nicht mehr, ein Auftrag darauf wäre ein Auftrag auf nichts. ``Gesperrt``
    #: bejaht es – **das Greifen ist das Aufheben**, es braucht keinen zweiten Mechanismus.
    selectable: bool = True


#: **Die eine Liste.** Reihenfolge = Anzeige-Reihenfolge (Leiste, Legende, Filter).
CATALOG: tuple[Status, ...] = (
    Status(FREIGEGEBEN, "Freigegeben", "done", (UNIT, ARTICLE), stock=LIVE),
    Status(IM_PROZESS, "Im Prozess", "pending", (UNIT, ORDER), stock=LIVE),
    # **Gesperrt zählt zum Bestand.** Das Stück liegt im Regal – es ist da, nur nicht
    # verwendbar. Es in die Historie zu legen hiesse, den Bestand kleiner zu melden, als
    # er ist; die Leiste zeigt es als eigenes Segment, und genau das ist die Auskunft.
    Status(GESPERRT, "Gesperrt", "pending", (UNIT,), stock=LIVE),
    Status(VERSCHROTTET, "Verschrottet", "danger", (UNIT,), stock=HISTORY, selectable=False),
    Status(ABGESCHLOSSEN, "Abgeschlossen", "done", (ORDER,)),
    Status(ABGEBROCHEN, "Abgebrochen", "danger", (ORDER,)),
    Status(INAKTIV, "Inaktiv", "danger", (ARTICLE,)),
)

_TONES = ("done", "pending", "danger")


def _check(catalog: tuple[Status, ...] = CATALOG) -> None:
    """**Der Wächter beim Start** – ein unvollständiger Eintrag kommt gar nicht erst durch.

    Ein Stück-Zustand ohne Bestands-Zugehörigkeit wäre die gefährlichste Form eines
    Fehlers: er landete stillschweigend irgendwo, und die Bestandsleiste zeigte eine
    Zahl, die niemand nachrechnet. Darum startet die Anwendung lieber nicht.

    Der Katalog ist ein **Parameter**, damit ein Test die Regel gegen ihre Fehlerform
    prüfen kann: ein Wächter, der nie anschlägt, ist von einem kaputten nicht zu
    unterscheiden.
    """
    seen: set[str] = set()
    for s in catalog:
        if s.value in seen:
            raise ValueError(f"Status «{s.value}» steht zweimal im Katalog.")
        seen.add(s.value)
        if s.tone not in _TONES:
            raise ValueError(
                f"Status «{s.value}» hat den Ton «{s.tone}» – erlaubt: {', '.join(_TONES)}."
            )
        if not s.axes or any(a not in (UNIT, ORDER, ARTICLE) for a in s.axes):
            raise ValueError(f"Status «{s.value}» nennt keine gültige Achse ({s.axes}).")
        if UNIT in s.axes and s.stock not in (LIVE, HISTORY):
            raise ValueError(
                f"Status «{s.value}» kann an einer Einzelinstanz stehen, sagt aber nicht, "
                f"ob er zum Bestand oder zur Historie zählt. Setze stock=LIVE oder "
                f"stock=HISTORY – ohne die Angabe wäre die Bestandsleiste eine Behauptung."
            )
        if UNIT not in s.axes and s.stock is not None:
            raise ValueError(
                f"Status «{s.value}» trägt kein Stück, behauptet aber eine Bestands-"
                f"Zugehörigkeit ({s.stock}). Das ist eine Aussage über etwas, das es nicht gibt."
            )
        if UNIT not in s.axes and not s.selectable:
            raise ValueError(
                f"Status «{s.value}» trägt kein Stück, sagt aber, dass ein Auftrag ihn "
                f"nicht aufnehmen darf. Auch das ist eine Aussage über etwas, das es "
                f"nicht gibt."
            )


_check()

# ---------------------------------------------------------------------------
# Alles Weitere ist ABGELEITET – keine zweite Liste, die jemand nachziehen müsste
# ---------------------------------------------------------------------------

_BY_VALUE: dict[str, Status] = {s.value: s for s in CATALOG}

#: Wert → Beschriftung. Die Reihenfolge ist die Anzeige-Reihenfolge.
STATUS_LABELS: dict[str, str] = {s.value: s.label for s in CATALOG}

STATUSES: tuple[str, ...] = tuple(STATUS_LABELS)


def _on(axis: str) -> tuple[str, ...]:
    return tuple(s.value for s in CATALOG if axis in s.axes)


#: Einzelinstanz: einsatzbereit oder unterwegs. Mehr Zustände hat ein Stück heute nicht.
UNIT_STATUSES: tuple[str, ...] = _on(UNIT)

#: Auftrag: **genau drei**, und alle drei sind **abgeleitet** (``process.order_status``).
#: «Freigegeben» ist bewusst nicht dabei — Freigeben ist eine Aktion, kein Zustand.
ORDER_STATUSES: tuple[str, ...] = _on(ORDER)

#: Artikel: freigegeben (er entsteht erst damit) oder ausser Betrieb.
ARTICLE_STATUSES: tuple[str, ...] = _on(ARTICLE)

#: **Welche Stücke darf ein Auftrag greifen?** Abgeleitet aus der Eigenschaft am Status –
#: keine zweite Liste, die jemand nachzieht, wenn ein Zustand dazukommt.
SELECTABLE_UNIT_STATUSES: tuple[str, ...] = tuple(
    s.value for s in CATALOG if UNIT in s.axes and s.selectable
)

# **Keine Liste «was zählt zum Bestand»** – die Frage beantwortet ``stock_kind`` je
# Zustand. Sie stand hier einmal als abgeleitete Liste und war der Rückfall in genau das
# Muster, das dieses Modul abschaffen soll: eine zweite Aufzählung, die jemand liest,
# statt die Eigenschaft zu fragen.

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

#: Was ein Zustand ist, den der Katalog nicht kennt. Er wird **gemeldet**, nicht
#: einsortiert: eine Bestandsleiste, die ihn stillschweigend mitzählt, verbirgt genau
#: den Fehler, den man sehen müsste.
UNKNOWN = "unknown"


def label(status: str) -> str:
    """Beschriftung eines Status. Unbekannt → der rohe Wert, damit eine Anzeige nie
    lügt: ein Wert, den es nicht geben dürfte, wird sichtbar, nicht versteckt."""
    return STATUS_LABELS.get(status, status)


def is_selectable(status: str) -> bool:
    """**Darf ein Auftrag ein Stück in diesem Zustand greifen?**

    Die eine Antwort für die Freigabe (``process.release``) **und** für die Auswahl-Liste
    (``routers/orders``). Getrennt gestellt wären es zwei Regeln, und die Oberfläche böte
    irgendwann etwas an, das der Server ablehnt – oder schlimmer, umgekehrt.

    Ein unbekannter Wert ist **nicht** wählbar: was der Katalog nicht kennt, kann er auch
    nicht erlauben.
    """
    s = _BY_VALUE.get(status)
    return bool(s and s.selectable)


def stock_kind(status: str) -> str:
    """**Bestand, Historie – oder unbekannt?** Die eine Antwort für die Bestandsansicht.

    Sie kommt aus der Eigenschaft am Status, nicht aus einer Liste in der Oberfläche.
    Ein Wert, den der Katalog nicht kennt (Altdaten, Fremdeintrag), landet in
    ``UNKNOWN`` – sichtbar als eigene Gruppe, statt eine der beiden echten zu
    verfälschen.
    """
    s = _BY_VALUE.get(status)
    return s.stock if s and s.stock else UNKNOWN


def in_order(counts: dict[str, int]) -> list[tuple[str, int]]:
    """Gezählte Zustände in **Anzeige-Reihenfolge**, Nullen weggelassen.

    Die Reihenfolge steht im ``CATALOG`` und sonst nirgends – jede Ansicht, die Zustände
    nebeneinander zeigt (Bestandsleiste, Legende), liest sie hier. Sonst stünde dieselbe
    Aufstellung an zwei Stellen in zwei Reihenfolgen.

    Ein **unbekannter** Wert wird hinten angehängt statt verschwiegen: er dürfte nicht
    existieren, und eine Leiste, deren Segmente sich nicht zur Menge summieren, verbirgt
    genau den Fehler, den man sehen müsste.
    """
    known = [(s, counts[s]) for s in STATUS_LABELS if counts.get(s)]
    rest = [(s, n) for s, n in counts.items() if s not in STATUS_LABELS and n]
    return known + sorted(rest)


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
