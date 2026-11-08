"""**Die geschlossene Statusliste — die eine Stelle, für alles.**

Ein Status (Einzelinstanz, Auftrag, Artikel, Dokument) steht hier **genau einmal**, mit
Beschriftung, Ampelton, Achsen und (für Stücke) **Bestand** oder **Historie**. So wenige
Status wie möglich, so viele gemeinsame wie möglich.

**Alles Weitere ist abgeleitet** (Achsen-Listen, Ampeltöne, Reihenfolge, Bestand/Historie).
Ein neuer Status ist **eine Zeile in** ``CATALOG``. Die Bestands-Zugehörigkeit ist eine
**Eigenschaft des Status**; fehlt sie, startet die App nicht.

**Geschlossen** (PROCESS_CORE.md §5.1), damit Farbe und Bestand systemweit ableitbar sind.
Es gibt genau einen Endzustand (§4.2).
"""

from dataclasses import dataclass

from fastapi import HTTPException

# ---------------------------------------------------------------------------
# Die Werte — so wenige wie möglich, geteilt über drei Achsen
# ---------------------------------------------------------------------------

#: Einsatzbereit: die **Einzelinstanz** steckt in keinem Auftrag, der **Artikel** ist
#: auftragsfähig.
FREIGEGEBEN = "freigegeben"

#: Läuft gerade (**Einzelinstanz** und **Auftrag**).
IM_PROZESS = "im_prozess"

#: **Der Auftrag ist seinen definierten Weg zu Ende gegangen** (**Auftrag**) – auch über
#: einen **Ausgang** (§4.6): Zugehörigkeit geschlossen **und** vor keinem Modul mehr
#: (``order_state.order_statuses``).
ABGESCHLOSSEN = "abgeschlossen"

#: Das Ziel ist nicht mehr erreichbar (**Auftrag**) – roter Ton.
ABGEBROCHEN = "abgebrochen"

#: Ausser Betrieb (**Artikel**): von einem Nachfolger abgelöst (``Article.status``).
INAKTIV = "inaktiv"

#: **Dokument**: freigegeben, aber es fehlt noch mindestens eine verlangte Unterschrift.
#: Erst mit der letzten Unterschrift ist es «Freigegeben» (``services/documents.status_of``).
UNTERSCHRIFT_ANGEFRAGT = "unterschrift_angefragt"

#: **Dokument**: eine verlangte Unterschrift wurde abgelehnt – endgültig.
ABGELEHNT = "abgelehnt"

#: **Dokument**: gelöscht. Der Datensatz bleibt (Art, Name, wer, wann, Grund), die Datei
#: ist weg. Gelöscht wird nur, was nirgends hängt.
GELOESCHT = "geloescht"

#: Aus dem Verkehr gezogen und **physisch weg** (**Einzelinstanz**). Endgültig.
VERSCHROTTET = "verschrottet"

#: Aus dem Verkehr gezogen, aber **physisch noch da** (**Einzelinstanz**). Nicht mehr
#: einplanbar, solange die Sperre gilt – aufhebbar, indem ein Auftrag das Stück greift.
GESPERRT = "gesperrt"

#: **Gehört einer anderen Partei** (**Einzelinstanz**), geschrieben am Ziel
#: (``process._finish``); grün wie ``VERBAUT``.
#:
#: **Nicht endgültig**: Service oder Retoure sind ein **regulärer Start**
#: (``REGULAR_STARTS``). Ob es danach uns gehört, sagt allein die Zahlung
#: (``voucher.sold_units``).
#:
#: **Historie**: FIFO schlägt es nicht vor, der Bestand zählt es nicht – wählbar bleibt es
#: trotzdem (``stock`` ↔ ``terminal`` sind unabhängig).
VERKAUFT = "verkauft"

