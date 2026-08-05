from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator

from .article_process_step import ArticleProcessStepCreate
from .disposal import DisposalEmbed
from .document import DocumentEmbed
from .inspection import InspectionEmbed
from .instance import InstanceUnit, InstanceEmbed, MaterialMoveView
from .movement import MovementEmbed
from .purchase_order import PurchaseEmbed
from .resource import ResourceEmbed
from .sale import SaleEmbed


class ShortfallInstance(BaseModel):
    """Eine freie, freigegebene Instanz am Lager, mit der sich eine Fehlmenge decken liesse
    («Andere Instanz wählen»)."""
    object_id: int
    quantity: float = 1   # Bruchmenge möglich (kg/m²/…)


class AffectedShare(BaseModel):
    """**Woher** der Verlust kommt – Instanz + Menge. Ohne diese Angabe nennt die Frage nur
    eine Zahl, und die Zahl allein beantwortet nicht, welches Stück gemeint ist (#393)."""
    instance_object_id: int
    quantity: float = 0


class AffectedOrder(BaseModel):
    """**Wem nimmt die Auswahl dieses Entwurfs etwas weg?**

    Steht am **Entwurf**, nicht erst im Fehlerfall: wer gebundene Instanzen wählt, greift auf
    laufende Aufträge zu – und soll **vor** der Freigabe sehen, auf welche. Die Frage «was
    geschieht dort weiter?» (pausieren · ersetzen · Menge reduzieren) fällt sonst über
    Objektnummern, die niemand einordnen kann (Testnotiz #387).

    Die Zeile beantwortet drei Dinge, sonst beantwortet sie keines (Testnotiz #393): **wer**
    verliert (ein Auftrag – sein Name ist der Artikelname, darum steht die Datensatzart
    dabei), **wie viel** (in der Einheit des Artikels, nicht in seinem Namen) und **woher**
    (``sources``: aus welcher Instanz).

    **Jeder Betroffene braucht eine Antwort** (Testnotiz #397). Früher unterschied ein Feld
    ``needs_decision`` zwei Sorten – ein festes Subjekt (Abweichung/Retoure/Bereitstellung)
    galt als «schrumpft lautlos mit». Das war eine zweite Logik für dieselbe Lage; sie ist
    entfallen, und mit ihr das Feld."""
    object_id: int
    name: Optional[str] = None
    reason: Optional[str] = None      # deviation | supply | return | provisioning | None
    article_name: Optional[str] = None
    unit: Optional[str] = None        # Einheit der Menge (stk | kg | …)
    quantity: float = 0               # was er an den gewählten Instanzen VERLIERT
    sources: list[AffectedShare] = []


class StepShortfall(BaseModel):
    """Ein ungedeckter Bedarf des **Auftrags** (Artikel + Fehlmenge).

    Die Fehlmenge gehört dem Auftrag, nicht einem Schritt: sie entsteht aus «Soll − Gesichert»
    und ist dieselbe Aussage, egal welcher Schritt gerade dran ist. Früher hing sie an jedem
    Subjekt-Schritt – dieselbe Zahl mehrfach, und in einem Prozess ohne Subjekt-Schritt
    (z. B. reine Beschaffung) war sie **gar nicht** sichtbar.

    ``kind`` sagt, WAS fehlt: ``subject`` = die Fertigware, die der Auftrag schuldet (dafür
    gibt es «Ohne Ersatz weiter») · ``component`` = Material, das ein Ressourcen-Schritt
    verbraucht (das kann man nicht wegbestätigen – ohne Material wird nichts gebaut).

    ``available_*`` beschreibt, ob & womit sich der Bedarf **aus vorhandenem Lagerbestand**
    decken liesse (für «Ersetzen» / «Bestimmte Instanz wählen»)."""
    article_object_id: Optional[int] = None
    article_name: Optional[str] = None
    quantity: float   # Bruchmenge möglich (kg/m²/…)
    kind: str = "subject"          # subject | component
    # **Ist dem Auftrag egal, WELCHES Stück es ist?** Nur dann ist «Ersetzen» eine ehrliche
    # Antwort. Trägt das Fehlende bereits die Geschichte dieses Auftrags – er hat es selbst
    # erzeugt oder schon daran gearbeitet –, wäre ein frisches Stück kein Ersatz: es hat die
    # bisherigen Schritte nie durchlaufen. Abgeleitet, kein Schalter (``recovery.is_replaceable``).
    replaceable: bool = True
    available_quantity: float = 0
    available_instances: list[ShortfallInstance] = []


class StepResolution(BaseModel):
    """**Was an diesem Schritt entschieden wurde**, als er unterdeckt war (Notiz #281).

    Ohne diese Spur sieht man später nur das Ergebnis (der Auftrag lief weiter), nicht den
    Weg dorthin – dabei ist gerade die Entscheidung die Geschichte des Auftrags. Quelle ist
    der **Event-Strom**, kein neues Feld; die Formulierung macht das Frontend."""
    kind: str                              # covered_from_stock | quantity_confirmed | share_taken
    article_object_id: Optional[int] = None
    article_name: Optional[str] = None
    quantity: Optional[float] = None       # gedeckte/entzogene Menge
    quantity_from: Optional[float] = None  # vorherige Sollmenge (quantity_confirmed)
    quantity_to: Optional[float] = None    # neue Sollmenge
    # **Welche Instanz** – damit später nachvollziehbar ist, dass ursprünglich Stück X
    # zugeteilt war und nun Stück Y gilt. Gleich geführt für FIFO wie für Hand-Auswahl.
    instance_object_ids: list[int] = []
    other_order_object_id: Optional[int] = None   # wer den Anteil geholt hat (share_taken)
    at: Optional[datetime] = None
    by: Optional[str] = None


