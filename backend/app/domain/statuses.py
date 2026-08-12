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

#: **Der Auftrag ist seinen definierten Weg zu Ende gegangen** (**Auftrag**).
#:
#: Nicht «hat das Ziel erreicht» – das klang nach dem Ende-Objekt und liess einen Auftrag
#: zweifelhaft aussehen, dessen Stücke durch einen **Ausgang** hinausgingen (§4.6). Ein
#: terminales Modul IST das Ende des Weges; wer dort ankommt, ist fertig, auch wenn er das
#: Ende-Objekt nie passiert. Genau das zählt ``process.order_statuses`` schon immer:
#: Zugehörigkeit geschlossen **und** vor keinem Modul mehr stehend.
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

#: **Steckt in einem anderen Stück** (**Einzelinstanz**). Es hat seinen Zweck erreicht:
#: kein Mangel, kein Verlust – darum grün und nicht gelb.
#:
#: **Nicht endgültig**, und das ist eine Entscheidung: Demontage ist real (ein Getriebe
#: wird zerlegt, die Zahnräder gehen zurück ins Lager). Ein Auftrag darf das Stück
#: greifen – **das Greifen IST der Ausbau**, genau wie beim Sperren; und weil sein Start
#: dann vom Regelstart abweicht, ist der Vorgang **automatisch** eine Abweichung
#: (``process.deviation_flags``) und damit dokumentiert, ohne eine Zeile dafür.
#:
#: **Die Stückliste liest darum den LOG, nicht diesen Wert** (``services/genealogy``):
#: läse sie den heutigen Zustand, verschwände ein ausgebautes Teil rückwirkend aus der
#: Vergangenheit des Produkts. Was verbaut *war*, bleibt verbaut gewesen.
VERBAUT = "verbaut"

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
    #: Position im Fluss** (§5.4); die konkreten Farbwerte stehen in den Design-Tokens.
    tone: str
    #: Welche Achsen ihn tragen können.
    axes: tuple[str, ...]
    #: **Bestand oder Historie?** Pflicht für jeden Zustand, den ein Stück tragen kann;
    #: für alle anderen sinnlos und darum verboten (siehe ``_check``).
    stock: str | None = None
    #: **Ist dieser Zustand endgültig?**
    #:
    #: Die stärkste Eigenschaft, die ein Status haben kann: aus ihm heraus gibt es keinen
    #: Übergang mehr – aus keinem Anlass, an keiner Stelle, durch kein Modul. Was passiert
    #: ist, ist passiert.
    #:
    #: **Alles Weitere folgt daraus, statt daneben zu stehen:**
    #:
    #: * ``is_selectable`` – ein Auftrag kann ein Stück in einem Endzustand nicht
    #:   aufnehmen. Er könnte nichts damit tun; die Aufnahme wäre ein Versprechen, das
    #:   der erste Schritt bricht. (Das war einmal ein eigenes Feld ``selectable``. Zwei
    #:   Felder für dieselbe Frage sind zwei Stellen, an denen sie verschieden beantwortet
    #:   werden kann – und genau eine davon wird beim nächsten Zustand vergessen.)
    #: * der **Schutz in der Datenbank** (``terminal_guard_sql``): ein Trigger weist jeden
    #:   Statuswechsel aus einem Endzustand ab. Nicht als Anwendungsregel, sondern als
    #:   Eigenschaft der Tabelle – es gibt keinen Parameter, der ihn abschaltet.
    #:
    #: **Die Farbe folgt NICHT hieraus.** Hier stand einmal «was endgültig ist, ist rot;
    #: was aufhebbar ist, gelb» – das stimmte, solange die einzigen beiden Ausgänge
    #: *Verschrottet* und *Gesperrt* hiessen. Mit *Verbaut* stimmt es nicht mehr: ein
    #: verbautes Stück ist aufhebbar **und** grün, weil es seinen Zweck erreicht hat. Der
    #: Ton sagt «gut · offen · Problem», ``terminal`` sagt «gibt es einen Weg zurück» –
    #: zwei Fragen, und eine Regel, die beide beantwortet, wäre beim nächsten Zustand
    #: falsch. Sie steht darum je Eintrag im Katalog.
    #:
    #: Nur ein **Stück**-Zustand darf terminal sein: er ist der einzige, der gespeichert
    #: und geändert wird. Auftrags- und Artikel-Zustände sind abgeleitet bzw. anderswo
    #: geführt; sie hier terminal zu nennen wäre eine Zusage, die niemand einlöst.
    terminal: bool = False