#: **Steckt in einem anderen Stück** (**Einzelinstanz**) – Zweck erreicht, darum grün.
#:
#: **Nicht endgültig**: Demontage ist real. **Das Greifen IST der Ausbau** und automatisch
#: eine Abweichung (``order_state.deviation_flags``).
#:
#: **Die Stückliste liest den LOG, nicht diesen Wert** (``services/genealogy``): was verbaut
#: *war*, bleibt verbaut gewesen.
VERBAUT = "verbaut"

# ---------------------------------------------------------------------------
# Die Eigenschaften, die ein Status trägt
# ---------------------------------------------------------------------------

#: Achsen. Wer kann diesen Status tragen?
UNIT, ORDER, ARTICLE, DOCUMENT = "unit", "order", "article", "document"

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
    #: Position im Fluss** (§5.4); die konkreten Farbwerte stehen in den Design-Tokens.
    tone: str
    #: Welche Achsen ihn tragen können.
    axes: tuple[str, ...]
    #: **Bestand oder Historie?** Pflicht für Stück-Zustände, sonst verboten (``_check``).
    stock: str | None = None
    #: **Ist dieser Zustand endgültig?** Kein Übergang mehr, durch nichts. Daraus folgen
    #: ``is_selectable`` und der Trigger ``terminal_guard_sql``; die Farbe folgt NICHT daraus
    #: (verbaut ist aufhebbar **und** grün). Nur ein **Stück**-Zustand darf terminal sein.
    terminal: bool = False


#: **Die eine Liste.** Reihenfolge = Anzeige-Reihenfolge (Leiste, Legende, Filter).
CATALOG: tuple[Status, ...] = (
    Status(FREIGEGEBEN, "Freigegeben", "done", (UNIT, ARTICLE, DOCUMENT), stock=LIVE),
    Status(IM_PROZESS, "Im Prozess", "pending", (UNIT, ORDER), stock=LIVE),
    # **Gesperrt zählt zum Bestand**: es liegt im Regal, nur nicht verwendbar.
    Status(GESPERRT, "Gesperrt", "pending", (UNIT,), stock=LIVE),
    # **Verbaut zählt zur Historie** (steckt in einem anderen Stück) und ist nicht terminal.
    Status(VERBAUT, "Verbaut", "done", (UNIT,), stock=HISTORY),
    # **Verkauft wie Verbaut**: grün, Historie, mit Weg zurück (Retoure).
    Status(VERKAUFT, "Verkauft", "done", (UNIT,), stock=HISTORY),
    Status(VERSCHROTTET, "Verschrottet", "danger", (UNIT,), stock=HISTORY, terminal=True),
    Status(ABGESCHLOSSEN, "Abgeschlossen", "done", (ORDER,)),
    Status(ABGEBROCHEN, "Abgebrochen", "danger", (ORDER,)),
    Status(INAKTIV, "Inaktiv", "danger", (ARTICLE,)),
    Status(UNTERSCHRIFT_ANGEFRAGT, "Unterschrift angefragt", "pending", (DOCUMENT,)),
    Status(ABGELEHNT, "Abgelehnt", "danger", (DOCUMENT,)),
    Status(GELOESCHT, "Gelöscht", "danger", (DOCUMENT,)),
)

_TONES = ("done", "pending", "danger")