class FlowLot(BaseModel):
    """**Eine Materialmenge auf einer Kante des Flusses** – «4 × 100000590» (Notiz #413).

    Der Prozess zeigt nicht nur, WAS getan wird, sondern **womit**: welche Instanz, wie viel
    davon, und – am Abzweig – wie viel wieder zurückkommt. Genau daran sieht man, dass 2
    Stück hineingingen und 0 zurückkamen, weil sie verschrottet wurden.

    Mehrere Artikel und mehrere Instanzen sind der Normalfall, nicht die Ausnahme: darum ist
    es eine **Liste** und jede Zeile nennt ihren Artikel.

    **Die Kante trägt die vier Angaben, die den Verlauf nachvollziehbar machen** (Notiz
    #426): welche **Instanz**, welcher **Artikel**, **wo** sie liegt und **wie viel**. Kurz
    steht Menge × Instanz; Artikel und Standort erscheinen im Hover, und beide Objektnummern
    öffnen ihren Datensatz. Sie werden hier **einmal** aufgelöst (batch, kein N+1) statt in
    jeder Ansicht neu zusammengesucht – dieselbe Zeile speist die Hauptachse (was der Auftrag
    hält) und die Abzweige (was hineinging).

    **Die Menge schrumpft nicht, der Zustand ändert sich** (Testnotiz #481): wird ein Stück
    verschrottet, verschwinden weder die Instanz noch ihre Menge – nur ihr Zustand ist ein
    anderer. Darum trägt jede Zeile die beiden Instanz-Achsen mit, und die Oberfläche
    projiziert sie auf **eine Ampelfarbe** (``lib/process.instanceStatusConfig`` – dieselbe
    Projektion wie an der Instanz selbst, kein zweites Regelwerk).

    **Der Zustand hängt an der MENGE, nicht an der Instanz** (Testnotizen #483/#485). Bei
    Einzelserialisierung fällt beides zusammen – eine Instanz ist 1 Stück und hat einen
    Zustand. Bei einer **Charge** nicht: von 4 Stück können 3 in Arbeit und 1 verschrottet
    sein. Eine Zeile beschreibt darum immer nur **eine Menge in einem Zustand**; dieselbe
    Instanz kann mehrere Zeilen haben. (Der Vorschlag, eine Charge intern in
    ``Nummer_01…_04`` zu zerlegen, führt zum selben Ergebnis – aber ohne dessen Kosten: eine
    Charge darf gebrochen sein (2.5 kg), ihre Objektnummer ist systemweit eindeutig, und
    1000 Zeilen je Reservierung wären ein hoher Preis für eine Anzeige-Frage.)"""
    instance_object_id: int
    # **Welche Stücke** – die Kante nennt die Nummern, nicht nur die Anzahl
    # (``services/units.py``). Gekappt; ``unit_count`` sagt, wie viele es insgesamt sind.
    units: list[InstanceUnit] = []
    unit_count: int = 0
    article_id: Optional[int] = None
    article_object_id: Optional[int] = None
    article_name: Optional[str] = None
    quantity: float
    unit: Optional[str] = None
    location_label: Optional[str] = None
    quality: Optional[str] = None        # pending | passed | blocked
    disposition: Optional[str] = None    # in_process | in_stock | consumed | sold | scrapped
    # Gehört diese Menge gerade einem **laufenden** Auftrag? Dann ist sie nicht «frei am
    # Lager», auch wenn die Instanz das für ihren Rest sagt (Testnotiz #485).
    reserved: bool = False
    # **Wann** diese Menge in diesen Zustand kam – nur bei einem Abgang gesetzt. Eine Kante
    # des Flusses zeigt den Zustand, den die Menge **damals** hatte: was später passiert ist,
    # gab es dort noch nicht (Testnotiz #488). Ohne den Zeitpunkt trüge jede durchlaufene
    # Kante rückwirkend den heutigen Zustand.
    at: Optional[datetime] = None


class FlowEdge(BaseModel):
    """**Eine Kante der Prozess-Achse – fertig gerechnet** (ADR 007, Stufe «das Frontend
    zeichnet, der Server weiss»).

    Die Oberfläche hat jahrelang Wahrheit AUSGERECHNET (Material-Arithmetik, Stichtage,
    Zustands-Zeitmaschine als React-Code) – und jede Abweichung von der Server-Sicht war
    eine Testnotiz. Jetzt liefert der Server jede Kante fertig: welches Material hier lag
    (im Zustand von damals, #488), ob der Fluss bis hierhin gekommen ist und ob der Prozess
    GENAU HIER steht (aktuelle Zahlen, Abkürzungs-Knopf). Das Frontend rendert nur noch."""

    lots: list[FlowLot] = []
    reached: bool = False     # bis hierhin ist der Fluss gekommen → Material zeigen
    live: bool = False        # HIER steht der Prozess – aktuelle Zahlen, Abkürzung ansetzen
    # **Ist hier etwas GEFLOSSEN?** – die Strichstärke, an EINER Stelle abgeleitet
    # (Testnotizen #589/#586). «Erreicht» und «geflossen» sind zwei verschiedene Aussagen:
    # zweigt an einer Stelle ALLES ab, ist der Weg darunter erreicht, aber leer – eine volle
    # Linie behauptete dort, es sei etwas durchgegangen. Der Bypass las das längst aus seinem
    # Material (`lots.length > 0` im Frontend); jetzt gilt dieselbe Regel für die ganze Achse,
    # und sie steht im Backend statt zweimal in der Oberfläche.
    flowed: bool = False