#: **Die eine Liste.** Reihenfolge = Anzeige-Reihenfolge (Leiste, Legende, Filter).
CATALOG: tuple[Status, ...] = (
    Status(FREIGEGEBEN, "Freigegeben", "done", (UNIT, ARTICLE), stock=LIVE),
    Status(IM_PROZESS, "Im Prozess", "pending", (UNIT, ORDER), stock=LIVE),
    # **Gesperrt zählt zum Bestand.** Das Stück liegt im Regal – es ist da, nur nicht
    # verwendbar. Es in die Historie zu legen hiesse, den Bestand kleiner zu melden, als
    # er ist; die Leiste zeigt es als eigenes Segment, und genau das ist die Auskunft.
    Status(GESPERRT, "Gesperrt", "pending", (UNIT,), stock=LIVE),
    # **Verbaut zählt zur Historie.** Das Stück liegt nicht im Regal – es steckt in einem
    # anderen. Als Bestand geführt wäre es Material, das niemand greifen kann, ohne
    # vorher etwas auseinanderzunehmen.
    #
    # **Historie und nicht terminal** ist damit die erste Kombination dieser Art – und
    # der Beleg, dass die beiden Eigenschaften unabhängig sind: «zählt es zum Bestand»
    # und «gibt es einen Weg zurück» sind zwei Fragen. Nachgemessen: nichts im System
    # koppelt sie.
    Status(VERBAUT, "Verbaut", "done", (UNIT,), stock=HISTORY),
    Status(VERSCHROTTET, "Verschrottet", "danger", (UNIT,), stock=HISTORY, terminal=True),
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

#: **Die Endzustände eines Stücks.** Die eine Liste, aus der der Schutz entsteht – in der
#: Anwendung (``process._pass``) wie in der Datenbank (``terminal_guard_sql``).
TERMINAL_UNIT_STATUSES: tuple[str, ...] = tuple(
    s.value for s in CATALOG if UNIT in s.axes and s.terminal
)

#: **Welche Stücke darf ein Auftrag greifen?** Abgeleitet aus derselben Eigenschaft –
#: keine zweite Liste, die jemand nachzieht, wenn ein Zustand dazukommt.
SELECTABLE_UNIT_STATUSES: tuple[str, ...] = tuple(
    s.value for s in CATALOG if UNIT in s.axes and not s.terminal
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


def is_terminal(status: str) -> bool:
    """**Ist dieser Zustand endgültig?** – die eine Frage, an der der Schutz hängt.

    Ein unbekannter Wert ist **nicht** terminal: sonst wäre ein Tippfehler in den Daten
    eine Sperre, die niemand mehr aufheben kann. Unbekanntes wird gemeldet
    (``stock_kind`` → ``unknown``), nicht eingemauert.
    """
    s = _BY_VALUE.get(status)
    return bool(s and s.terminal)


def is_selectable(status: str) -> bool:
    """**Darf ein Auftrag ein Stück in diesem Zustand greifen?**

    Die eine Antwort für die Freigabe (``process.release``) **und** für die Auswahl-Liste
    (``routers/orders``). Getrennt gestellt wären es zwei Regeln, und die Oberfläche böte
    irgendwann etwas an, das der Server ablehnt – oder schlimmer, umgekehrt.

    **Abgeleitet aus ``terminal``**, nicht daneben deklariert: aufnehmen heisst, etwas tun
    zu wollen, und aus einem Endzustand heraus gibt es nichts mehr zu tun.

    Ein unbekannter Wert ist **nicht** wählbar: was der Katalog nicht kennt, kann er auch
    nicht erlauben.
    """
    s = _BY_VALUE.get(status)
    return bool(s and not s.terminal)


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


#: Wie der Trigger und seine Funktion heissen. An **einer** Stelle, weil Migration,
#: Sicherheitsnetz und Wächter dieselben Namen brauchen.
TERMINAL_GUARD_FN = "instance_units_terminal_guard"
TERMINAL_GUARD_TRIGGER = "trg_instance_units_terminal"


def terminal_guard_sql(statuses: tuple[str, ...] = TERMINAL_UNIT_STATUSES) -> str:
    """**Der Schutz als Eigenschaft der TABELLE, nicht als Regel der Anwendung.**

    Ein Endzustand ist endgültig – und «endgültig» ist nur dann eine Zusage, wenn es
    keinen Weg daran vorbei gibt. Eine Prüfung in der Anwendungslogik ist ein Weg, den
    man vergessen kann: ein neues Modul, ein Reparaturskript, eine Migration, ein
    ``UPDATE`` von Hand. Der Trigger kennt sie alle, weil er unter ihnen sitzt.

    **Kein Parameter, kein Force-Flag, keine Ausnahme.** Wer eine bräuchte, hat ein
    Modellproblem und keinen Sonderfall: ein Zustand, den man doch verlassen können muss,
    ist schlicht nicht terminal – und das ist eine Zeile im ``CATALOG``.

    Die Liste ist ein **Parameter**, damit ein Test die Regel gegen ihre Fehlerform
    prüfen kann; im Betrieb kommt sie aus dem Katalog, und das Sicherheitsnetz beim Start
    zieht sie nach. Damit kann die Datenbank nicht von der einen Liste abweichen.

    Idempotent: ``CREATE OR REPLACE`` plus ein ``DROP TRIGGER IF EXISTS``.

    **Ein ``%`` ist ein Platzhalter, kein Sonderzeichen.** In der Meldung stehen einfache
    Prozentzeichen, weil plpgsql sie so liest; ``%%`` wäre ein *literales* Prozentzeichen,
    und die Funktion liesse sich gar nicht erst übersetzen («too many parameters specified
    for RAISE»). Der Reflex, sie zu verdoppeln, kommt vom Datenbanktreiber – der ersetzt
    aber nur, wenn Parameter mitkommen, und hier kommen keine.
    """
    values = ", ".join(f"'{s}'" for s in statuses) or "NULL"
    return f"""
DO $guard$
BEGIN
  IF to_regclass('public.instance_units') IS NULL THEN
    RETURN;
  END IF;

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
