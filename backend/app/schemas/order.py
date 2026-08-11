"""Auftrag – API-Form.

Der Entwurf kommt in **einem** Aufruf an: Definitionszeilen und Prozessschritte zusammen.
Das ist keine Bequemlichkeit, sondern die Folge aus PROCESS_CORE.md §6.3 – der Auftrag
entsteht erst bei der Freigabe, und die ist eine Transaktion. Zwei Aufrufe hiessen zwei
Transaktionen und damit die Möglichkeit eines halben Auftrags.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, computed_field

from ..domain import modules, sampling

from .process import ModuleInput


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
    origin: str
    units: list[UnitPick] = Field(default_factory=list)
    #: **Die Rückführung** – kehren Stücke, die aus einem laufenden Auftrag übernommen
    #: werden, dorthin zurück (Abweichungsauftrag §3.3/§3.4)? Gespeichert wird sie an der
    #: **Verbindung** (``order_units.return_to_order_id``), nicht am Auftrag; darum
    #: funktionieren Schachtelung und Parallelität ohne Zusatzregel.
    #:
    #: Für freie Stücke bedeutungslos: sie kommen aus keinem Auftrag.
    returns: bool = True


class OrderCreate(BaseModel):
    """Der Entwurf, so wie ihn die Oberfläche schickt."""

    lines: list[DefinitionLine] = Field(default_factory=list)
    #: Der modellierte Prozess. Ein Auftrag mit einer ``Neu``-Zeile **ignoriert** ihn:
    #: sein Prozess ist die Vorlage des Artikels, als Kopie. Etwas anderes zu schicken
    #: änderte daran nichts.
    steps: list[ModuleInput] = Field(default_factory=list)


#: Die Marke, unter der ein Entwurf im Bild seines künftigen Nachbarn steht. Er hat noch
#: keine Objektnummer (§6.1) – und soll auch keine bekommen, nur um gezeichnet zu werden.
#: Null ist keine gültige Objektnummer (der Kreis beginnt bei 100'000'001), kollidiert
#: also mit nichts.
DRAFT_OBJECT_ID = 0


class OrderValidation(BaseModel):
    """Antwort auf «wäre dieser Entwurf freigebbar?» – ohne etwas anzulegen."""

    saveable: bool
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


class ProcessStepResponse(BaseModel):
    """Ein Modul im laufenden Auftrag.

    **Die ``id`` ist seine Identität** (Testnotiz #687): der Ereignis-Log zeigt auf sie
    und auf nichts sonst. ``label`` ist nur die Beschriftung und **abgeleitet** aus
    ``domain/modules`` – ein gespeicherter Name wäre eine zweite Aussage darüber, was
    dieses Modul ist, und die erste falsche Eingabe liesse beide auseinanderlaufen.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    position: int
    module_type: str
    status_before: str
    status_after: str
    #: Was der Modultyp braucht – bei der Datenerfassung die Erfassungspunkte.
    config: Optional[dict] = None
    #: Gesetzt, wenn dieser Schritt die **Kopie** eines Artikel-Erzeugungsprozesses ist.
    source_article_id: Optional[int] = None
    source_version: Optional[int] = None
    #: **Worauf dieses Modul wartet** – Objektnummern der Abweichungen, deren Rückführung
    #: aussteht. Nicht leer heisst: gesperrt. Die Sperre wird serverseitig durchgesetzt
    #: (``process.confirm_step``); diese Liste ist die **Begründung** für die Oberfläche,
    #: nicht ihre Regel. Abgeleitet, nicht gespeichert (``process.pending_returns``).
    waiting_for: list[int] = Field(default_factory=list)
    #: **Die Arbeitsliste dieses Moduls** – eine Zeile je wartender Instanz
    #: (``process.step_work``). Ein Vorgang ist eine Instanz, weil der Scan eine Instanz
    #: verifiziert; die Liste ist damit zugleich die Liste der zu scannenden Dinge.
    work: list["StepWork"] = Field(default_factory=list)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def label(self) -> str:
        """Wie das Modul heisst – aus der Registry, nicht aus einer Spalte."""
        return modules.label(self.module_type)

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
    #: Die übrigen: sie laufen ohne Erfassung durch. Sichtbar, nicht stillschweigend.
    rest: int
    #: Hat die letzte Erfassung **nicht bestanden**? Dann rückt hier nichts vor (§4).
    held: bool = False
    failed_numbers: list[str] = Field(default_factory=list)


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
    #: **Wann dieses Stück das Start-Objekt passiert hat** (Testnotiz #689). Aus dem
    #: Ereignis-Log, nicht aus einer neuen Spalte: der Start ist ein Ereignis wie jedes
    #: andere, und sein Zeitstempel steht dort bereits. Ein Feld daneben wäre eine Kopie,
    #: die beim ersten Nacherfassen auseinanderläuft.
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
    end_status: str
    steps: list[ProcessStepResponse] = Field(default_factory=list)
    #: **Sein** Graph – dieselbe Form wie in der Mitte, mit derselben Komponente
    #: gezeichnet. Darin stehen auch die Kanten zu *diesem* Auftrag: ein übergeordneter
    #: Auftrag trägt seine ``out``-Kante zu uns, wir tragen unsere zu den Abweichungen.
    #: Beide Richtungen stammen damit aus dem Log dessen, bei dem sie passiert sind –
    #: es gibt keine zweite Ableitung für die Gegenrichtung.
    flow: FlowGraph = Field(default_factory=FlowGraph)
    active_step_id: Optional[int] = None
    #: Wie viele Stücke dieses Auftrags stammen aus bzw. gehen an den gezeigten Auftrag.
    unit_count: int
    #: Kehren sie zurück? Bei ``False`` läuft der Quell-Auftrag mit weniger weiter.
    returns: bool = False


class OrderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    object_id: int
    #: «Auftrag <Objektnummer>», bei der Freigabe gesetzt.
    name: str
    #: **Abgeleitet** aus dem Zustand der Einzelinstanzen (``process.order_status``) –
    #: es gibt keine Spalte dafür. Drei Werte: Im Prozess · Abgeschlossen · Abgebrochen.
    status: str
    end_status: str
    created_at: datetime
    updated_at: datetime
    is_active: bool

    lines: list[OrderLineResponse] = Field(default_factory=list)
    steps: list[ProcessStepResponse] = Field(default_factory=list)
    #: **Das Bild** – Knoten, Kanten, Positionen (``services/flow``). Es ersetzt die
    #: frühere flache Liste ``unit_groups``: die sagte nur, wie viele Stücke wo stehen,
    #: und die Oberfläche musste daraus selbst ableiten, wo Linien verlaufen und wie
    #: weit sie kräftig sind. Genau diese Ableitung gehört hierher.
    flow: FlowGraph = Field(default_factory=FlowGraph)
    events: list[ProcessEventResponse] = Field(default_factory=list)
    #: Wie viele Einträge der Log **insgesamt** hat. Ist er länger als ``events``, sagt
    #: die Oberfläche das – ein stumm gekappte Liste sähe aus wie die ganze Wahrheit.
    event_count: int = 0

    #: **Die Journey** (Testnotiz-Auftrag Teil A) – woher die Stücke dieses Auftrags
    #: kamen und wohin sie gingen. Beides **abgeleitet** aus dem Ereignis-Log
    #: (``services/journey``), nicht gepflegt: Zeiger-Felder liefen irgendwann
    #: auseinander, und dann wäre die Journey für genau das unbrauchbar, was sie
    #: beweisen soll. Leer heisst «keiner» – kein Platzhalter, nichts erfunden.
    journey_in: list[JourneyNeighbour] = Field(default_factory=list)
    journey_out: list[JourneyNeighbour] = Field(default_factory=list)
    #: Welches Modul ist jetzt dran – **abgeleitet**, nicht gespeichert.
    active_step_id: Optional[int] = None

    # ── Struktur: übergeordnete Aufträge ↔ Abweichungen ──────────────────────
    #
    # **«Abweichung» ist eine Auskunft, kein Feld** (§2): sie ergibt sich aus dem Log –
    # der Start-Eintrag dieses Auftrags trägt ``status_before = im_prozess``, das Stück
    # kam also aus einem laufenden Auftrag. Es gibt keinen Auftragstyp und keine Spalte.
    is_deviation: bool = False
    #: Links: die Aufträge, aus denen dieser hier Stücke übernommen hat.
    parents: list[RelatedOrder] = Field(default_factory=list)
    #: Rechts: die Aufträge, die diesem hier Stücke abgenommen haben. **Gekappt bei
    #: ``RELATED_LIMIT``** – bei vielen Abweichungen wäre die Antwort sonst so gross wie
    #: die Summe aller Abläufe. ``deviation_total`` nennt die wahre Zahl.
    deviations: list[RelatedOrder] = Field(default_factory=list)
    deviation_total: int = 0
    #: Wie viele Stücke sind gerade ausgeliehen und kommen zurück – **abgeleitet** aus
    #: den offenen rückführenden Verbindungen. 0 heisst: dieser Auftrag wartet auf nichts.
    waiting_for_return: int = 0


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
    is_active: bool
    #: Kleines Label neben dem Zustand – **abgeleitet**, siehe ``OrderResponse``.
    is_deviation: bool = False


class ArticleOption(BaseModel):
    """Ein wählbarer Artikel für eine Definitionszeile.

    ``template_steps`` ist die Zahl der Module im Erzeugungsprozess. Sie steht hier,
    damit die Oberfläche «Neu» sperren **und den Grund nennen** kann – ohne Vorlage kann
    ein Erzeugungsauftrag nichts erzeugen.
    """

    object_id: int
    name: str
    serialization: str
    unit: str
    template_steps: int


class UnitOption(BaseModel):
    """Eine wählbare Einzelinstanz für eine ``Lager``-Zeile.

    ``in_order`` nennt den Auftrag, in dem das Stück gerade läuft. Das ist **kein
    Hindernis mehr**: ein Stück im Prozess lässt sich nehmen, und genau daraus wird eine
    Abweichung (§2/§3.5). Die Angabe steht hier, damit die Oberfläche sagen kann, was
    beim Wählen passiert – statt es geschehen zu lassen.

    ``available`` heisst darum nur noch: dieses Stück lässt sich überhaupt nehmen.
    """

    number: str
    status: str
    article_object_id: Optional[int] = None
    article_name: Optional[str] = None
    available: bool
    in_order: Optional[int] = None