class FlowNode(BaseModel):
    """Ein Knoten der Achse: ein Prozessschritt ODER eine Teilung (Abzweige an dieser
    Stelle). Die Reihenfolge der Liste IST die Achse; Kante i liegt über Knoten i."""

    kind: str                          # 'step' | 'split'
    step_id: Optional[int] = None      # kind='step': Verweis auf OrderResponse.steps
    branch_object_ids: list[int] = []  # kind='split': die Abzweige, nach Entstehung sortiert
    reached: bool = False              # die Linie ist bis hierhin stark
    passed: bool = False               # ganz durchlaufen
    # kind='split': das Material NEBEN der Teilung («was blieb hier») – live, solange der
    # Prozess an ihr steht, sonst der Stand von damals.
    bypass: Optional[FlowEdge] = None


class SubOrderStep(BaseModel):
    """**Ein Schritt eines Unter-Auftrags – angeteasert, nicht ausgeführt** (Notiz #409).

    Am Ende ist alles ein Prozess: der abgezweigte Auftrag hat selbst einen Ablauf, und wer
    im Eltern-Auftrag steht, will auf einen Blick sehen, wie weit der Abzweig ist – ohne ihn
    zu öffnen. Darum nur das Minimum, aus dem sich das Miniatur-Flussbild bauen lässt: WELCHES
    Modul und in WELCHEM Zustand. Alles Weitere steht im Unter-Auftrag selbst (ein Klick).

    Das Label steht bewusst NICHT hier: die Schrittnamen sind Registry-Wissen und liegen im
    Frontend an EINER Stelle (``lib/process.STEP_META``, gegen ``domain/event_types.py``
    getestet) – ein zweites Mal mitgeschickt, könnten sie auseinanderlaufen."""
    id: int
    step_type: str
    state: str   # done | active | blocked | locked | failed
    # **Der fachliche Zwischenstand** (Beschaffung/Verkauf) – dieselbe Angabe, die die
    # Modul-Karte auf der Hauptachse trägt. Ohne sie sähe derselbe Schritt im Abzweig anders
    # aus als beim Öffnen des Unter-Auftrags, und genau das darf nicht sein (Testnotiz #492).
    status: Optional[str] = None


class OrderDeviationInfo(BaseModel):
    """Kurzinfo eines Unter-Auftrags (Abweichung · Nachschub · Retoure · Bereitstellung) –
    für die Sichtbarkeit im Eltern-Auftrag."""
    object_id: int
    status: str
    reason: Optional[str] = None   # deviation | supply | return | provisioning
    instance_count: int = 0
    instance_object_ids: list[int] = []
    title: Optional[str] = None
    # Sein **Zustand** gehört an den Knoten im Ablauf (Notiz #404): dort steht ohnehin, dass
    # es diesen Unter-Auftrag gibt – ohne seinen Status muss man ihn öffnen, um zu wissen,
    # ob noch etwas zu tun ist. ``abort_into_id`` unterscheidet dabei «Abgebrochen»
    # (fortgeführt) von «Inaktiv» (verworfen) – dieselbe Projektion wie überall.
    abort_into_id: Optional[int] = None
    # **Wo er relativ zu seinem Schritt steht** – die eine Deklaration für die Darstellung
    # (Notiz #372/#377): «vorher» = er hält den Schritt auf (erst das hier, dann dieser
    # Schritt – Abweichung, Nachschub, herbeigeschafftes Material); «nachher» = er folgt aus
    # ihm (die Ware kommt an, nachdem bestellt wurde). Das Frontend platziert nur, es
    # entscheidet nicht – darum trägt jeder Unter-Auftrag seine Position selbst, statt dass
    # drei getrennte Listen im Fluss wieder zusammengesetzt werden müssten.
    stage: str = "before"          # before | after
    # **Sein eigener Ablauf, angeteasert** (Notiz #409): der Knoten zeigt die Module des
    # Abzweigs als Miniatur-Fluss – wie weit er ist, sieht man damit ohne ihn zu öffnen.
    steps: list[SubOrderStep] = []
    # **Das Material des Abzweigs** (Notiz #413) – dieselbe Zeile, die er auf seiner eigenen
    # Achse trägt (``order_material``), damit der Teaser und der geöffnete Unter-Auftrag nicht
    # zwei Zahlen für denselben Vorgang zeigen (Testnotiz #482).
    flow_in: list[FlowLot] = []
    # Was er dem Bestand **endgültig** entzogen hat (verschrottet/verkauft/verbaut). Der Fluss
    # leitet daraus zweierlei ab: wie viel nach dem Abzweig auf der Achse weiterläuft – und ob
    # überhaupt etwas zurückkommt. Kommt nichts zurück, geht die Prozesslinie gar nicht erst
    # zum Eltern-Auftrag zurück (Testnotiz #481) – einfacher kann man es nicht sagen.
    flow_lost: list[FlowLot] = []
    # **Was tatsächlich schon zurück IST** – leer, solange der Abzweig läuft (Testnotiz #496).
    #
    # Eine Teilung hat DREI Stellen, nicht zwei: **über** ihr das ganze Material, **neben** ihr
    # das, was NICHT abgezweigt ist, und **unter** ihr das Verbliebene plus das
    # Zurückgekommene. Die Achse hatte für die letzten beiden nur EINE Menge – also musste sie
    # den Bypass verfälschen, damit die Rechnung darunter aufging: ein Stück, das komplett in
    # die Abweichung ging, stand trotzdem neben ihr auf dem Hauptprozess.
    flow_back: list[FlowLot] = []
    # **Kommt etwas zurück?** – dieselbe Ableitung wie am Rückweg-Knoten des Unter-Auftrags
    # selbst (``orders.returns_material``). Wurden sie getrennt hergeleitet, zeigte derselbe
    # Abzweig im Eltern-Auftrag ein anderes Bild als beim Öffnen (Testnotiz #492).
    # (Antwort auf «geht die Linie überhaupt zurück?» – ``flow_back`` auf «was ist schon da?».)
    returns_material: bool = True
    # Der Name des Abzweigs (dieselbe Ableitung wie im Feed) – der Teaser nennt die Sache,
    # nicht nur seinen Grund.
    name: Optional[str] = None


