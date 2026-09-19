"""Instanz und Einzelinstanz – die API-Form, **nur lesend**.

Die Menge steht überall als **Anzahl** da, nie als Dezimalzahl: eine Einzelinstanz ist
genau ein Stück, also ist die Menge einer Instanz ihre Anzahl Einzelinstanzen. Es gibt
kein Mengen-Feld, das man setzen könnte.

Es gibt auch keine **Eingabe**-Form mehr: eine Einzelinstanz entsteht mit ihrer Instanz
und die mit einem Auftrag; gelöscht wird nie. Und die Gruppe trägt **keinen Zustand** –
den haben nur ihre Stücke (Testnotizen #675/#678/#679).
"""

from datetime import datetime
from typing import Mapping, Optional

from pydantic import BaseModel, ConfigDict

from ..domain import statuses as st
from .place import PlaceRef, UnitPlace


class InstanceUnitResponse(BaseModel):
    """Eine Einzelinstanz – das Arbeitsobjekt."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    suffix: int
    number: str          # <Objektnummer der Instanz>-<suffix>, die sichtbare Identität
    status: str
    #: In welchem Auftrag läuft dieses Stück gerade? ``None`` = in keinem. Das ist
    #: dieselbe Aussage wie ``status == im_prozess``, nur brauchbar: sie sagt **wo**.
    order_object_id: Optional[int] = None
    #: **Wie viele Teile stecken darin?** Nur die Zahl – die Liste kommt auf Klick
    #: (``GET …/units/{suffix}/genealogy``). Sie steht hier, damit die Zeile weiss, ob es
    #: überhaupt etwas aufzuklappen gibt; ein Pfeil an jeder von 5000 Zeilen, hinter dem
    #: nichts liegt, ist ein Versprechen, das die Liste nicht halten kann.
    parts_count: int = 0
    #: **Wo dieses Stück liegt** – unmittelbarer Halter plus die Kette darüber
    #: (``services/places``). ``None`` heisst **standortlos**, und das ist ein regulärer
    #: Zustand: ein frisch erzeugtes Stück liegt nirgends, bis ein Modul es irgendwohin
    #: bringt. Aufgelöst wird die Kette je **Halter**, nicht je Stück – 60 Schrauben in
    #: einem Regal sind eine Kette, nicht sechzig.
    place: Optional[UnitPlace] = None
    #: ►►► **Wem dieses Stück gehört** – die zweite Achse neben dem Ort. ◄◄◄
    #:
    #: ``None`` heisst **uns**, und das ist der Normalfall: alles, was wir erzeugen,
    #: gehört uns, bis jemand es verkauft. Sonst steht hier die Rechtsperson, der es
    #: gehört – eine Beistellung in unserem Regal, ein verkauftes Stück beim Kunden.
    #:
    #: Es ist **nicht** dasselbe wie der Ort: ein Muster beim Kunden gehört uns, eine
    #: Beistellung bei uns gehört ihm. Und es ist kein Status: der Prozess schreibt den
    #: bei jedem Modul, hier steht das Geschäft.
    owner: Optional[PlaceRef] = None
    created_at: datetime


class OwnerShare(BaseModel):
    """**Wem gehört wie viel?** – ein Segment der Eigentums-Leiste.

    ``owner_object_id = None`` heisst **uns** (das Haus); ``ours`` ist trotzdem ein
    eigenes Feld, denn es gilt auch für eine unserer Gesellschaften: kaufen zwei von uns
    Material, gehört jedes Stück *einer* von beiden – und beides ist «unseres». Die
    Auflösung gehört dem **Server** (``owners.is_ours``), wie die Bestands-Zugehörigkeit
    eines Status: eine Liste unserer Gesellschaften in der Oberfläche wäre die zweite
    Wahrheit, und die veraltet bei der ersten neuen Gesellschaft.
    """

    owner_object_id: Optional[int] = None
    name: str
    ours: bool
    quantity: int


class StockState(BaseModel):
    """Ein Zustand mit seiner Menge – ein Segment der Bestandsleiste.

    Die Aufstellung ersetzt den Zustand, den eine Gruppe nicht haben kann: nicht «diese
    Instanz ist freigegeben», sondern «3 freigegeben, 1 im Prozess».

    ``stock`` sagt, in welchen Block das Segment gehört – ``live`` (aktueller Bestand),
    ``history`` (nur noch Datensatz) oder ``unknown``. **Die Zuordnung kommt vom
    Server**, weil sie eine Eigenschaft des Status ist (``domain/statuses.Status.stock``)
    und keine Liste, die eine Oberfläche pflegt. Ein neuer Status wird damit an genau
    einer Stelle ergänzt, und die Bestandsansicht folgt ohne Änderung.
    """

    status: str
    quantity: int
    stock: str


def stock_states(counts: Mapping[str, int]) -> list["StockState"]:
    """Gezählte Zustände → **Segmente**: in Anzeige-Reihenfolge, je mit Zugehörigkeit.

    Die eine Umwandlung. Sie stand an vier Stellen fast gleich – und hätte beim
    Hinzufügen der Zugehörigkeit an vier Stellen nachgezogen werden müssen.
    """
    return [
        StockState(status=s, quantity=n, stock=st.stock_kind(s))
        for s, n in st.in_order(dict(counts))
    ]


class InstanceResponse(BaseModel):
    """Instanz – die Gruppe, mit ihrer Menge und ihrer Aufstellung.

    ``quantity`` ist **gezählt**, nicht gespeichert – die Instanz hat keine Mengen-Spalte.

    Einen ``status`` trägt sie nicht: eine Gruppe hat keinen Zustand, nur ihre Stücke
    haben einen (Testnotiz #675). ``states`` zählt darum auf, statt zu behaupten.

    **Die Nummern der Stücke stehen nicht drin.** Sie kommen seitenweise über
    ``GET /erp/instances/{id}/units`` – eine 5000er-Charge hier vollständig mitzuliefern
    hiesse, jedes Öffnen der Instanz so teuer zu machen wie die ganze Charge, und die
    Oberfläche müsste 5000 Zeilen auf einmal zeichnen.
    """

    id: int
    object_id: int
    article_id: int
    article_object_id: Optional[int] = None
    article_name: Optional[str] = None
    kind: str
    label: Optional[str] = None
    quantity: int
    states: list[StockState] = []
    #: Dieselbe zweite Aufteilung wie am Artikel, eine Ebene tiefer – damit die
    #: Bestandsansicht an der **Instanz** dieselbe Karte zeigt wie am Artikel und nicht
    #: eine ärmere (``StockView`` ist EIN Modul mit zwei Umfängen).
    owners: list[OwnerShare] = []
    created_at: datetime
    updated_at: datetime
    is_active: bool


class InstanceSummary(BaseModel):
    """Feed-Zeile: ohne die Einzelinstanzen, aber mit ihrer Anzahl **und Aufstellung**.

    ``quantity`` ist die Summe über ``states`` – dieselbe Abfrage, zwei Lesarten. Die
    Zeile behauptet damit keinen Zustand (den hat eine Gruppe nicht), sondern zählt auf.
    """

    id: int
    object_id: int
    article_id: int
    article_name: Optional[str] = None
    kind: str
    label: Optional[str] = None
    quantity: int
    states: list[StockState] = []
    created_at: datetime
    updated_at: datetime
    is_active: bool


class UnitPage(BaseModel):
    """Eine Seite Einzelinstanz-Nummern – plus wie viele es insgesamt sind."""

    units: list[InstanceUnitResponse]
    total: int


class GenealogyPart(BaseModel):
    """Ein Teil in einer Stückliste – **abgeleitet**, nicht gespeichert.

    ``still_in`` trennt die beiden Fragen, die eine Stückliste beantworten muss: *was
    wurde verbaut* (der Log, unveränderlich) und *was steckt heute noch drin* (der
    Zustand). Ein ausgebautes Teil bleibt in der Liste – die Vergangenheit bekommt eine
    Fortsetzung, sie wird nicht gelöscht.
    """

    unit_id: int
    number: str
    status: str
    article_name: Optional[str] = None
    article_object_id: Optional[int] = None
    #: In welchem Auftrag wurde es verbaut. Er steht immer dabei: die Zuordnung läuft
    #: über ihn, und bei mehreren Erzeugnissen je Auftrag ist er die genauere Aussage.
    order_object_id: Optional[int] = None
    still_in: bool = True


class GenealogyHost(BaseModel):
    """Ein Auftrag, in dem dieses Stück verbaut wurde, samt dem, was dort entstand."""

    order_object_id: Optional[int] = None
    products: list[GenealogyPart] = []


class Genealogy(BaseModel):
    """**Woraus besteht es – und worin steckt es?** Beide Richtungen, eine Antwort."""

    parts: list[GenealogyPart] = []
    built_into: list[GenealogyHost] = []


class ArticleStock(BaseModel):
    """**Der Bestand eines Artikels** – die eine Antwort auf «was habe ich davon».

    Drei Ebenen in einer Antwort, und keine davon ist ein gespeichertes Feld:
    ``states``/``total`` beschreiben **alle** Stücke des Artikels (nicht nur die
    angezeigte Seite), ``instances`` ist eine Seite Instanzen mit je ihrer eigenen
    Aufstellung, und die Nummern der Stücke holt die Ebene darunter
    (``GET /erp/instances/{id}/units``) – erst auf Klick, nie auf Vorrat.
    """

    states: list[StockState]
    #: ►►► **Die zweite Aufteilung DERSELBEN Menge: wem gehört sie?** ◄◄◄
    #:
    #: *«Ich muss den globalen Überblick behalten und zugleich wissen, mit was ich als
    #: jeweiliges Unternehmen wirtschaften kann.»* – Das sind zwei Fragen über dieselben
    #: Stücke, und darum ist es dieselbe Gesamtzahl: ``states`` teilt sie nach **Zustand**
    #: auf, ``owners`` nach **Eigentümer**. Summierten sie sich verschieden, wären es
    #: zwei Auskünfte über zwei Dinge, und niemand könnte sie nebeneinander lesen.
    #:
    #: **Eine Liste mit einem einzigen Eintrag ist keine Aussage** – gehört alles uns,
    #: kommt sie leer, und die Oberfläche zeigt dort nichts. Dieselbe Regel wie bei den
    #: Zuständen: was es nicht gibt, steht nicht da.
    owners: list[OwnerShare] = []
    total: int
    instance_total: int
    instances: list[InstanceSummary]

