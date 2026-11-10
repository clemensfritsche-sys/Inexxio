"""Auftrag – API-Form.

Der Entwurf kommt in **einem** Aufruf an: Definitionszeilen und Prozessschritte zusammen.
Das ist keine Bequemlichkeit, sondern die Folge aus PROCESS_CORE.md §6.3 – der Auftrag
entsteht erst bei der Freigabe, und die ist eine Transaktion. Zwei Aufrufe hiessen zwei
Transaktionen und damit die Möglichkeit eines halben Auftrags.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, computed_field

from ..domain import loop as loop_rules, modules, sampling
from ..models.order_line import ORIGINS

from .voucher import VoucherEmbed
from .instance import StockState
from .place import PlaceRef
from .process import ModuleFacts, ModuleInput


class UnitPick(BaseModel):
    """Ein gewähltes Stück — **und wo es lag, als es gewählt wurde.**

    Ein Entwurf lebt im Browser, die Freigabe passiert später. Dazwischen kann jemand
    anders dasselbe Stück nehmen: die Exklusivität (§3) verhindert, dass beide es halten,
    aber ohne diese Angabe **entscheidet die Zeit**, welche Art Auftrag entsteht. Genau das
    ist passiert – ein als frei gewähltes Stück, das inzwischen lief, machte die Freigabe
    **still** zur Abweichung und entzog es dem anderen Auftrag, ohne Rückführung und ohne
    dass jemand gefragt wurde.

    ``from_order`` ist darum keine Zusatzinfo, sondern die **Aussage des Menschen**: «ich
    nehme ein freies Stück» (``None``) oder «ich hole es aus Auftrag N». Stimmt sie bei
    der Freigabe nicht mehr, bricht die Freigabe ab und sagt, was sich geändert hat —
    statt lautlos etwas anderes zu tun als gewollt.

    Damit gibt es **eine** Auswahl-Logik: konkrete Stücke, sichtbar vorher, änderbar, und
    mit der Absicht, in der sie gewählt wurden. Kein zweiter Weg «nur nach Kriterium».
    """

    number: str
    #: Objektnummer des Auftrags, in dem das Stück bei der Auswahl lief. ``None`` = frei.
    from_order: Optional[int] = None


class DefinitionLine(BaseModel):
    """Eine Definitionszeile: Artikel · Menge · Herkunft.

    ``quantity`` referenziert **immer exakt Einzelinstanzen** – nie Instanzen und nie
    eine Artikelmenge. Bei ``origin='lager'`` müssen genau so viele ``units``
    dabeistehen; bei ``origin='neu'`` bleiben sie leer, weil die Stücke erst bei der
    Freigabe entstehen.
    """

    article_object_id: int
    quantity: int = Field(ge=1)
    #: Woher die Stücke kommen: ``neu`` (werden erzeugt) oder ``lager`` (bestehende, in ``units``).
    #: Die erlaubten Werte stehen im Schema (``enum`` aus ``order_line.ORIGINS``); geprüft wird im
    #: Dienst, mit einem Satz.
    origin: str = Field(json_schema_extra={"enum": list(ORIGINS)})
    units: list[UnitPick] = Field(default_factory=list)
    #: **Die Rückführung** – kehren übernommene Stücke in ihren Auftrag zurück (§3.3/§3.4)?
    #: Gespeichert an der Verbindung (``order_units.return_to_order_id``); für freie Stücke
    #: bedeutungslos.
    returns: bool = True


class LoopIn(BaseModel):
    """►► **Die Schlaufe im Entwurf** – eingestellt wie ein Dauerauftrag (``domain/loop``). ◄◄

    Geprüft wird sie im Dienst (``loop.draft_problems``), nicht hier: so nennt die Prüfung des
    Entwurfs jeden fehlenden Teil als Satz, statt mit 422 abzubrechen."""

    #: Der Takt (``domain/loop.EVERY``) – im Schema als ``enum``, geprüft im Dienst.
    every: Optional[str] = Field(None, json_schema_extra={"enum": [*loop_rules.EVERY, None]})
    #: Die erste Wiederholung (Kalendertag, heute oder später).
    first: Optional[str] = None
    #: Ende: ein Datum **oder** eine Anzahl Wiederholungen – beides leer heisst unbefristet.
    until: Optional[str] = None
    count: Optional[int] = None
    #: Je Zeile des Entwurfs (gleiche Reihenfolge): ``same`` (gleiche Einzelinstanzen) oder
    #: ``fifo``; bei einer Zeile «Neu» bedeutungslos. **Ohne Vorbelegung**.
    takes: list[Optional[str]] = Field(
        default_factory=list,
        json_schema_extra={"items": {"enum": [*loop_rules.TAKES, None]}})


class OrderCreate(BaseModel):
    """Der Entwurf, so wie ihn die Oberfläche schickt."""

    lines: list[DefinitionLine] = Field(default_factory=list)
    #: Der modellierte Prozess; ein Auftrag mit einer ``Neu``-Zeile ignoriert ihn (sein
    #: Prozess ist die Vorlage des Artikels, als Kopie).
    steps: list[ModuleInput] = Field(default_factory=list)
    #: **Die Schlaufe** – nur im Entwurf; mit der Freigabe eingefroren (Wiederkehr).
    loop: Optional[LoopIn] = None


#: Die Marke, unter der ein Entwurf im Bild seines künftigen Nachbarn steht – er hat noch
#: keine Objektnummer (§6.1); 0 kollidiert mit keiner.
DRAFT_OBJECT_ID = 0


class OrderValidation(BaseModel):
    """Antwort auf «wäre dieser Entwurf freigebbar?» – ohne etwas anzulegen."""

    missing: list[str] = Field(
        default_factory=list,
        description="Was noch fehlt – leer heisst freigebbar.",
    )
    parents: list["RelatedOrder"] = Field(
        default_factory=list,
        description=(
            "**Die Vorschau**: die laufenden Aufträge, aus denen dieser Entwurf Stücke "
            "nähme – jeder mit dem Bild, das er nach der Freigabe hätte (Abzweigung, "
            "und Rückführpunkt nur, wenn zurückgeführt wird). Damit zeigt der Entwurf "
            "dieselbe Darstellung wie der freigegebene Auftrag; sie kommt aus derselben "
            "Ableitung (``flow.build``) und wird nicht daneben nachgebaut."
        ),
    )


class ProcessStepResponse(ModuleFacts):
    """Ein Modul im laufenden Auftrag.

    **Die ``id`` ist seine Identität** (Testnotiz #687): der Ereignis-Log zeigt auf sie
    und auf nichts sonst. Beschriftung, Farbfamilie und «Ausgang?» kommen aus
    ``ModuleFacts`` – abgeleitet aus dem Typ, nie gespeichert.
    """

    id: int
    position: int
    #: Was der Modultyp braucht – bei der Datenerfassung die Erfassungspunkte.
    config: Optional[dict] = None
    #: **Worauf dieses Modul wartet** – Abweichungen mit ausstehender Rückführung; nicht leer
    #: heisst gesperrt. Die Begründung für die Oberfläche; durchgesetzt in
    #: ``process.confirm_step``, abgeleitet aus ``order_state.pending_returns``.
    waiting_for: list[int] = Field(default_factory=list)
    #: **Die Arbeitsliste** – eine Zeile je wartender Instanz (``order_state.step_work``),
    #: zugleich die Liste der zu scannenden Dinge.
    work: list["StepWork"] = Field(default_factory=list)
    #: **Was dieses Modul verbraucht** (``services/consumption``); leer ohne Stückliste.
    needs: list["StepNeed"] = Field(default_factory=list)
    #: **Wohin dieses Modul bringt** – aufgelöst auf den Namen (``services/places``). ``None``
    #: heisst beim Bewegen «wird beim Ausführen gewählt», nicht «vergessen».
    target: Optional[PlaceRef] = None
    #: ►►► **Der Beleg** (``services/voucher``) – nur beim Modul «Zahlung», sonst ``None``.
    voucher: Optional[VoucherEmbed] = None
    #: ►►► **Warum lässt sich dieses Modul JETZT nicht abschliessen?** ◄◄◄ ``None`` = nichts
    #: im Weg. aus ``Module.passes_itself`` (dieselbe Regel weist in ``confirm_step`` ab).
    blocked: Optional[str] = None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def action(self) -> str:
        """Wie die Ausführung dieses Moduls heisst – das Verb auf dem Knopf.

        Aus der Registry (``Module.action_for``), nicht aus der Oberfläche: beim
        Aussondern hängt es an der Ausprägung, und «Erfassen & bestätigen» über einem
        Verschrotten-Modul wäre schlicht falsch.
        """
        return modules.get(self.module_type).action_for(self.config)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def sample(self) -> str:
        """Die Stichprobenregel als **Satz** – aus einer Quelle (``sampling.describe``).

        Sie steht in ``config``, aber die Oberfläche soll sie nicht selbst formulieren:
        «3 je Instanz» ist eine Aussage über das Los, und eine zweite Formulierung
        daneben liefe der ersten davon. Was zur **Laufzeit** wirklich gezogen wurde,
        sagt ``StepWork`` – das ist die Ziehung, nicht die Regel.
        """
        return sampling.describe(modules.sample_of(self.config))

    @computed_field  # type: ignore[prop-decorator]
    @property
    def reason(self) -> str:
        """**Warum** hier ausgesondert wird – aus der Definition, nicht vom Band.

        Der Grund wird beim Modellieren gegeben (``domain/modules.Aussondern``) und
        gehört damit zum Modul, nicht zum einzelnen Vorgang. Er steht hier, damit die
        Ausführungsstelle ihn zeigen kann, ohne in ``config`` zu greifen – und damit
        jedes künftige Modul, das einen mitbringt, ihn ohne eine Zeile Oberfläche erbt.
        Leer heisst: dieses Modul kennt keinen.
        """
        return modules.reason_of(self.config)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def records(self) -> bool:
        """►►► **Hat dieses Modul mehr zu berichten als die blosse Passage?** (#825) ◄◄◄

        Das Protokoll (``services/record``) bleibt für **jedes** Modul, was es ist: der
        Nachweis. Aber bei einem Modul, das am Stück nichts ändert, nichts erfasst und
        nichts verifiziert, blieben genau drei Angaben übrig – eine Nummer, ein Name und
        eine Uhrzeit –, und die Frage «warum steht die hier?» war berechtigt.

        **Gefragt wird die Sache, nicht der Modultyp.** Ein ``if module_type ==
        'zahlung'`` wäre beim nächsten Modul ohne physisches Gegenstück wieder falsch.
        Es gibt genau drei Dinge, die ein Eintrag über «wer, wann» hinaus tragen kann:

        * **erfasste Werte** – das Modul hat Erfassungspunkte (``config``),
        * **ein Zustandswechsel** – ein Ausgang (``terminal``): wer hier ankommt, geht hinaus,
        * **eine Verifikation** – der Scan, der sagt, welches physische Ding es war.

        Trifft keines zu, ist das Protokoll leer im Wortsinn und wird nicht angeboten.
        Alle drei Angaben stehen **am Schritt**; es braucht dafür keine Abfrage auf den
        Log, und schon gar nicht eine je Modul in jeder Auftrags-Antwort.
        """
        return bool(
            modules.points_of(self.config)
            or self.terminal
            or self.verifies
        )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def open_actions(self) -> bool:
        """►►► **Kann man an diesem Modul noch etwas tun?** (Testnotiz #821) ◄◄◄

        Die Oberfläche graut ein Modul aus, an dem nichts mehr ansteht – und das war
        genau dann falsch, wenn der Auftrag längst durch ist und trotzdem noch eine
        Rechnung oder eine Zahlung zu buchen ist (ein Zahlungsziel läuft weiter, wenn
        die Ware draussen ist). Die Karte sagte optisch «hier ist nichts mehr», während
        ihre Knöpfe funktionierten.

        **Abgeleitet, nicht gespeichert – und aus derselben Tabelle, die auch das Tor
        ist**: ``can`` am Beleg. Eine zweite Herleitung («ist der Typ ``beleg``?») liefe
        beim nächsten Modul auseinander, und eine Heuristik der Oberfläche wäre eine
        dritte Wahrheit.

        Das aktive Modul fragt hier gar nicht – es ist ohnehin nie ausgegraut.
        """
        return bool(self.voucher.can if self.voucher else [])


class StepWork(BaseModel):
    """Was an einem Modul für **eine Instanz** ansteht.

    Zahlen statt Nummern: bei einer 6000er-Charge wäre der «Rest» sechstausend Nummern
    in jeder Auftrags-Antwort. Wer sie braucht (die Vorauswahl einer Entscheidung), holt
    sie einzeln (``GET …/steps/{id}/hold``) – erst auf Klick.

    Die **durchgefallenen** Nummern stehen trotzdem hier: sie sind die Stichprobe, also
    von Natur aus wenige, und sie sind die eigentliche Auskunft («welches Stück war es»).
    """

    instance_object_id: int
    article_name: Optional[str] = None
    #: Wie viele Stücke dieser Instanz stehen vor dem Modul.
    waiting: int
    #: Davon **gezogen** – nur diese werden erfasst (``domain/sampling``).
    sample: int
    #: Die übrigen: sie laufen ohne Erfassung durch.
    rest: int
    #: Hat die letzte Erfassung **nicht bestanden**? Dann rückt hier nichts vor (§4).
    held: bool = False
    failed_numbers: list[str] = Field(default_factory=list)


class NeedSource(BaseModel):
    """Eine Instanz, aus der genommen werden könnte — und wie viel dort frei liegt."""

    instance_object_id: int
    free: int
    #: **Davon am Arbeitsort** (eine Aussage über die Halter-Kette); ohne Ortsanforderung
    #: gleich ``free``.
    here: int = 0
    #: **Wo diese Kiste liegt** – die Ursache, wenn sie nicht hier ist.
    place: Optional[PlaceRef] = None


class StepNeed(BaseModel):
    """Eine Zeile der Stückliste, **gegen den Bestand gehalten**.

    ``required`` ist die Rechnung dieses Augenblicks: Menge je Stück × Stücke, die vor
    dem Modul stehen. Sie entsteht beim **Erreichen** und nicht beim Definieren – vorher
    weiss niemand, wie viele Produkte ankommen.

    **Fehlt etwas, ist das kein Zustand des Auftrags.** Es gibt keinen Pausen-Wert und
    keine Sperre: das Modul ist schlicht nicht fertig, und diese Zeile sagt in Klartext,
    woran es liegt (Artikel · gebraucht · verfügbar · **davon hier**). Was daraus folgt,
    entscheidet ein Mensch – eine andere Instanz wählen, holen lassen oder Nachschub
    anlegen.

    **«Am falschen Ort» ist dieselbe Aussage wie «zu wenig da», eine Spalte weiter.** Kein
    neuer Zustand, keine Wartelogik: fehlt nur der Ort, ist die Handlung ein Transport;
    fehlt die Menge, eine Beschaffung.
    """

    article_object_id: int
    article_name: str
    #: Menge **je Einzelinstanz** – «4» heisst vier Stück je Produkt, nicht vier im Auftrag.
    per_unit: int
    required: int
    #: Frei – **egal wo**.
    available: int
    #: Davon **am Arbeitsort**; ohne Ortsanforderung gleich ``available``.
    here: int = 0
    #: **Wo das Material liegen muss** – der Ort des Produkts, abgeleitet
    #: (``consumption.required_place``). ``None``: kein Ort verlangt.
    place: Optional[PlaceRef] = None
    #: Woher genommen werden kann – die Kisten, die der Lagerist scannt.
    sources: list[NeedSource] = Field(default_factory=list)
    #: **Was an Menge fehlt** – egal wo (``Need.missing``).
    missing: int = 0
    #: **Was da ist, aber nicht am Arbeitsort** – der Fall für einen Transport
    #: (``Need.misplaced``).
    misplaced: int = 0
    #: **Die Kisten, aus denen der Server nähme** – älteste zuerst, am Ort, wenn einer verlangt
    #: ist (``Need.plan``). Die Oberfläche scannt sie; sie rechnet die Reihenfolge nicht nach.
    plan: list[int] = Field(default_factory=list)


class OrderLineResponse(BaseModel):
    """Eine festgeschriebene Definitionszeile."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    position: int
    quantity: int
    origin: str
    article_object_id: Optional[int] = None
    article_name: Optional[str] = None


class OrderUnitResponse(BaseModel):
    """Ein einzelnes Stück im Auftrag – wo es steht und wie es steht."""

    instance_unit_id: int
    number: str
    status: str
    current_step_id: Optional[int] = None
    active: bool
    #: **Wann dieses Stück das Start-Objekt passiert hat** – aus dem Ereignis-Log.
    started_at: Optional[datetime] = None


class OrderUnitPage(BaseModel):
    """Eine Seite Einzelinstanzen – auf Abruf, wenn eine Gruppe aufgeklappt wird."""

    units: list[OrderUnitResponse] = Field(default_factory=list)
    total: int


class ProcessEventResponse(BaseModel):
    """Ein Eintrag im Ereignis-Log. Append-only – es gibt keinen Schreib-Pfad hierauf."""

    id: int
    kind: str
    step_id: Optional[int] = None
    unit_number: str
    status_before: str
    status_after: str
    actor: Optional[str] = None
    created_at: datetime


class JourneyNeighbour(BaseModel):
    """Ein Nachbar-Auftrag in der Journey – **gruppiert**, nicht je Stück.

    Bei 5000 Einzelinstanzen will niemand 5000 Verweise sehen; die Frage lautet «wie
    viele kamen woher», nicht «welche». Wer die einzelnen Stücke braucht, öffnet den
    genannten Auftrag – dort stehen sie.
    """

    object_id: int
    name: str
    unit_count: int


class FlowNode(BaseModel):
    """Ein **Prozessobjekt** im Bild. Fünf Arten, mehr gibt es nicht.

    ============  ==========================================================
    ``start``     Start-Objekt
    ``module``    ein Prozessschrittmodul
    ``end``       Ende-Objekt
    ``fork``      **Abzweigepunkt** – hier hat ein Stück den Auftrag verlassen
    ``join``      **Rückführpunkt** – hierher kehrt eines zurück
    ============  ==========================================================

    ``at`` ist bei ``module`` die eigene ``step_id``, bei ``fork``/``join`` das Modul,
    **vor** dem der Punkt liegt (§12.4 – das Modul benennt ihn, es besitzt ihn nicht).

    Ein Knoten trägt **keinen Namen**: was in einem Modul steht, sagt seine Zeile in
    ``steps``. Beides hier wäre dieselbe Angabe an zwei Stellen.
    """

    id: str
    kind: str
    at: Optional[int] = None


class FlowUnits(BaseModel):
    """Stücke an **einer** Position – gezählt, nicht aufgezählt.

    ``at_step_id`` und ``active`` sind der Schlüssel, mit dem die Oberfläche die
    einzelnen Nummern nachlädt (``GET …/units``).
    """

    status: str
    count: int
    active: bool
    at_step_id: Optional[int] = None


class FlowEdge(BaseModel):
    """Eine **Kante** zwischen genau zwei Knoten – und was auf ihr steht.

    ``kind`` sagt, wohin sie führt: ``axis`` bleibt in diesem Auftrag, ``out`` geht in
    einen anderen hinaus (``to`` = ``order:<Objektnummer>``, gemeint ist dessen Start),
    ``back`` kommt aus einem anderen zurück (``frm`` = ``order:<Objektnummer>``, gemeint
    ist dessen Ende). Steht dieser Auftrag gerade nicht im Bild, zeichnet die Oberfläche
    die Kante nicht – sie muss dafür nichts wissen und nichts erfragen.

    ``to = null`` gibt es genau einmal: hinter dem Ende. Dort ist der Prozess zu Ende;
    die angekommenen Stücke stehen trotzdem irgendwo, und «irgendwo» ist diese Kante.

    ``walked`` hat **zwei** Werte und keinen dritten: kräftig, wenn Material die Kante
    laut Log erreicht hat – sonst Haarlinie.
    """

    id: str
    frm: str
    to: Optional[str] = None
    kind: str = "axis"
    walked: bool = False
    units: list[FlowUnits] = Field(default_factory=list)


class FlowGraph(BaseModel):
    """**Das Bild, wie der Server es sieht.** Das Frontend layoutet und zeichnet es nur.

    Vorher baute die Oberfläche die Knotenfolge selbst und leitete aus den *aktuellen*
    Stück-Gruppen ab, wie weit die Linie kräftig läuft. Das war Prozesslogik am falschen
    Ort – und sie las den Zustand statt den Log: sobald an einer Stelle nichts mehr
    stand, verschwand sie samt der Abzweigung, die dort stattgefunden hatte.

    ``problems`` ist die Notbremse: verletzte Invarianten (eine Einzelinstanz ohne oder
    mit zwei Positionen, eine Kante ins Leere). Nicht leer heisst, die Oberfläche sagt
    es – ein Bild, das eine Einzelinstanz verliert, ist schlimmer als keines, weil es
    vollständig aussieht.
    """

    nodes: list[FlowNode] = Field(default_factory=list)
    edges: list[FlowEdge] = Field(default_factory=list)
    problems: list[str] = Field(default_factory=list)


class RelatedOrder(BaseModel):
    """Ein **benachbarter Auftrag** – links der übergeordnete, rechts eine Abweichung.

    Er bringt seinen **vollständigen Ablauf** mit (``steps`` + ``flow`` +
    ``active_step_id``), damit die Spalte daneben dieselbe Komponente rendern kann wie
    die Mitte. Eine Zusammenfassung oder ein Symbol wäre eine zweite Darstellungsform
    für dieselbe Sache – und die läuft irgendwann von der ersten weg.

    ``unit_count`` ist die Zahl der Stücke, die **zwischen den beiden** unterwegs sind;
    ``returns`` sagt, ob sie zurückkommen. Beides ist die Beschriftung der Verbindung.
    """

    object_id: int
    name: str
    status: str
    steps: list[ProcessStepResponse] = Field(default_factory=list)
    #: **Sein** Graph – dieselbe Form wie in der Mitte. Beide Richtungen der Kanten stammen
    #: aus dem Log des Auftrags, bei dem sie passiert sind.
    flow: FlowGraph = Field(default_factory=FlowGraph)
    active_step_id: Optional[int] = None
    #: Wie viele Stücke dieses Auftrags stammen aus bzw. gehen an den gezeigten Auftrag.
    unit_count: int
    #: Kehren sie zurück? Bei ``False`` läuft der Quell-Auftrag mit weniger weiter.
    returns: bool = False


class LoopLineView(BaseModel):
    """Was eine Zeile in jeder Wiederholung nimmt."""

    position: int
    article_name: str = ""
    #: ``same`` · ``fifo`` · ``new``.
    take: Optional[str] = None
    take_label: str = ""


class LoopView(BaseModel):
    """►► **Die Schlaufe eines Auftrags** – alles abgeleitet aus dem Log (``services/loop``). ◄◄"""

    every: str
    every_label: str
    #: Der Termin des Nachfolgers (Kalendertag, ISO).
    next: str
    until: Optional[str] = None
    #: Wie viele Wiederholungen noch (bei «nach Anzahl»), sonst ``None``.
    left: Optional[int] = None
    #: Die Schlaufe in einem Satz – derselbe wie auf dem Papier.
    sentence: str = ""
    lines: list[LoopLineView] = Field(default_factory=list)
    #: ``run`` · ``wait`` · ``stuck`` · ``ended`` · ``done`` (Kette zu Ende) · ``continued``.
    state: str
    #: Wort und Ampelton des Zustands (``domain/loop.STATES``) – die Karte übersetzt nichts.
    state_label: str
    tone: str
    #: Warum es wartet bzw. nicht mehr geht – der Satz vom Server; beim Beenden das Datum.
    reason: Optional[str] = None
    successor: Optional[int] = None
    predecessor: Optional[int] = None
    #: Die Zusage, auf die sich Offerte und Zusage dieser Wiederholung stützen.
    agreed_from: Optional[int] = None
    agreed_on: Optional[str] = None
    #: Darf hier beendet werden? Nur am neuesten Auftrag der Kette, solange sie läuft.
    may_end: bool = False


class OrderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    object_id: int
    #: «Auftrag <Objektnummer>», bei der Freigabe gesetzt.
    name: str
    #: **Abgeleitet** (``order_state.order_status``): Im Prozess · Abgeschlossen · Abgebrochen.
    status: str
    created_at: datetime
    updated_at: datetime

    lines: list[OrderLineResponse] = Field(default_factory=list)
    steps: list[ProcessStepResponse] = Field(default_factory=list)
    #: **Das Bild** – Knoten, Kanten, Positionen (``services/flow``); Prozesslogik, nicht
    #: Oberfläche.
    flow: FlowGraph = Field(default_factory=FlowGraph)
    events: list[ProcessEventResponse] = Field(default_factory=list)
    #: Wie viele Einträge der Log **insgesamt** hat (``events`` ist gekappt).
    event_count: int = 0

    #: **Die Journey** – woher die Stücke kamen und wohin sie gingen, abgeleitet aus dem
    #: Log (``services/journey``). Leer heisst «keiner».
    journey_in: list[JourneyNeighbour] = Field(default_factory=list)
    journey_out: list[JourneyNeighbour] = Field(default_factory=list)
    #: Welches Modul ist jetzt dran – **abgeleitet**, nicht gespeichert.
    active_step_id: Optional[int] = None

    # ── Struktur: übergeordnete Aufträge ↔ Abweichungen ──────────────────────
    #
    # «Abweichung» ist eine Auskunft aus dem Log (§2), kein Feld und kein Auftragstyp.
    is_deviation: bool = False
    #: **Die Schlaufe** (Wiederkehr) – ``None``, wenn sich der Auftrag nicht wiederholt.
    loop: Optional[LoopView] = None
    #: Links: die Aufträge, aus denen dieser hier Stücke übernommen hat.
    parents: list[RelatedOrder] = Field(default_factory=list)
    #: Rechts: die Aufträge, die diesem hier Stücke abgenommen haben – gekappt bei
    #: ``RELATED_LIMIT``, die wahre Zahl in ``deviation_total``.
    deviations: list[RelatedOrder] = Field(default_factory=list)
    deviation_total: int = 0


class OrderSummary(BaseModel):
    """Feed-Zeile. Ohne Schritte, Stücke und Historie – die kommen mit dem Detail.

    Genau deshalb lädt das Detailfenster seinen Auftrag **selbst** nach: was hier fehlt,
    kann es nicht anzeigen, und eine Feed-Zeile als Detail zu rendern hiess, einen
    laufenden Prozess als leer darzustellen.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    object_id: int
    name: str
    status: str
    created_at: datetime
    updated_at: datetime
    #: Kleines Label neben dem Zustand – **abgeleitet**, siehe ``OrderResponse``.
    is_deviation: bool = False


class ArticleOption(BaseModel):
    """Ein wählbarer Artikel für eine Definitionszeile.

    Zwei Angaben sagen, ob «Neu» hier möglich ist, und beide tragen ihren Grund mit:
    ``template_steps`` (ohne Vorlage kann ein Erzeugungsauftrag nichts erzeugen) und
    ``create_problem`` (ein Artikel ausser Betrieb erzeugt nichts Neues mehr).

    **Ein ausser Betrieb genommener Artikel bleibt in der Liste** – er wird nur nicht mehr
    erzeugt. Ihn auszublenden hiesse, seinen Restbestand unerreichbar zu machen: die
    vorhandenen Stücke müssen über «Lager» abwickelbar bleiben, sonst liesse sich nicht
    einmal mehr aussondern.
    """

    object_id: int
    name: str
    serialization: str
    unit: str
    template_steps: int
    #: **Warum «Neu» hier nicht geht** – oder ``None``; der Satz aus ``articles.may_create``.
    create_problem: Optional[str] = None


class UnitOption(BaseModel):
    """Eine wählbare Einzelinstanz für eine ``Lager``-Zeile.

    **Zwei Fragen, zwei Felder – und sie sind nicht dieselbe.** Der Statuskatalog trägt
    beide Antworten seit jeher; die Auswahl las nur eine davon (Testnotiz #739):

    ``available``   «lässt sich das überhaupt nehmen?» – aus ``Status.terminal``. Ein
                    **verbautes** Stück ja: das Greifen IST der Ausbau. Ein
                    **verschrottetes** nein: es gibt es physisch nicht mehr.
    ``in_stock``    «liegt es im Regal?» – aus ``Status.stock``. Ein verbautes Stück
                    **nein**: es steckt in einem anderen. Genau das ist die Frage, die
                    FIFO stellt, wenn es die ältesten Stücke vorschlägt.

    Ein Stück ist also greifbar **und trotzdem kein Lagerbestand** – die erste Kombination
    dieser Art, und der Beleg, dass es zwei Eigenschaften sind. Die **Farbe** ist eine
    dritte Frage («hat es sein Ziel erreicht?») und bleibt bei Verbaut grün.

    ``in_order`` nennt den Auftrag, in dem das Stück gerade läuft. Das ist **kein
    Hindernis**: ein Stück im Prozess lässt sich nehmen, und genau daraus wird eine
    Abweichung (§2/§3.5). Die Angabe steht hier, damit die Oberfläche sagen kann, was
    beim Wählen passiert – statt es geschehen zu lassen.
    """

    number: str
    status: str
    article_object_id: Optional[int] = None
    article_name: Optional[str] = None
    available: bool
    #: **Liegt es im Regal?** Die Frage, die FIFO stellt – siehe Klassen-Docstring.
    in_stock: bool = False
    in_order: Optional[int] = None


class UnitChoices(BaseModel):
    """Eine **Seite** wählbarer Einzelinstanzen – plus das, was die Seite nicht weiss.

    Bei zehntausend Schrauben ist eine flache Liste keine Antwort mehr (Testnotiz #740).
    Drei Angaben machen aus der Seite trotzdem eine vollständige Auskunft:

    ``states``    wie viele Stücke es **je Zustand** gibt – über den ganzen Artikel, nicht
                  über die geladene Seite. Eine aus der Seite gezählte Zahl zeigte «300»,
                  wo fünfzigtausend liegen.
    ``preselect`` die FIFO-Vorauswahl, **vom Server**. Sie aus einer gekappten Liste zu
                  ziehen war der eigentliche Fehler: sind die ersten 300 Stücke verbaut,
                  findet die Oberfläche **nichts** – obwohl freie da sind.
    ``total``     wie viele Stücke die aktuelle Auswahl (Filter/Suche) trifft.
    """

    units: list[UnitOption] = Field(default_factory=list)
    total: int = 0
    states: list[StockState] = Field(default_factory=list)
    #: Die Nummern der FIFO-Vorauswahl – älteste zuerst, nur was **im Regal liegt** und in
    #: keinem laufenden Auftrag steckt (ein gebundenes Stück ist nie die Voreinstellung).
    preselect: list[str] = Field(default_factory=list)