class OrderOrigin(BaseModel):
    """**Woher dieser Unter-Auftrag kam – und wohin er zurückgibt** (Notiz #409).

    Der Abzweig ist im Eltern längst sichtbar (``OrderStepInfo.sub_orders``); die Gegen-
    richtung fehlte: wer in einer Abweichung steht, sah nicht, aus welchem Auftrag und aus
    welchem **Schritt** sie hervorgegangen ist – und schon gar nicht, wohin ihre Stücke beim
    Abschluss zurückkehren. Beides ist keine neue Wahrheit, sondern dieselbe von der anderen
    Seite gelesen: ``parent_order_id`` + ``origin_step_id`` für das Woher, und für das Wohin
    genau die Ableitung, die es auch TUT (``subject.lender_of`` bzw. das Nachschub-Pegging) –
    keine zweite Behauptung daneben.

    Wichtig: das Rückgabe-Ziel ist **nicht** zwingend der Eltern. Wurde der Eltern
    abgebrochen, reicht die Ausleihe durch bis zum nächsten laufenden Auftrag (Notiz #404) –
    genau den nennt ``returns_to_object_id``."""
    order_object_id: int
    order_name: Optional[str] = None
    order_status: Optional[str] = None
    order_reason: Optional[str] = None
    # (Entfallen sind die Brotkrumen-``chain`` (Notiz #428) **und** der angeteaserte
    #  Eltern-Prozess (#436/#437): der aktuelle Auftrag steht im Kopf des Fensters, der
    #  übergeordnete als Verweis im Fluss – der reicht. Ein Prozessschritt des Eltern gehört
    #  in den Eltern-Auftrag, nicht als Vorschau daneben.)
    # Wohin die Stücke beim Abschluss zurückgehen (leer = niemand wartet mehr darauf).
    returns_to_object_id: Optional[int] = None
    returns_to_name: Optional[str] = None
    # **Was tatsächlich zurückgegangen ist** – NICHT, was einmal zurückgehen wird
    # (Testnotiz #554). Die Rückgabe-Kante zeigte bisher das lebende Material des Auftrags,
    # also eine Vorhersage; dieselbe Stelle im Eltern-Auftrag las längst die Buchungen
    # (``_flow_back``). Zwei Bilder derselben Sache – jetzt eine Quelle: leer, solange
    # nichts zurück ist.
    returned_lots: list[FlowLot] = []


