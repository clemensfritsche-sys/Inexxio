"""Auftrag – API-Form.

Der Entwurf kommt in **einem** Aufruf an: Definitionszeilen und Prozessschritte zusammen.
Das ist keine Bequemlichkeit, sondern die Folge aus PROCESS_CORE.md §6.3 – der Auftrag
entsteht erst bei der Freigabe, und die ist eine Transaktion. Zwei Aufrufe hiessen zwei
Transaktionen und damit die Möglichkeit eines halben Auftrags.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, computed_field

from ..domain import modules

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


class OrderValidation(BaseModel):
    """Antwort auf «wäre dieser Entwurf freigebbar?» – ohne etwas anzulegen."""

    saveable: bool
    missing: list[str] = Field(
        default_factory=list,
        description="Was noch fehlt – leer heisst freigebbar.",
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

    @computed_field  # type: ignore[prop-decorator]
    @property
    def label(self) -> str:
        """Wie das Modul heisst – aus der Registry, nicht aus einer Spalte."""
        return modules.label(self.module_type)


class OrderLineResponse(BaseModel):
    """Eine festgeschriebene Definitionszeile."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    position: int
    quantity: int
    origin: str
    article_object_id: Optional[int] = None
    article_name: Optional[str] = None


class UnitGroup(BaseModel):
    """Wie viele Stücke stehen an einer Stelle, in welchem Zustand.

    Die Datenhaltung bleibt **pro Einzelinstanz** – dies ist die Darstellungsfrage. Bei
    5000 Stück ist der Unterschied nicht Geschmack, sondern der zwischen einer Zeile und
    5000. Die einzelnen Nummern holt ``GET …/units``, wenn jemand aufklappt.
    """

    #: ``None`` = am Ende angekommen (bzw. noch nicht gestartet).
    current_step_id: Optional[int] = None
    status: str
    #: ``False`` = die Stücke haben den Auftrag verlassen und sind wieder frei.
    active: bool
    count: int


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


class BranchPoint(BaseModel):
    """**Der Zustandspunkt**, an dem Stücke ausgeschert sind.

    Ein Zustandspunkt ist die Stelle auf der Prozesslinie, an der ein Stück wartet –
    zwischen zwei Objekten, nicht in einem. Er heisst «**vor** Modul ``at_step_id``»;
    ``None`` ist der Punkt nach dem Ende. Das Modul benennt den Punkt, es besitzt ihn
    nicht: die Abzweigung geht **vor** dem Modul von der Linie ab, weil das Stück es zu
    diesem Zeitpunkt noch gar nicht betreten hatte – und darum durchläuft es das Modul
    nach der Rückkehr regulär.
    """

    at_step_id: Optional[int] = None
    unit_count: int


class RelatedOrder(BaseModel):
    """Ein **benachbarter Auftrag** – links der übergeordnete, rechts eine Abweichung.

    Er bringt seinen **vollständigen Ablauf** mit (``steps`` + ``unit_groups`` +
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
    unit_groups: list[UnitGroup] = Field(default_factory=list)
    active_step_id: Optional[int] = None
    #: Wie viele Stücke dieses Auftrags stammen aus bzw. gehen an den gezeigten Auftrag.
    unit_count: int
    #: Kehren sie zurück? Bei ``False`` läuft der Quell-Auftrag mit weniger weiter.
    returns: bool = False
    #: **An welchen Zustandspunkten** des betrachteten Auftrags die Abzweigung ansetzt.
    #: Eine Liste, weil derselbe Auftrag an zwei Stellen zugegriffen haben kann; ein
    #: einzelner Wert hätte sich für eine entschieden und die andere verschwiegen.
    #: Bei einem übergeordneten Auftrag genau ein Eintrag mit ``at_step_id = None``:
    #: von dort kommen die Stücke am **Start** herein.
    branches: list[BranchPoint] = Field(default_factory=list)


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
    #: Gezählt, nicht aufgelistet – siehe ``UnitGroup``.
    unit_groups: list[UnitGroup] = Field(default_factory=list)
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