def _check(catalog: tuple[Status, ...] = CATALOG) -> None:
    """**Der Wächter beim Start** – ein unvollständiger Eintrag kommt gar nicht erst durch.

    Der Katalog ist ein Parameter, damit ein Test die Regel gegen ihre Fehlerform prüft.
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
        if not s.axes or any(a not in (UNIT, ORDER, ARTICLE, DOCUMENT) for a in s.axes):
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
        if UNIT not in s.axes and s.terminal:
            raise ValueError(
                f"Status «{s.value}» trägt kein Stück, nennt sich aber endgültig. Nur ein "
                f"Stück-Zustand wird gespeichert und geändert – bei allen anderen wäre "
                f"das eine Zusage, die niemand einlösen kann."
            )


_check()

# ---------------------------------------------------------------------------
# Alles Weitere ist ABGELEITET – keine zweite Liste, die jemand nachziehen müsste
# ---------------------------------------------------------------------------

_BY_VALUE: dict[str, Status] = {s.value: s for s in CATALOG}

#: Wert → Beschriftung. Die Reihenfolge ist die Anzeige-Reihenfolge.
STATUS_LABELS: dict[str, str] = {s.value: s.label for s in CATALOG}



def _on(axis: str) -> tuple[str, ...]:
    return tuple(s.value for s in CATALOG if axis in s.axes)


#: Einzelinstanz: einsatzbereit oder unterwegs. Mehr Zustände hat ein Stück heute nicht.
UNIT_STATUSES: tuple[str, ...] = _on(UNIT)

#: Auftrag: **genau drei**, und alle drei sind **abgeleitet** (``order_state.order_status``).
#: «Freigegeben» ist bewusst nicht dabei — Freigeben ist eine Aktion, kein Zustand.
ORDER_STATUSES: tuple[str, ...] = _on(ORDER)

#: Artikel: freigegeben (er entsteht erst damit) oder ausser Betrieb.
ARTICLE_STATUSES: tuple[str, ...] = _on(ARTICLE)

#: **Die Endzustände eines Stücks.** Die eine Liste, aus der der Schutz entsteht – in der
#: Anwendung (``process._pass``) wie in der Datenbank (``terminal_guard_sql``).
TERMINAL_UNIT_STATUSES: tuple[str, ...] = tuple(
    s.value for s in CATALOG if UNIT in s.axes and s.terminal
)

#: **Die Zustände, in denen ein Stück im Regal liegt** – die Antwort auf «woraus darf sich
#: FIFO bedienen?».
#:
#: **Nicht** dasselbe wie ``is_selectable`` (``terminal``): ein verbautes Stück lässt sich
#: greifen, liegt aber nicht im Regal.
IN_STOCK_UNIT_STATUSES: tuple[str, ...] = tuple(
    s.value for s in CATALOG if UNIT in s.axes and s.stock == LIVE and not s.terminal
)

#: **Welche Stücke darf ein Auftrag greifen?** Abgeleitet aus ``terminal``.
SELECTABLE_UNIT_STATUSES: tuple[str, ...] = tuple(
    s.value for s in CATALOG if UNIT in s.axes and not s.terminal
)

# «Was zählt zum Bestand» beantwortet ``stock_kind`` je Zustand – keine Liste.

# ---------------------------------------------------------------------------
# Die festen Rand-Übergänge (§4.1)
# ---------------------------------------------------------------------------

#: Start: das Stück tritt in den Prozess ein. **Nicht je Auftrag einstellbar.**
#: Dieser Übergang IST die Aktion «Auftrag freigeben».
START_BEFORE = FREIGEGEBEN
START_AFTER = IM_PROZESS

#: ►►► **Womit ein Auftrag regulär beginnt** – was **ruht**: in keinem Auftrag, nicht gesperrt,
#: in nichts verbaut. ◄◄◄ Bei uns (``FREIGEGEBEN``) oder bei der Partei (``VERKAUFT``).
#: Jeder andere Start ist eine Abweichung (``order_state.deviation_flags``, PROCESS_CORE
#: §12.2). FIFO und Verbrauch nehmen weiterhin nur ``FREIGEGEBEN``.
REGULAR_STARTS: frozenset[str] = frozenset({FREIGEGEBEN, VERKAUFT})

#: Ende: das **Nachher** ist ``FREIGEGEBEN`` – oder ``VERKAUFT``, wenn das Stück einer
#: anderen Partei gehört (``process._finish``).
END_BEFORE = IM_PROZESS
DEFAULT_END_STATUS = FREIGEGEBEN

#: Womit eine frisch angelegte Einzelinstanz startet.
INITIAL_UNIT_STATUS = FREIGEGEBEN

#: Ein Zustand, den der Katalog nicht kennt – **gemeldet**, nicht einsortiert.
UNKNOWN = "unknown"


def label(status: str) -> str:
    """Beschriftung eines Status. Unbekannt → der rohe Wert (sichtbar, nicht versteckt)."""
    return STATUS_LABELS.get(status, status)


def is_terminal(status: str) -> bool:
    """**Ist dieser Zustand endgültig?** – die eine Frage, an der der Schutz hängt.

    Ein unbekannter Wert ist **nicht** terminal: er wird gemeldet (``stock_kind``), nicht
    eingemauert.
    """
    s = _BY_VALUE.get(status)
    return bool(s and s.terminal)


def is_selectable(status: str) -> bool:
    """**Darf ein Auftrag ein Stück in diesem Zustand greifen?**

    Die eine Antwort für Freigabe (``release.release``) und Auswahl-Liste
    (``routers/orders``), abgeleitet aus ``terminal``. Unbekanntes ist nicht wählbar.
    """
    s = _BY_VALUE.get(status)
    return bool(s and not s.terminal)


def stock_kind(status: str) -> str:
    """**Bestand, Historie – oder unbekannt?** Die eine Antwort für die Bestandsansicht.

    Unbekanntes landet in ``UNKNOWN`` – sichtbar als eigene Gruppe.
    """
    s = _BY_VALUE.get(status)
    return s.stock if s and s.stock else UNKNOWN


def in_order(counts: dict[str, int]) -> list[tuple[str, int]]:
    """Gezählte Zustände in **Anzeige-Reihenfolge**, Nullen weggelassen.

    Die Reihenfolge steht nur im ``CATALOG``. Ein **unbekannter** Wert wird hinten
    angehängt statt verschwiegen.
    """
    known = [(s, counts[s]) for s in STATUS_LABELS if counts.get(s)]
    rest = [(s, n) for s, n in counts.items() if s not in STATUS_LABELS and n]
    return known + sorted(rest)


#: Wie der Trigger und seine Funktion heissen (Start und Wächter brauchen dieselben Namen).
TERMINAL_GUARD_FN = "instance_units_terminal_guard"
TERMINAL_GUARD_TRIGGER = "trg_instance_units_terminal"


def terminal_guard_sql(statuses: tuple[str, ...] = TERMINAL_UNIT_STATUSES) -> str:
    """**Der Schutz als Eigenschaft der TABELLE, nicht als Regel der Anwendung.**

    Der Trigger sitzt unter jedem Schreibweg (Modul, Skript, Migration, ``UPDATE`` von Hand).
    **Keine Ausnahme**: was man verlassen können muss, ist nicht terminal.

    Die Liste ist ein Parameter (Test gegen die Fehlerform); im Betrieb kommt sie aus dem
    Katalog, der Start (`main._sync_database_rules`) zieht sie nach. Idempotent.

    Ein ``%`` ist ein plpgsql-Platzhalter – nicht verdoppeln (es kommen keine
    Treiber-Parameter mit).
    """
    values = ", ".join(f"'{s}'" for s in statuses) or "NULL"
    return f"""
DO $guard$
BEGIN
  CREATE OR REPLACE FUNCTION {TERMINAL_GUARD_FN}() RETURNS trigger AS $fn$
  BEGIN
    IF NEW.status IS DISTINCT FROM OLD.status
       AND OLD.status = ANY (ARRAY[{values}]::text[]) THEN
      RAISE EXCEPTION
        'Einzelinstanz % steht auf «%» – das ist ein Endzustand. '
        'Ein Endzustand wird nicht überschrieben (Versuch: «%»).',
        OLD.id, OLD.status, NEW.status
        USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
  END;
  $fn$ LANGUAGE plpgsql;

  DROP TRIGGER IF EXISTS {TERMINAL_GUARD_TRIGGER} ON instance_units;
  CREATE TRIGGER {TERMINAL_GUARD_TRIGGER}
    BEFORE UPDATE ON instance_units
    FOR EACH ROW EXECUTE FUNCTION {TERMINAL_GUARD_FN}();
END
$guard$;
"""


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