class OrderStepInfo(BaseModel):
    """Ein Schritt im Auftrag-Stepper (für die Fortschritts-Visualisierung).

    Mehr-Operationen-Routing: ``id`` (Schritt-Definition) ist der eindeutige
    Schlüssel; je Schritt ist – passend zum Typ – genau ein Ausführungs-Embed
    gesetzt, damit mehrere gleichartige Schritte unabhängig bedient werden."""

    id: int = 0
    step_type: str
    position: int
    label: str
    state: str   # done | active | blocked | locked | failed
    completed_by: Optional[str] = None   # wer hat den Schritt abgeschlossen
    completed_at: Optional[datetime] = None  # wann
    # (``shortfall``/``waiting_for`` sind an den **Auftrag** gewandert: die Fehlmenge ist
    # eine Aussage über den Auftrag, nicht über einen Schritt – siehe ``OrderResponse``.)
    # Was an diesem Schritt bereits entschieden wurde (ersetzt / ohne Ersatz weiter) –
    # auch dann noch, wenn er längst wieder läuft.
    resolutions: list[StepResolution] = []
    # **Die Unter-Aufträge, die AUS DIESEM SCHRITT hervorgegangen sind** (``orders.
    # origin_step_id``) – Abweichung, Nachschub und Bereitstellung in EINER Liste, weil sie
    # dasselbe sind: ein eigener Auftrag, der an dieser Stelle in den Ablauf hineinragt. Wo
    # genau, sagt jeder von ihnen selbst (``OrderDeviationInfo.stage``).
    #
    # Vorher waren es drei Felder für diese eine Aussage (``provisionings`` +
    # ``provisioning_stage`` + ``deviations``, dazu das nie befüllte
    # ``provisioning_order_object_ids``) – und das Frontend musste sie mit einer
    # Fallunterscheidung wieder zusammensetzen.
    sub_orders: list[OrderDeviationInfo] = []

    # Ausführungs-Embed des konkreten Schritts (nur das zum Typ passende ist gesetzt).
    # «Beschaffung» und «Verkauf» sind – wie jeder andere Schritttyp – GENAU EIN Schritt,
    # auch bei mehreren Artikeln/Positionen: ``purchases``/``sales`` tragen dann mehrere
    # Belege (einen je Artikel/Position, gleicher ``step_id``); ``purchase``/``sale``
    # bleiben die ERSTEN (Bequemlichkeit/Rückwärtskompatibilität für den Einzel-Artikel-
    # Fall, wo beide identisch sind).
    purchase: Optional[PurchaseEmbed] = None
    purchases: list[PurchaseEmbed] = []
    sale: Optional[SaleEmbed] = None
    sales: list[SaleEmbed] = []
    inspection: Optional[InspectionEmbed] = None
    movement: Optional[MovementEmbed] = None
    resource: Optional[ResourceEmbed] = None
    disposal: Optional[DisposalEmbed] = None
    document: Optional[DocumentEmbed] = None

# completed wird automatisch gesetzt (alle Prozessschritte erledigt)
ALLOWED_STATUS = ("draft", "released", "inactive", "completed")

# FIX: Obergrenze für Bestellmengen – ``quantity`` war nur nach unten begrenzt; eine
# absurde Menge (z. B. 2e9) hätte bei der Freigabe versucht, ebenso viele Einzel-
# Instanzen zu erzeugen (Worker-/DB-Flut). Grosszügig über jedem realen Bedarf (~10 MA).
MAX_ORDER_QUANTITY = 100_000


def _validate_qty(v: Optional[float]) -> Optional[float]:
    """Menge > 0 und ≤ MAX. Bruchmengen (kg/m²/m³/l) sind erlaubt – ob ein Artikel nur
    GANZE Stück haben darf (Einzelteil), prüft der Router gegen die Serialisierung."""
    if v is None:
        return v
    if v <= 0:
        raise ValueError("Menge muss grösser als 0 sein")
    if v > MAX_ORDER_QUANTITY:
        raise ValueError(f"Menge darf höchstens {MAX_ORDER_QUANTITY} betragen")
    return v


def _validate_future_date(v: Optional[date]) -> Optional[date]:
    """Wunsch-Liefertermin darf nicht in der Vergangenheit liegen."""
    if v is None:
        return v
    if v < date.today():
        raise ValueError("Wunsch-Liefertermin darf nicht in der Vergangenheit liegen")
    return v


class InstancePick(BaseModel):
    """**Ein Anteil, kein Ding** – die eine Form, in der eine Instanz-Auswahl daherkommt.

    Eine Instanz ist eine **Menge**, und ihre Menge ist immer vollständig aufgeteilt: jeder
    Anteil gehört genau einem Auftrag oder ist frei (``instances.reservations``). Wer
    auswählt, wählt darum drei Dinge zugleich – **welche** Instanz, **wie viel** davon und
    **wem** er es wegnimmt.

    Der dritte Punkt ist der entscheidende: hält eine Charge à 4 Stück zwei Ansprüche
    (Hauptauftrag 2, Abweichung 2) und ein dritter Auftrag greift 1 Stück, wäre ohne ihn
    nicht entscheidbar, wer verliert. Mit ihm ist es keine Regel mehr, sondern ein Klick –
    die Auswahl zeigt die Anteile als Zeilen, und man klickt die Zeile an.

    ``from_order_object_id`` leer = **freier Anteil**: es verliert niemand etwas, es wird
    niemand gefragt. ``quantity`` leer = die ganze Instanz."""

    instance_object_id: int
    quantity: Optional[float] = None
    from_order_object_id: Optional[int] = None


class OrderLineCreate(BaseModel):
    """Eine weitere Position – beim Erteilen (``POST /orders``) oder an einem bestehenden
    Auftrag (``POST .../lines``). Macht ihn (falls noch nicht) zu einem Mehrpositionen-
    Auftrag; nur im Entwurf möglich, „Herstellen" scheidet dann aus (siehe
    ``services/order_lines.py``)."""

    article_id: int
    quantity: float   # ganze Stück ODER Bruchmenge (kg/m²/m³/l)
    # **Die Position bringt ihre Auswahl mit.** Ein Auftrag entsteht als Ganzes (Testnotiz
    # #386) – also auch mit dem, was je Position gewählt wurde, statt in einem zweiten
    # Aufruf nachgereicht zu werden. Leer = FIFO.
    picks: Optional[list[InstancePick]] = None

    @field_validator("quantity")
    @classmethod
    def _qty_positive(cls, v: float) -> float:
        return _validate_qty(v)


class OrderLinePins(BaseModel):
    """Gewählte **Anteile** EINER Position statt FIFO (analog ``OrderUpdate.picks`` am
    Einzel-Artikel-Auftrag). Leere Liste = zurück auf FIFO."""

    picks: list[InstancePick] = []


class OrderUpdate(BaseModel):
    status: Optional[str] = None
    article_id: Optional[int] = None
    quantity: Optional[float] = None   # ganze Stück ODER Bruchmenge (kg/m²/m³/l)
    # Vorgewählte Subjekt-Instanzen im Entwurf anpassen (Mehrfachauswahl, gleicher Artikel).
    # **Die Auswahl bestimmt die Art des Auftrags** (``subject.classify_pick``): verkaufte
    # Instanzen → Retoure · gebundene (in Arbeit/reserviert/gesperrt) → **Abweichung** ·
    # freie → gewöhnlicher Auftrag. Ein Tag, kein zweiter Weg.
    picks: Optional[list[InstancePick]] = None
    desired_delivery_date: Optional[date] = None
    recurrence_active: Optional[bool] = None
    recurrence_interval_days: Optional[int] = None
    recurrence_lead_time_days: Optional[int] = None
    recurrence_anchor: Optional[date] = None
    # FIX: ``is_active`` ist kein Client-Feld mehr: ein PATCH {"is_active": false} auf einen
    # FREIGEGEBENEN Auftrag hätte ihn aus allen Sichten entfernt, OHNE seine Reservierungen
    # zu lösen (dauerhaft blockierter Bestand). Deaktivieren läuft über den Status-Fluss
    # (Entwurf → inaktiv) bzw. «Abbrechen» (Folgeauftrag) – nie über ein rohes Flag.
    expected_updated_at: Optional[datetime] = None   # Optimistic Locking (optional)

    @field_validator("status")
    @classmethod
    def _status_allowed(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if v not in ALLOWED_STATUS:
            raise ValueError(f"Status muss eine von {', '.join(ALLOWED_STATUS)} sein")
        return v

    @field_validator("quantity")
    @classmethod
    def _qty_positive(cls, v: Optional[int]) -> Optional[int]:
        return _validate_qty(v)

    @field_validator("desired_delivery_date")
    @classmethod
    def _date_future(cls, v: Optional[date]) -> Optional[date]:
        return _validate_future_date(v)


class OrderCreate(BaseModel):
    """**Auftrag erteilen** – Anlage UND Freigabe in EINEM Aufruf.

    Ein Auftrag entsteht **als Ganzes oder gar nicht**: Artikel, Menge, Positionen, der
    Ablauf und die Instanz-Auswahl kommen zusammen an, und erst hier bekommt er seine
    **Objektnummer**. Vorher entstand er beim Tippen (Auto-Save) und wartete als Entwurf –
    wer es sich anders überlegte, hinterliess einen nummernlosen Datensatz im System
    (Testnotiz #386). Jetzt gilt: freigegeben oder es hat ihn nie gegeben. Der Entwurf lebt
    bis dahin im Browser; er wird **nicht** zwischengespeichert.

    Scheitert irgendeine Prüfung (fehlende Bezugsquelle, Unterdeckung ohne Antwort, …),
    wird NICHTS angelegt – auch keine Objektnummer verbraucht.

    Anker ist IMMER **Artikel + Menge**. Was damit geschieht, ergibt sich aus dem Ablauf,
    der danach im Entwurf definiert wird: kein eigener Ablauf → Erzeugung (Artikel-Prozess);
    eigener Ablauf → Operation auf ``quantity`` Instanzen des Artikels (FIFO ab Lager,
    optional durch fixierte Instanzen ergänzt). Die Subjektart wird also abgeleitet.

    Weitere Artikel lassen sich danach jederzeit über ``POST .../lines`` ergänzen (Mehr-
    positionen-Auftrag – „Aus Lager"/„Instanz wählen" über mehrere Artikel; „Herstellen"
    ist dann nicht mehr möglich, siehe ``services/order_lines.py``)."""

    article_id: int
    quantity: float   # ganze Stück ODER Bruchmenge (kg/m²/m³/l)
    # **Vorauswahl**, keine Fixierung (Testnotiz #371): der Abkürzungs-Knopf an einer Instanz
    # legt einen ganz gewöhnlichen Auftrag an und trägt die Instanz gleich ein – als
    # Eingabehilfe. Änderbar wie jede andere Auswahl; was daraus folgt (Abweichung/Retoure/
    # gewöhnlicher Bedarf), leitet ``subject.classify_pick`` ab.
    picks: Optional[list[InstancePick]] = None
    # Weitere Positionen (Mehrpositionen-Auftrag) – im Entwurf gesammelt, hier mitgeliefert.
    lines: Optional[list[OrderLineCreate]] = None
    # Der **auftragseigene Ablauf**. Ohne eigene Schritte fährt der Auftrag den
    # Artikel-Prozess (Erzeugung) – das bleibt unverändert.
    steps: Optional[list[ArticleProcessStepCreate]] = None
    # **Die Rückführung ist gekappt** (Testnotiz #563): was dieser Auftrag übernimmt, kommt
    # nicht zurück. Der Verleiher endet damit an dieser Stelle – abgebrochen, fortgeführt
    # hier. Eine Aussage über die Zukunft, die das System nicht selbst treffen kann.
    returns_nothing: Optional[bool] = None
    desired_delivery_date: Optional[date] = None
    # Wiederkehrend (direkt am Auftrag, kein eigenes Objekt)
    recurrence_active: Optional[bool] = None
    recurrence_interval_days: Optional[int] = None
    recurrence_lead_time_days: Optional[int] = None
    recurrence_anchor: Optional[date] = None

    @field_validator("quantity")
    @classmethod
    def _qty_positive(cls, v: float) -> float:
        return _validate_qty(v)

    @field_validator("desired_delivery_date")
    @classmethod
    def _date_future(cls, v: Optional[date]) -> Optional[date]:
        return _validate_future_date(v)


class OrderCoverStock(BaseModel):
    """«Aus Lager decken» / «Andere Instanz wählen»: die offene Subjekt-Fehlmenge eines
    blockierten Schritts aus vorhandenem Lagerbestand decken. Ohne ``instance_object_ids``
    wird FIFO aus dem freien Bestand reserviert; mit Auswahl genau diese Instanzen."""
    instance_object_ids: Optional[list[int]] = None


class OrderLineInfo(BaseModel):
    """Eine Position eines Mehrpositionen-Auftrags (``order.article_id`` ist dann NULL)."""
    id: int
    article_id: int
    article_object_id: Optional[int] = None
    article_name: Optional[str] = None
    article_unit: Optional[str] = None
    quantity: float   # Bruchmenge möglich (kg/m²/…)
    position: int


class OrderSummary(BaseModel):
    """Schlanke Auftrags-Sicht für den Feed (OHNE Prozess-Embeds).

    Der Feed braucht nur Kopf-Daten; die teuren Embeds (FIFO-Vorschau, Stichproben,
    Verlauf) werden erst im Detail (``GET /orders/{id}``) berechnet."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    object_id: Optional[int]
    status: str
    article_id: Optional[int]
    quantity: Optional[float]   # Bruchmenge möglich (kg/m²/…)
    desired_delivery_date: Optional[date]
    is_active: bool
    created_at: datetime
    updated_at: datetime
    # **Der Name dieses Datensatzes** – abgeleitet in `orders.order_display_name`, damit
    # Feed und Detail dasselbe zeigen (nie das Wort «Auftrag» als Typ-Platzhalter).
    name: str = "Auftrag"
    # denormalisiert (Batch-geladen, nicht je Auftrag)
    article_name: Optional[str] = None
    article_object_id: Optional[int] = None
    article_unit: Optional[str] = None
    purchase_status: Optional[str] = None   # für das Status-Badge im Feed
    recurrence_active: bool = False         # wiederkehrender Auftrag (Badge)
    recurrence_due: bool = False            # fällig (Termin − Vorlaufzeit erreicht)
    replaced_by_id: Optional[int] = None
    parent_order_id: Optional[int] = None   # gesetzt → Unter-Auftrag (Badge)
    reason: Optional[str] = None            # deviation | supply (Art des Unter-Auftrags)
    abort_into_id: Optional[int] = None     # gesetzt → «Abbruch ausstehend»


class OrderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    object_id: Optional[int]
    status: str
    # Abgeleitete Subjektart (kein Modus-Flag): produce | stock | instance
    subject_role: str = "produce"
    # Aggregierte Bestandswirkung des Prozesses: increase | decrease | mixed | neutral
    stock_effect: str = "neutral"
    title: Optional[str]
    # Der Name dieses Datensatzes (dieselbe Ableitung wie im Feed – `order_display_name`).
    name: str = "Auftrag"
    article_id: Optional[int]
    quantity: Optional[float]   # Bruchmenge möglich (kg/m²/…)
    desired_delivery_date: Optional[date]
    is_active: bool
    created_at: datetime
    updated_at: datetime

    # Wiederkehrend (am Auftrag)
    recurrence_active: bool = False
    recurrence_interval_days: Optional[int] = None
    recurrence_lead_time_days: int = 0
    recurrence_anchor: Optional[date] = None
    recurring_parent_id: Optional[int] = None
    recurrence_due: bool = False

    # Denormalisierter Artikel + eingebetteter Prozess (Beschaffung/Verkauf)
    article_name: Optional[str] = None
    article_object_id: Optional[int] = None
    article_size: Optional[str] = None
    article_unit: Optional[str] = None
    article_weight_kg: Optional[Decimal] = None
    article_serialization: Optional[str] = None
    article_supplier_article_number: Optional[str] = None
    purchase: Optional[PurchaseEmbed] = None
    sale: Optional[SaleEmbed] = None
    # Positionen eines Mehrpositionen-Auftrags (leer beim gewöhnlichen Einzel-Artikel-Auftrag).
    order_lines: list[OrderLineInfo] = []
    instances: list[InstanceEmbed] = []
    inspection: Optional[InspectionEmbed] = None
    movement: Optional[MovementEmbed] = None
    resource: Optional[ResourceEmbed] = None
    disposal: Optional[DisposalEmbed] = None
    document: Optional[DocumentEmbed] = None
    steps: list[OrderStepInfo] = []
    # **Was diesem Auftrag fehlt** – Fertigware (``kind='subject'``) und/oder Material eines
    # Ressourcen-Schritts (``kind='component'``). EINE Aussage über den Auftrag, an EINER
    # Stelle – und kein Auftrag geht «fertig», solange etwas offen ist.
    shortfall: list[StepShortfall] = []
    # **Wem nimmt dieser ENTWURF etwas weg?** Nur am Entwurf gefüllt – dort steht die Frage,
    # bevor sie gestellt wird (Notiz #387). Leer, sobald er freigegeben ist.
    affects: list[AffectedOrder] = []
    # **Ruht der Prozess?** – abgeleitet aus derselben Fehlmenge (``process.is_paused``),
    # kein zweiter Zustand daneben. Fehlt dem Auftrag sein Subjekt (z. B. weil eine offene
    # Abweichung ein Stück in Klärung hält) oder ist Material noch unterwegs, läuft KEIN
    # Schritt weiter. Aufgelöst wird das über die drei Antworten der Unterdeckung.
    paused: bool = False
    # Worauf der Auftrag **wartet**: offene Unter-Aufträge, die diese Fehlmenge bereits
    # binden – eine **Abweichung** (das Stück ist in Klärung) oder ein laufender **Nachschub**.
    # Solange etwas hier steht, ist die Entscheidung getroffen: die Oberfläche zeigt nur noch
    # den Zustand, statt dieselbe Frage ein zweites Mal zu stellen. Ein **steckengebliebener**
    # Unter-Auftrag zählt NICHT (``supply.covering_sub_orders``) – sonst wartete der Auftrag
    # für immer auf etwas, das nie kommt.
    waiting_for: list[int] = []
    # Ersetzen (Nachvollziehbarkeit): Nachfolger / Vorgänger (Objektnummern)
    replaced_by_id: Optional[int] = None
    replaces_id: Optional[int] = None
    # Unter-Auftrag (parent) + Grund + Abbruch-Folgeauftrag (Objektnummern)
    parent_order_id: Optional[int] = None
    reason: Optional[str] = None   # deviation | supply | return | provisioning (gesetzt → Unter-Auftrag)
    abort_into_id: Optional[int] = None
    # **Die Rückführung ist gekappt** (Testnotiz #563): dieser Auftrag gibt nichts zurück.
    returns_nothing: bool = False
    # **Woher er kam und wohin er zurückgibt** – nur an einem Unter-Auftrag gesetzt (#409).
    origin: Optional[OrderOrigin] = None
    # **Das Material dieses Auftrags** – die Kanten seiner Achse (Notiz #426). Aus **derselben**
    # Quelle wie ``OrderDeviationInfo.flow_in`` (``services/orders.order_material``): dieselbe
    # Zeile, dieselbe Menge, damit derselbe Vorgang nicht je nach Blickrichtung zwei Zahlen
    # trägt (Testnotizen #479/#480/#482).
    flow_lots: list[FlowLot] = []
    # Was er dem Bestand endgültig entzogen hat – siehe ``OrderDeviationInfo.flow_lost``.
    flow_lost: list[FlowLot] = []
    # **Was ist passiert** – das Material-Journal dieses Auftrags (ADR 007), chronologisch
    # und unveränderlich. Die dritte der drei Fragen, am Auftrag beantwortet; die Instanz
    # zeigt dieselben Zeilen aus der anderen Richtung. Nur fürs Personal gefüllt.
    history: list[MaterialMoveView] = []
    # **Die fertig gerechnete Prozess-Achse** (Knoten + Kanten): das Frontend zeichnet sie
    # nur noch – keine Material-Arithmetik, keine Stichtags-Zeitmaschine im Client mehr.
    flow_nodes: list[FlowNode] = []
    flow_edges: list[FlowEdge] = []    # len = flow_nodes + 1; Kante i liegt ÜBER Knoten i
    # Sichtbarkeit der Unteraufträge im Eltern-Auftrag + Pause-Zustand
    deviations: list[OrderDeviationInfo] = []        # Abweichungen (pausieren den Eltern)
    supply_orders: list[OrderDeviationInfo] = []     # Nachschub (deckt Bedarf; blockiert nur Schritte)
    returns: list[OrderDeviationInfo] = []           # Retouren/Erstattungen
    # Bereitstellungen: bringen vorhandenes Material an den Ort, den ein Schritt verlangt.
    # Eigener Topf, weil eine Bereitstellung sonst im ``deviations``-Topf landete und als
    # «Abweichung» erschiene.
    provisionings: list[OrderDeviationInfo] = []
    # (``paused`` ist entfallen: eine Abweichung hält den Auftrag nicht mehr an, sie nimmt ihr
    #  Stück heraus – was fehlt, blockiert den Schritt, der es braucht.)
    # Fakturierende Gesellschaft (Seller of Record, ADR 006) – NUR bei einem Verkauf/einer
    # Retoure gesetzt: ein Produktions-/Beschaffungsauftrag hat keinen Kunden, also keinen
    # Fakturierenden. Eingefroren auf dem Verkaufsbeleg ≻ live aus dem Kundenland ≻ Betreiber
    # (`sale.seller_company_for_order`); die Objektnummer ist im ERP klickbar.
    seller_company_object_id: Optional[int] = None
    seller_company_name: Optional[str] = None
